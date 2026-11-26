"""Tokenize and bind Bleh source into immutable branch definitions."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Mapping
from types import MappingProxyType

from esolangs.exceptions import InterpreterLimitError
from esolangs.languages.bleh._syntax import (
    _Bits,
    _Branch,
    _Call,
    _Expr,
    _Funcs,
    _Join,
    _PAny,
    _Pattern,
    _PLit,
    _PRest,
    _PSplit,
    _PVar,
    _Ref,
    _Seq,
    _Slot,
    _utf8_bits,
)
from esolangs.runtime.source_hints import syntax_error

_BUILTINS = ("print", "debug", "next", "hasNext")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}
_TOKEN = re.compile(
    r"""\s+|//[^\n]*|/\*.*?\*/|(::|\.\.|[:=;,()\[\]{}^])|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\w+)|(.)""",
    re.DOTALL | re.ASCII,
)
_NAME = re.compile(r"\w+", re.ASCII)


def _string(token: str) -> str:
    """Return the bits of a quoted string token."""
    out, chars = [], iter(token[1:-1])
    for raw_char in chars:
        char = raw_char
        if char == "\\":
            escaped = next(chars)
            if escaped not in _ESCAPES:
                raise syntax_error(
                    f"\\{escaped} is not a Bleh string escape",
                    "use \\n \\t \\r \\0 \\\\ \\\" or \\'",
                )
            char = _ESCAPES[escaped]
        out.append(char)
    return _utf8_bits("".join(out))


def _tokens(code: str) -> list[str]:
    out = []
    for match in _TOKEN.finditer(code):
        punct, string, word, stray = match.groups()
        if stray is not None:
            raise syntax_error(
                f"{stray!r} is not part of Bleh's syntax",
                "check for an unterminated string or /* comment",
            )
        token = punct or string or word
        if token:
            out.append(token)
    return out


def _is_bits(token: str) -> bool:
    return not token.strip("01")


def _is_name(token: str) -> bool:
    return bool(_NAME.fullmatch(token)) and not _is_bits(token)


class _Parser:
    """Parse source within a nesting budget independent of the caller stack."""

    def __init__(self, code: str) -> None:
        self.tokens = _tokens(code)
        self.pos = 0
        self.aliases: dict[str, str] = {}
        # Descending through one group formerly used a parser and an item frame.
        self.depth_limit = sys.getrecursionlimit() // 2

    @staticmethod
    def _nesting_error() -> InterpreterLimitError:
        return InterpreterLimitError(
            "the Bleh interpreter recursed deeper than CPython's stack "
            "limit allows while loading this program",
            hint="reduce expression nesting or recursion depth",
        )

    def peek(self, ahead: int = 0) -> str | None:
        at = self.pos + ahead
        return self.tokens[at] if at < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            want = repr(expected) if expected else "more source"
            raise syntax_error(
                f"Bleh expected {want}, got {token or 'the end'!r}",
                "write functions as `name: patterns = expression;`",
            )
        self.pos += 1
        return token

    def name(self) -> str:
        token = self.take()
        if not _is_name(token) or token == "_":
            raise syntax_error(
                f"{token!r} is not a Bleh name",
                "use letters, digits and _, not only 0s and 1s",
            )
        return token

    def program(self) -> dict[str, tuple[_Branch, ...]]:
        funcs: dict[str, tuple[_Branch, ...]] = {}
        while self.peek() is not None:
            if self.peek() == "^":
                self.imports()
                continue
            if self.peek() == "::":
                self.take()
            name = self.name()
            if name in funcs:
                raise syntax_error(
                    f"Bleh function {name!r} is defined twice", "merge its branches"
                )
            branches = []
            while self.peek() == ":":
                self.take()
                branches.append(self.branch())
            self.take(";")
            funcs[name] = tuple(branches)
        return funcs

    def imports(self) -> None:
        self.take("^")
        while self.peek() == ":":
            self.take()
            path = [self.name()]
            while self.peek() == "::":
                self.take()
                path.append(self.name())
            if path != ["std", "io"]:
                raise syntax_error(
                    f"Bleh module {'::'.join(path)!r} is unavailable",
                    "import std::io; a single source has no other modules",
                )
            alias = path[-1]
            if self.peek() == "=":
                self.take()
                alias = self.name()
            self.aliases[alias] = "io"
        self.take(";")

    def branch(self) -> _Branch:
        patterns = self.patterns("=")
        self.take("=")
        return patterns, self.expr()

    def patterns(self, end: str) -> tuple[_Pattern, ...]:
        pending: list[tuple[str | None, list[_Pattern], str]] = []
        out: list[_Pattern] = []
        while True:
            if self.peek() == end:
                if sum(isinstance(p, _PRest) for p in out) > 1:
                    raise syntax_error(
                        "two .. patterns at one Bleh pattern level are ambiguous",
                        "keep at most one .. a level",
                    )
                result = tuple(out)
                if not pending:
                    return result
                self.pos += 1
                name, out, end = pending.pop()
                out.append(_PSplit(name, result))
            else:
                pattern = self.pattern()
                if pattern is None or isinstance(pattern, str):
                    if len(pending) == self.depth_limit:
                        raise self._nesting_error()
                    pending.append((pattern, out, end))
                    out = []
                    end = "]"
                    continue
                out.append(pattern)
            if self.peek() != end:
                self.take(",")

    def pattern(self) -> _Pattern | str | None:
        """Read a leaf or the optional name on an open split pattern."""
        token = self.take()
        if token == "..":
            return _PRest(None)
        if token == "[":
            return None
        if token[0] in "\"'":
            return _PLit(_string(token))
        if _is_bits(token):
            return _PLit(token)
        if token == "_":
            return _PAny()
        self.pos -= 1
        name = self.name()
        if self.peek() == "..":
            self.take()
            return _PRest(name)
        if self.peek() == "[":
            self.take()
            return name
        return _PVar(name)

    def _starts_expr(self) -> bool:
        token = self.peek()
        return token is not None and (
            token[0] in "[{\"'" or _NAME.match(token, 0, 1) is not None
        )

    def expr(self) -> _Expr:
        head = self._expr_head()
        if not isinstance(head, tuple):
            return head
        pending: list[tuple[str | None, str, list[_Expr]]] = [(*head, [])]
        value: _Expr | None = None
        while True:
            if value is None:
                closing, func, children = pending[-1]
                if closing is not None and self.peek() == closing:
                    pending.pop()
                    self.pos += 1
                    value = self._group(closing, func, tuple(children))
                else:
                    head = self._expr_head()
                    if isinstance(head, tuple):
                        if len(pending) == self.depth_limit:
                            raise self._nesting_error()
                        pending.append((*head, []))
                        continue
                    value = head
            if not pending:
                return value
            close, func, children = pending[-1]
            if close is None:
                pending.pop()
                value = _Call(func, (value,))
            else:
                children.append(value)
                if self.peek() == close:
                    pending.pop()
                    self.pos += 1
                    value = self._group(close, func, tuple(children))
                else:
                    self.take(";" if close == "}" else ",")
                    value = None

    @staticmethod
    def _group(close: str, func: str, children: tuple[_Expr, ...]) -> _Expr:
        if close == "]":
            return _Join(children)
        if close == "}":
            if not children:
                raise syntax_error("Bleh {} needs an expression", "write {a; b}")
            return _Seq(children)
        return _Call(func, children)

    def _expr_head(self) -> _Expr | tuple[str | None, str]:
        """Read a leaf or return the closer and function for an open group."""
        token = self.take()
        if token == "[":
            return "]", ""
        if token == "{":
            return "}", ""
        if token[0] in "\"'":
            return _Bits(_string(token))
        if _is_bits(token):
            return _Bits(token)
        self.pos -= 1
        func = self.name()
        qualified = self.peek() == "::"
        if qualified:
            self.take()
            func = f"{func}::{self.name()}"
        if self.peek() == "(":
            self.take()
            return ")", func
        if self._starts_expr():
            return None, func
        if qualified:
            raise syntax_error(
                f"Bleh {func} is a function, not a variable", f"call it: {func}()"
            )
        return _Ref(func)


def _pattern_names(patterns: tuple[_Pattern, ...]) -> set[str]:
    names: set[str] = set()
    pending = list(patterns)
    while pending:
        p = pending.pop()
        if isinstance(p, (_PVar, _PRest, _PSplit)) and p.name:
            names.add(p.name)
        if isinstance(p, _PSplit):
            pending.extend(p.subs)
    return names


def _resolve(
    expr: _Expr, bound: set[str], funcs: Mapping[str, object], aliases: dict[str, str]
) -> _Expr:
    """Return ``expr`` with builtins resolved; check names and variables."""
    pending: list[tuple[_Join | _Seq | _Call, Iterator[_Expr], list[_Expr]]] = []
    node = expr
    while True:
        if isinstance(node, _Ref):
            if node.name not in bound:
                raise syntax_error(
                    f"Bleh variable {node.name!r} is not bound by its branch",
                    "bind it in a pattern, or call a function with ()",
                )
            value: _Expr = node
        elif isinstance(node, (_Bits, _Slot)):
            value = node
        else:
            children = _children(node)
            if children:
                siblings = iter(children)
                pending.append((node, siblings, []))
                node = next(siblings)
                continue
            value = _resolve_group(node, (), funcs, aliases)
        while pending:
            parent, siblings, parts = pending[-1]
            parts.append(value)
            child = next(siblings, None)
            if child is not None:
                node = child
                break
            pending.pop()
            value = _resolve_group(parent, tuple(parts), funcs, aliases)
        else:
            return value


def _resolve_group(
    expr: _Join | _Seq | _Call,
    parts: tuple[_Expr, ...],
    funcs: Mapping[str, object],
    aliases: dict[str, str],
) -> _Expr:
    if isinstance(expr, _Join):
        return _Join(parts)
    if isinstance(expr, _Seq):
        return _Seq(parts)
    module, _, name = expr.func.rpartition("::")
    if module:
        if aliases.get(module) != "io" or name not in _BUILTINS:
            raise syntax_error(
                f"Bleh has no function {expr.func!r}", "import std::io for io::print"
            )
        return _Call(f"io.{name}", parts)
    if name not in funcs:
        raise syntax_error(f"Bleh has no function {name!r}", "define it")
    return _Call(name, parts)


def _children(expr: _Expr) -> tuple[_Expr, ...]:
    if isinstance(expr, (_Join, _Seq)):
        return expr.parts
    assert isinstance(expr, _Call)
    return expr.args


def _parse(code: str) -> dict[str, tuple[_Branch, ...]]:
    parser = _Parser(code)
    if parser.peek() is None:
        raise syntax_error("a Bleh program needs a main function", "write main := ...;")
    funcs = parser.program()
    if "main" not in funcs:
        raise syntax_error("a Bleh program needs a main function", "write main := ...;")
    return {
        name: tuple(
            (patterns, _resolve(body, _pattern_names(patterns), funcs, parser.aliases))
            for patterns, body in branches
        )
        for name, branches in funcs.items()
    }


def _prepare_source(code: str) -> _Funcs:
    return MappingProxyType(_parse(code))
