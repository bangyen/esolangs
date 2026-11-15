r"""Interpreter for Bleh.

Ashli Katt's 2024 lazy functional language over bitstrings.  A program is
functions, each a name, branches ``: patterns = expression`` and ``;``; the
run calls ``main`` with no arguments and ends when it returns.  A call tries
its function's branches in order and evaluates the first whose patterns all
match the arguments; none matching crashes.

Commands:
    Expressions: ``1011`` bits; ``"s"`` or ``'s'`` the UTF-8 bits of ``s``;
    ``x`` a variable; ``[a, b]`` concatenation; ``{a; b}`` each in turn,
    giving the last; ``f(a, b)`` a call, ``f a`` the call ``f(a)``.
    Patterns: a literal matches equal bits; ``_`` anything; ``x`` binds, or
    when bound matches its value; ``x[p, ...]`` and ``[p, ...]`` match the
    bits one each, binding the whole to ``x``; ``x..`` and ``..`` match any
    run (of arguments at the top, of bits inside brackets), at most one a
    level.
    ``^: std::io;`` imports ``io``; ``^: std::io = name;`` renames it.
    ``//`` and ``/* */`` are comments; ``::`` before a function is ignored.

Input/output:
    ``io::print`` writes its arguments' bits as UTF-8, ``io::debug`` as
    ``0``/``1`` characters or ``[]``; both return the empty bitstring.
    ``io::next()`` returns the next character's UTF-8 bits, empty at EOF;
    ``io::hasNext()`` returns ``1`` while a character is left, else ``0``.

Errors:
    ProgramError: a token or construct outside the grammar, a call to an
    undefined function, an unbound variable, a second function of one name,
    an import other than ``std::io``, and a program with no ``main``.
    HaltError: a call no branch matches, ``io::print`` of bits that are not
    UTF-8 bytes, and ``io::next`` or ``io::hasNext`` given an argument.

Decisions:
    * Call by need: an argument is evaluated once, when first forced, which
      is when a literal, bracket or repeated-variable pattern inspects it;
      ``_``, ``..`` and a first ``x`` bind without forcing, so the page's
      ``AND`` and ``OR`` short-circuit.  ``x..`` binds lazily too.
    * ``{a; b}`` forces each element in order, as statements; a block
      passed as an argument runs only if the argument is forced.
    * A string escape is one of ``\n \t \r \0 \\ \" \'``.
    * A qualified name with no argument (``io::next``) is refused: it is no
      variable, and the page writes every zero-argument call with ``()``.
    * Modules other than ``std::io`` are refused: one source has no other
      files to import.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, fields
from itertools import chain
from reprlib import recursive_repr
from types import MappingProxyType
from typing import Any, NamedTuple, cast

from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.languages.bleh.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import (
    WorkspaceModel,
    WorkspaceSnapshot,
    WorkspaceVariant,
    repr_snapshot_record,
)
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error


class _RecursiveRecord:
    """Share the workspace display budget with nested syntax and values."""

    __slots__ = ()

    @recursive_repr()
    def __repr__(self) -> str:
        return repr_snapshot_record(self, fields(cast("Any", self)))


@dataclass(frozen=True, slots=True)
class _Bits:
    value: str


@dataclass(frozen=True, slots=True)
class _Ref:
    name: str


@dataclass(frozen=True, slots=True, repr=False)
class _Join(_RecursiveRecord):
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Seq(_RecursiveRecord):
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Call(_RecursiveRecord):
    #: A function's name, or ``io.<builtin>``.
    func: str
    args: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True)
class _Slot:
    """A bound value in an expression's place: a lazy join's part."""

    val: _Val


class _LazyHashStorage(_RecursiveRecord):
    # Pickle and worker records carry only dataclass fields. A hash of strings
    # must be computed afresh in the process that reads them.
    __slots__ = ("_hash",)

    _hash: int


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class _Lazy(_LazyHashStorage):
    """An unforced ``x..`` binding: the arguments it spans, joined."""

    parts: tuple[_Val, ...]

    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._cache_hashes()
            return self._hash

    def _cache_hashes(self) -> None:
        """Cache each shared node before its parents ask for their hash."""
        pending = [(self, False)]
        while pending:
            node, ready = pending.pop()
            if hasattr(node, "_hash"):
                continue
            if ready:
                object.__setattr__(node, "_hash", hash((node.parts,)))
            else:
                pending.append((node, True))
                pending.extend(
                    (part, False) for part in node.parts if isinstance(part, _Lazy)
                )

    def __eq__(self, other: object) -> bool:
        """Compare content independently of how either argument shares its parts."""
        if not isinstance(other, _Lazy) or type(self) is not type(other):
            return NotImplemented
        pending: list[tuple[_Val, _Val]] = [(self, other)]
        seen: set[tuple[int, int]] = set()
        while pending:
            left, right = pending.pop()
            if left is right:
                continue
            if isinstance(left, _Lazy) and isinstance(right, _Lazy):
                if type(left) is not type(right) or len(left.parts) != len(right.parts):
                    return False
                pair = id(left), id(right)
                if pair not in seen:
                    seen.add(pair)
                    pending.extend(
                        zip(reversed(left.parts), reversed(right.parts), strict=True)
                    )
            elif left == right:
                continue
            else:
                return False
        return True


type _Expr = _Bits | _Ref | _Join | _Seq | _Call | _Slot
#: A bound value: a heap address, known bits, or a lazy join.
type _Val = int | str | _Lazy


@dataclass(frozen=True, slots=True)
class _PLit:
    value: str


@dataclass(frozen=True, slots=True)
class _PAny:
    pass


@dataclass(frozen=True, slots=True)
class _PVar:
    name: str


@dataclass(frozen=True, slots=True)
class _PRest:
    name: str | None


@dataclass(frozen=True, slots=True, repr=False)
class _PSplit(_RecursiveRecord):
    name: str | None
    subs: tuple[_Pattern, ...]


type _Pattern = _PLit | _PAny | _PVar | _PRest | _PSplit
#: One branch: its patterns and its expression.
type _Branch = tuple[tuple[_Pattern, ...], _Expr]
type _Funcs = Mapping[str, tuple[_Branch, ...]]

_BUILTINS = ("print", "debug", "next", "hasNext")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}
_TOKEN = re.compile(
    r"""\s+|//[^\n]*|/\*.*?\*/|(::|\.\.|[:=;,()\[\]{}^])|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\w+)|(.)""",
    re.DOTALL | re.ASCII,
)
_NAME = re.compile(r"\w+", re.ASCII)


def _utf8_bits(text: str) -> str:
    return "".join(format(byte, "08b") for byte in text.encode())


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


class _Need(Exception):  # noqa: N818 - a request, not an error
    """Matching needs the heap address ``at`` forced first."""

    def __init__(self, at: int) -> None:
        self.at = at


#: A branch's bindings, in binding order.
type _Env = tuple[tuple[str, _Val], ...]
#: A heap cell: bits once forced, else the expression and its bindings.
type _Cell = str | tuple[_Expr, _Env]
type _Heap = Mapping[int, _Cell]


def _lookup(env: _Env, name: str) -> _Val:
    return next(value for key, value in env if key == name)


def _value(val: _Val, heap: _Heap) -> str:
    """Return ``val``'s bits, raising :class:`_Need` for an unforced address."""
    if isinstance(val, str):
        return val
    if isinstance(val, _Lazy):
        pending = list(reversed(val.parts))
        bits = []
        while pending:
            part = pending.pop()
            if isinstance(part, _Lazy):
                pending.extend(reversed(part.parts))
            else:
                bits.append(_value(part, heap))
        return "".join(bits)
    cell = heap[val]
    if isinstance(cell, str):
        return cell
    raise _Need(val)


def _align[T](
    patterns: tuple[_Pattern, ...], items: tuple[T, ...]
) -> (
    tuple[
        list[tuple[_Pattern, T]], _PRest | None, tuple[T, ...], list[tuple[_Pattern, T]]
    ]
    | None
):
    """Pair patterns with items around the one rest pattern and its run."""
    rest = next((i for i, p in enumerate(patterns) if isinstance(p, _PRest)), None)
    if rest is None:
        if len(patterns) != len(items):
            return None
        return list(zip(patterns, items, strict=True)), None, (), []
    tail = len(patterns) - rest - 1
    if len(items) < rest + tail:
        return None
    cut = len(items) - tail
    rest_pattern = patterns[rest]
    assert isinstance(rest_pattern, _PRest)
    return (
        list(zip(patterns[:rest], items[:rest], strict=True)),
        rest_pattern,
        items[rest:cut],
        list(zip(patterns[rest + 1 :], items[cut:], strict=True)),
    )


def _match_items[T: _Val](
    patterns: tuple[_Pattern, ...],
    items: tuple[T, ...],
    run: Callable[[tuple[T, ...]], _Val],
) -> Iterator[tuple[_Pattern, _Val]] | None:
    aligned = _align(patterns, items)
    if aligned is None:
        return None
    head, rest, span, tail = aligned
    if rest is None:
        return iter(head)
    if rest.name is None:
        return chain(head, tail)

    def bind(name: str) -> Iterator[tuple[_Pattern, _Val]]:
        yield _PVar(name), run(span)

    return chain(head, bind(rest.name), tail)


class _Matcher:
    """One branch's match, left to right, forcing values only on demand."""

    def __init__(self, heap: _Heap) -> None:
        self.heap = heap
        self.bound: dict[str, _Val] = {}

    def bind(self, name: str, val: _Val) -> bool:
        if name not in self.bound:
            self.bound[name] = val
            return True
        return _value(self.bound[name], self.heap) == _value(val, self.heap)

    def matches(self, patterns: tuple[_Pattern, ...], items: tuple[_Val, ...]) -> bool:
        root = _match_items(patterns, items, _Lazy)
        if root is None:
            return False
        levels = [root]
        while levels:
            for pattern, val in levels[-1]:
                if isinstance(pattern, _PAny):
                    continue
                if isinstance(pattern, _PVar):
                    if not self.bind(pattern.name, val):
                        return False
                    continue
                bits = _value(val, self.heap)
                if isinstance(pattern, _PLit):
                    if bits != pattern.value:
                        return False
                    continue
                assert isinstance(pattern, _PSplit)
                if pattern.name and not self.bind(pattern.name, bits):
                    return False
                sub = _match_items(pattern.subs, tuple(bits), "".join)
                if sub is None:
                    return False
                levels.append(sub)
                break
            else:
                levels.pop()
        return True


def _match(
    patterns: tuple[_Pattern, ...], args: tuple[_Val, ...], heap: _Heap
) -> _Env | None:
    """Return the branch's bindings, None on a mismatch; may raise _Need."""
    if not patterns:
        return None if args else ()
    matcher = _Matcher(heap)
    if not matcher.matches(patterns, args):
        return None
    return tuple(matcher.bound.items())


@dataclass(frozen=True, slots=True)
class _Eval:
    expr: _Expr
    env: _Env


@dataclass(frozen=True, slots=True)
class _Ret:
    value: str


@dataclass(frozen=True, slots=True, repr=False)
class _Try(_RecursiveRecord):
    """Match ``func``'s branch ``branch``; as a frame, retry it."""

    func: str
    args: tuple[_Val, ...]
    branch: int


@dataclass(frozen=True, slots=True)
class _Do:
    """Run a builtin: the shell's job, since it is IO."""

    builtin: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Update:
    at: int


@dataclass(frozen=True, slots=True)
class _Part:
    """Part ``at`` of a join or block is running; ``acc`` is the join so far."""

    expr: _Join | _Seq
    at: int
    env: _Env
    acc: str


@dataclass(frozen=True, slots=True)
class _Arg:
    """Argument ``at`` of a builtin is running; ``values`` precede it."""

    builtin: str
    args: tuple[_Expr, ...]
    at: int
    env: _Env
    values: tuple[str, ...]


type _Control = _Eval | _Ret | _Try | _Do
type _Frame = _Update | _Part | _Arg | _Try
#: Continuation frames, innermost first.
type _Kont = tuple[_Frame, _Kont] | None
#: Heap writes a transition makes: addresses and their new cells.
type _Writes = tuple[tuple[int, _Cell], ...]


class _State(NamedTuple):
    control: _Control
    kont: _Kont
    #: The next free heap address.
    fresh: int


def _force(at: int, heap: _Heap, kont: _Kont, fresh: int) -> _State:
    cell = heap[at]
    if isinstance(cell, str):
        return tuple.__new__(_State, (_Ret(cell), kont, fresh))
    expr, env = cell
    return tuple.__new__(_State, (_Eval(expr, env), (_Update(at), kont), fresh))


def _advance(state: _State, heap: _Heap, funcs: _Funcs) -> tuple[_State, _Writes]:
    """Return the state after one transition, and the heap writes it makes.

    Pure: ``heap`` is read, never written; a builtin is the shell's.
    """
    control, kont, fresh = state
    if isinstance(control, _Eval):
        return _eval(control.expr, control.env, heap, kont, fresh)
    if isinstance(control, _Ret):
        assert kont is not None
        if isinstance(kont[0], _Update):
            # A forced thunk keeps its bits: call by need.
            return tuple.__new__(_State, (control, kont[1], fresh)), (
                (kont[0].at, control.value),
            )
        return _return(control.value, kont, fresh), ()
    assert isinstance(control, _Try)
    branches = funcs[control.func]
    patterns, body = branches[control.branch]
    try:
        env = _match(patterns, control.args, heap)
    except _Need as need:
        return _force(need.at, heap, (control, kont), fresh), ()
    if env is not None:
        return tuple.__new__(_State, (_Eval(body, env), kont, fresh)), ()
    if control.branch + 1 == len(branches):
        raise HaltError(f"no branch of Bleh function {control.func} matches")
    retry = _Try(control.func, control.args, control.branch + 1)
    return tuple.__new__(_State, (retry, kont, fresh)), ()


def _eval(
    expr: _Expr, env: _Env, heap: _Heap, kont: _Kont, fresh: int
) -> tuple[_State, _Writes]:
    if isinstance(expr, _Ref):
        expr = _Slot(_lookup(env, expr.name))
    if isinstance(expr, _Slot):
        val = expr.val
        if isinstance(val, int):
            return _force(val, heap, kont, fresh), ()
        if isinstance(val, str):
            return tuple.__new__(_State, (_Ret(val), kont, fresh)), ()
        expr = _Join(tuple(_Slot(part) for part in val.parts))
    if isinstance(expr, _Bits):
        return tuple.__new__(_State, (_Ret(expr.value), kont, fresh)), ()
    if isinstance(expr, (_Join, _Seq)):
        if not expr.parts:
            return tuple.__new__(_State, (_Ret(""), kont, fresh)), ()
        return _part(expr, 0, env, "", kont, fresh), ()
    if expr.func.startswith("io."):
        builtin = expr.func[3:]
        if not expr.args:
            return tuple.__new__(_State, (_Do(builtin, ()), kont, fresh)), ()
        frame = _Arg(builtin, expr.args, 0, env, ())
        return tuple.__new__(
            _State, (_Eval(expr.args[0], env), (frame, kont), fresh)
        ), ()
    args: list[_Val] = []
    writes: list[tuple[int, _Cell]] = []
    for arg in expr.args:
        if isinstance(arg, _Bits):
            args.append(arg.value)
        elif isinstance(arg, (_Ref, _Slot)):
            # A variable passes its binding on: the callee shares the thunk.
            args.append(_lookup(env, arg.name) if isinstance(arg, _Ref) else arg.val)
        else:
            writes.append((fresh, (arg, env)))
            args.append(fresh)
            fresh += 1
    return tuple.__new__(_State, (_Try(expr.func, tuple(args), 0), kont, fresh)), tuple(
        writes
    )


def _part(
    expr: _Join | _Seq, at: int, env: _Env, acc: str, kont: _Kont, fresh: int
) -> _State:
    """Start part ``at`` of a join or block; a block's last runs as a tail."""
    if isinstance(expr, _Seq) and at == len(expr.parts) - 1:
        return tuple.__new__(_State, (_Eval(expr.parts[at], env), kont, fresh))
    frame = _Part(expr, at, env, acc)
    return tuple.__new__(_State, (_Eval(expr.parts[at], env), (frame, kont), fresh))


def _return(value: str, kont: _Kont, fresh: int) -> _State:
    assert kont is not None
    frame, rest = kont
    if isinstance(frame, _Part):
        acc = frame.acc + value if isinstance(frame.expr, _Join) else ""
        if frame.at + 1 == len(frame.expr.parts):
            return tuple.__new__(_State, (_Ret(acc), rest, fresh))
        return _part(frame.expr, frame.at + 1, frame.env, acc, rest, fresh)
    if isinstance(frame, _Arg):
        values = (*frame.values, value)
        if frame.at + 1 == len(frame.args):
            return tuple.__new__(_State, (_Do(frame.builtin, values), rest, fresh))
        nxt = _Arg(frame.builtin, frame.args, frame.at + 1, frame.env, values)
        return tuple.__new__(
            _State, (_Eval(frame.args[frame.at + 1], frame.env), (nxt, rest), fresh)
        )
    assert isinstance(frame, _Try)  # ``_advance`` pops updates itself
    return tuple.__new__(_State, (frame, rest, fresh))  # retry the branch


_WORKSPACE_MODEL = WorkspaceModel(
    "bleh-v1", ("control", "continuation", "fresh", "heap", "lookahead", "input_cursor")
)


def _prepare_source(code: str) -> _Funcs:
    return MappingProxyType(_parse(code))


class _Machine:
    """The functions, the control and continuation, the heap, and lookahead."""

    #: A frame stack, not a place in the source; ``ip`` is its depth.
    ip_shape = "opaque"
    #: ``io::next()`` past EOF is the empty bitstring, not a raise.
    eof_is_a_value = True

    def __init__(self, code: str | _Funcs, io: IO) -> None:
        self.io = io
        self._writer = _BufferedOutput()
        self.funcs = _prepare_source(code) if isinstance(code, str) else code
        self.state = tuple.__new__(_State, (_Try("main", (), 0), None, 0))
        self.heap: dict[int, _Cell] = {}
        #: A character awaiting ``io::next``, ``""`` past EOF, or None.
        self.ahead: str | None = None

    @property
    def halted(self) -> bool:
        return self.state.kont is None and isinstance(self.state.control, _Ret)

    @property
    def ip(self) -> tuple[int, ...]:
        """The continuation's depth."""
        depth, kont = 0, self.state.kont
        while kont is not None:
            depth, kont = depth + 1, kont[1]
        return (depth,)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        continuation = []
        rest = self.state.kont
        while rest is not None:
            frame, rest = rest
            continuation.append(frame)
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            control=(
                WorkspaceVariant("pending_output", (self.state.control, accepted))
                if accepted
                else self.state.control
            ),
            continuation=tuple(continuation),
            fresh=self.state.fresh,
            heap=frozenset(self.heap.items()),
            lookahead=self.ahead,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = (
            *self.state,
            frozenset(self.heap.items()),
            self.ahead,
            self.io.progress(),
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def _read_char(self) -> str:
        """Return the next input character, or ``""`` at EOF."""
        try:
            return chr(self.io.input_char())
        except EOFError:
            return ""

    def _builtin(self, name: str, values: tuple[str, ...]) -> str:
        bits = "".join(values)
        if name in ("next", "hasNext") and values:
            raise HaltError(f"Bleh io::{name} takes no arguments")
        if name == "print":
            data = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
            try:
                if len(bits) % 8:
                    raise ValueError(len(bits))
                text = data.decode()
            except ValueError as exc:
                raise HaltError(f"Bleh io::print got non-UTF-8 bits {bits}") from exc
            self._writer.write(self.io, text)
        elif name == "debug":
            self._writer.write(self.io, bits or "[]")
        else:
            if self.ahead is None:
                self.ahead = self._read_char()
            if name == "next":
                result = _utf8_bits(self.ahead)
                if self.ahead:
                    self.ahead = None
                return result
            return "1" if self.ahead else "0"
        return ""

    def step(self) -> None:
        if self.halted:
            return
        control = self.state.control
        if isinstance(control, _Do):
            value = self._builtin(control.builtin, control.values)
            self.state = self.state._replace(control=_Ret(value))
            return
        self.state, writes = _advance(self.state, self.heap, self.funcs)
        self.heap.update(writes)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse source once and build fresh state for each run."""
    if not isinstance(source, str):
        raise TypeError("bleh machines require text source")
    if options:
        raise TypeError("bleh machines accept no runtime options")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Funcs, io: IO) -> CompletionReport:
    """Run a Bleh program from its ``main``."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Bleh program from its ``main``."""
    _execute(code, io)


SNAPSHOT_RECORDS = (
    _Bits,
    _Ref,
    _Join,
    _Seq,
    _Call,
    _Slot,
    _Lazy,
    _PLit,
    _PAny,
    _PVar,
    _PRest,
    _PSplit,
    _Eval,
    _Ret,
    _Try,
    _Do,
    _Update,
    _Part,
    _Arg,
)


if __name__ == "__main__":
    script_main(run)
