r"""Interpreter for DINAC."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_KEYWORDS = frozenset(("DEF", "ELSE", "GIVE", "IF", "IN", "OUT", "SET", "WHILE"))
# Named because a bare "'".
_QUOTE = "'"
_HEX = "0123456789ABCDEF"
_ESCAPES = {"0": "\0", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
_INDENT = 4

_Kind = Literal["wubyte", "aschar", "snuval"]


@dataclass(frozen=True)
class _Value:
    r"""A DINAC value: its type tag and its integer code (0 for a snuval)."""

    kind: _Kind
    code: int = 0

    def truthy(self) -> bool:
        r"""Return the truth value: a snuval is always false, else nonzero."""
        return self.kind != "snuval" and self.code != 0

    def render(self) -> str:
        r"""Render for ``OUT``: a wubyte as two hex digits, an aschar as itself."""
        if self.kind == "wubyte":
            return f"{self.code:02X}"
        if self.kind == "aschar":
            return chr(self.code)
        return "$"


_SNUVAL = _Value("snuval")


# -- expressions.

# Discriminated by the first.
_Lit = tuple[Literal["lit"], _Value]
_Name = tuple[Literal["name"], str]
_Not = tuple[Literal["not"], "_Expr"]
_Step = tuple[Literal["step"], str, "_Expr"]  # postfix + / -.
_Cmp = tuple[Literal["cmp"], str, "_Expr", "_Expr"]  # = / .
_Call = tuple[Literal["call"], str, tuple["_Expr", ...]]
_Expr = _Lit | _Name | _Not | _Step | _Cmp | _Call


def _parse_literal(text: str) -> _Value | None:
    r"""Return the value of a whole-token literal, or None if it is not one."""
    if text == "$":
        return _SNUVAL
    if len(text) == 2 and text[0] in _HEX and text[1] in _HEX:
        return _Value("wubyte", int(text, 16))
    if text.startswith("'"):
        return _parse_aschar(text[1:])
    # A bare escape: the wiki's.
    # examples write ``SET c:\0``,.
    # examples are ground truth, so.
    if text.startswith("\\"):
        return _parse_aschar(text)
    return None


def _parse_aschar(body: str) -> _Value | None:
    r"""Return the aschar named by ``body`` (a char or a 2-char escape)."""
    if body.startswith("\\") and len(body) == 2:
        escape = _ESCAPES.get(body[1])
        return None if escape is None else _Value("aschar", ord(escape))
    if len(body) == 1 and ord(body) < 128:
        return _Value("aschar", ord(body))
    return None


def _is_name(text: str) -> bool:
    r"""Whether ``text`` matches the identifier regex ``[a-z][A-Za-z0-9]*``."""
    return bool(text) and text[0].islower() and text[0].isalpha() and text.isalnum()


class _Reader:
    r"""A cursor over one statement's text, used by the expression parser."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def done(self) -> bool:
        self.skip()
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""


def _parse_expr(reader: _Reader) -> _Expr:
    r"""Parse one expression: a comparison, the loosest binding form."""
    return _parse_compare(reader)


def _parse_compare(reader: _Reader) -> _Expr:
    r"""Parse ``a = b`` / ``a ."""
    left = _parse_unary(reader)
    reader.skip()
    if reader.peek() in ("=", "!"):
        op = reader.peek()
        reader.pos += 1
        return ("cmp", op, left, _parse_unary(reader))
    return left


def _parse_unary(reader: _Reader) -> _Expr:
    r"""Parse ``~``-prefixed operands, which stack (the wiki's ``~~b``)."""
    reader.skip()
    if reader.peek() == "~":
        reader.pos += 1
        return ("not", _parse_unary(reader))
    return _parse_postfix(reader)


def _parse_postfix(reader: _Reader) -> _Expr:
    r"""Parse a primary followed by any run of ``+``/``-`` successors."""
    expr = _parse_primary(reader)
    while reader.peek() in ("+", "-"):
        expr = ("step", reader.peek(), expr)
        reader.pos += 1
    return expr


def _parse_primary(reader: _Reader) -> _Expr:
    r"""Parse a parenthesized group, a call, a name, or a literal."""
    reader.skip()
    if reader.peek() == "(":
        reader.pos += 1
        inner = _parse_expr(reader)
        reader.skip()
        if reader.peek() != ")":
            raise ValueError("unclosed parenthesis")
        reader.pos += 1
        return inner
    start = reader.pos
    while reader.pos < len(reader.text) and reader.text[reader.pos] not in " ()~=!,+-":
        reader.pos += 1
    token = reader.text[start : reader.pos]
    if not token:
        # An aschar literal may *be*.
        # ``'+``), so a quote is.
        raise ValueError(f"expected a value at position {start}")
    # A lone quote means the.
    # delimiters the scan above.
    # is taken raw here rather than.
    if len(token) == 1 and token == _QUOTE:
        if reader.pos < len(reader.text):
            char = reader.text[reader.pos]
            reader.pos += 1
            value = _parse_aschar(char)
            # The scan above stops only on.
            # those is a legal aschar, so.
            if value is not None:  # pragma: no branch
                return ("lit", value)
        raise ValueError("malformed aschar literal")
    if reader.peek() == "(":
        if not _is_name(token):
            raise ValueError(f"{token!r} is not a valid function name")
        return ("call", token, _parse_args(reader))
    literal = _parse_literal(token)
    if literal is not None:
        return ("lit", literal)
    if _is_name(token) and token not in _KEYWORDS:
        return ("name", token)
    raise ValueError(f"malformed value {token!r}")


def _parse_args(reader: _Reader) -> tuple[_Expr, ...]:
    r"""Parse a call's parenthesized, comma-separated argument list."""
    reader.pos += 1  # the "(".
    args: list[_Expr] = []
    reader.skip()
    if reader.peek() == ")":
        reader.pos += 1
        return ()
    while True:
        args.append(_parse_expr(reader))
        reader.skip()
        if reader.peek() == ",":
            reader.pos += 1
            continue
        if reader.peek() == ")":
            reader.pos += 1
            return tuple(args)
        raise ValueError("malformed argument list")


def _parse_whole(text: str) -> _Expr:
    r"""Parse ``text`` as a complete expression, rejecting a trailing tail."""
    reader = _Reader(text)
    expr = _parse_expr(reader)
    if not reader.done():
        raise ValueError(f"trailing text in expression {text!r}")
    return expr


# -- statements.

_Out = tuple[Literal["out"], _Expr]
_In = tuple[Literal["in"], str]
_Set = tuple[Literal["set"], str, _Expr]
_Assign = tuple[Literal["assign"], str, _Expr]
_Give = tuple[Literal["give"], _Expr]
_CallStmt = tuple[Literal["callstmt"], _Expr]
_If = tuple[Literal["if"], _Expr, tuple["_Stmt", ...], tuple["_Stmt", ...]]
_While = tuple[Literal["while"], _Expr, tuple["_Stmt", ...]]
_Stmt = _Out | _In | _Set | _Assign | _Give | _CallStmt | _If | _While

# : Where each statement kind.
# : absent because it has none.
_EXPR_SLOT = {
    "out": 1,
    "give": 1,
    "callstmt": 1,
    "if": 1,
    "while": 1,
    "set": 2,
    "assign": 2,
}


@dataclass(frozen=True)
class _Function:
    r"""One overload: its return type, parameter names/types, and body."""

    name: str
    returns: _Kind
    params: tuple[tuple[str, _Kind], ...]
    body: tuple[_Stmt, ...]

    @property
    def signature(self) -> tuple[str, tuple[_Kind, ...]]:
        r"""The overload key: the name plus the parameter *types*."""
        return (self.name, tuple(kind for _, kind in self.params))


def _strip_comment(line: str) -> str:
    r"""Remove a ``#`` comment, respecting an aschar literal."""
    out = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "#":
            break
        out.append(char)
        if char == "'" and i + 1 < len(line):
            # The quoted character is taken.
            nxt = line[i + 1]
            out.append(nxt)
            i += 2
            if nxt == "\\" and i < len(line):
                out.append(line[i])
                i += 1
            continue
        i += 1
    return "".join(out)


def _indent_of(line: str) -> int:
    r"""Return a line's indent level, rejecting a non-multiple of four."""
    spaces = len(line) - len(line.lstrip(" "))
    if spaces % _INDENT:
        raise ValueError(f"indent of {spaces} spaces is not a multiple of {_INDENT}")
    return spaces // _INDENT


def _split_lines(code: str) -> list[tuple[int, str]]:
    r"""Return ``(level, text)`` for every non-blank, non-comment line."""
    result = []
    for raw in code.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        result.append((_indent_of(line), line.lstrip(" ")))
    return result


def _parse_typed(token: str) -> _Kind:
    r"""Return the type a ``DEF/<v>`` or a parameter's sample value names."""
    value = _parse_literal(token)
    if value is None:
        raise ValueError(f"{token!r} does not name a type")
    return value.kind


class _Parser:
    r"""Folds the indented lines into functions and a top-level body."""

    def __init__(self, lines: list[tuple[int, str]]) -> None:
        self.lines = lines
        self.pos = 0
        self.functions: dict[tuple[str, tuple[_Kind, ...]], _Function] = {}

    def parse(self) -> tuple[_Stmt, ...]:
        r"""Parse the whole program, returning its top-level body."""
        top: list[_Stmt] = []
        while self.pos < len(self.lines):
            level, text = self.lines[self.pos]
            if level != 0:
                raise ValueError(f"unexpected indent before {text!r}")
            if text.startswith("DEF"):
                self._parse_def()
            else:
                top.append(self._parse_statement(0))
        return tuple(top)

    def _block(self, level: int, owner: str) -> tuple[_Stmt, ...]:
        r"""Parse the statements indented one level below ``level``."""
        body: list[_Stmt] = []
        while self.pos < len(self.lines):
            here, text = self.lines[self.pos]
            if here <= level:
                break
            if here != level + 1:
                raise ValueError(f"indent jumps to {here} before {text!r}")
            body.append(self._parse_statement(here))
        if not body:
            raise ValueError(f"{owner} needs an indented body")
        return tuple(body)

    def _parse_def(self) -> None:
        r"""Parse one ``DEF/<type> name p:v ...`` and register the overload."""
        level, text = self.lines[self.pos]
        self.pos += 1
        head, _, rest = text.partition(" ")
        if not head.startswith("DEF/"):
            raise ValueError(f"malformed DEF header {text!r}")
        returns = _parse_typed(head[4:])
        parts = rest.split()
        if not parts or not _is_name(parts[0]) or parts[0] in _KEYWORDS:
            raise ValueError(f"malformed DEF name in {text!r}")
        name = parts[0]
        params: list[tuple[str, _Kind]] = []
        seen: set[str] = set()
        for part in parts[1:]:
            pname, sep, sample = part.partition(":")
            if not sep or not _is_name(pname) or pname in _KEYWORDS or pname in seen:
                raise ValueError(f"malformed parameter {part!r}")
            seen.add(pname)
            params.append((pname, _parse_typed(sample)))
        body = self._block(level, f"DEF {name}")
        # The wiki: a non-snuval.
        # error".
        # refused at parse time; a GIVE.
        # runtime is the HaltError in.
        if returns != "snuval" and not any(s[0] == "give" for s in _walk(body)):
            raise ValueError(f"function {name!r} returns {returns} but never GIVEs")
        function = _Function(name, returns, tuple(params), body)
        if function.signature in self.functions:
            raise ValueError(f"duplicate overload for {name!r}")
        self.functions[function.signature] = function

    def _parse_statement(self, level: int) -> _Stmt:
        r"""Parse the statement at the cursor, consuming any indented body."""
        _, text = self.lines[self.pos]
        self.pos += 1
        if text.startswith("DEF/") or text.startswith("DEF "):
            raise ValueError("a DEF may not be nested")
        if text.startswith("IF "):
            return self._parse_if(level, text)
        if text.startswith("WHILE "):
            condition = _parse_whole(text[6:])
            return ("while", condition, self._block(level, "WHILE"))
        if text.rstrip() == "ELSE":
            raise ValueError("ELSE without a matching IF")
        if text.startswith("OUT "):
            return ("out", _parse_whole(text[4:]))
        if text.startswith("IN "):
            name = text[3:].strip()
            if not _is_name(name) or name in _KEYWORDS:
                raise ValueError(f"IN needs a variable name, got {name!r}")
            return ("in", name)
        if text.startswith("GIVE "):
            return ("give", _parse_whole(text[5:]))
        if text.startswith("SET "):
            name, sep, value = text[4:].partition(":")
            if not sep or not _is_name(name) or name in _KEYWORDS:
                raise ValueError(f"malformed SET in {text!r}")
            return ("set", name, _parse_whole(value))
        head, sep, value = text.partition(" . ")
        if sep and _is_name(head) and head not in _KEYWORDS:
            return ("assign", head, _parse_whole(value))
        # A bare call is a statement of.
        # DEF/$ function, whose value.
        if text.rstrip().endswith(")"):
            expr = _parse_whole(text)
            if expr[0] == "call":
                return ("callstmt", expr)
        raise ValueError(f"malformed statement {text!r}")

    def _parse_if(self, level: int, text: str) -> _If:
        r"""Parse ``IF``, its body, the mandatory ``ELSE``, and that body."""
        condition = _parse_whole(text[3:])
        then = self._block(level, "IF")
        if self.pos >= len(self.lines):
            raise ValueError("IF without its ELSE")
        here, next_text = self.lines[self.pos]
        if here != level or next_text.rstrip() != "ELSE":
            raise ValueError("IF without its ELSE")
        self.pos += 1
        return ("if", condition, then, self._block(level, "ELSE"))


def _walk(body: tuple[_Stmt, ...]) -> list[_Stmt]:
    r"""Return every statement in ``body``, descending into nested blocks."""
    found: list[_Stmt] = []
    for stmt in body:
        found.append(stmt)
        if stmt[0] == "if":
            found.extend(_walk(stmt[2]))
            found.extend(_walk(stmt[3]))
        elif stmt[0] == "while":
            found.extend(_walk(stmt[2]))
    return found


_Overloads = dict[tuple[str, tuple[_Kind, ...]], _Function]


def _parse(code: str) -> tuple[_Overloads, tuple[_Stmt, ...]]:
    r"""Parse a whole program into its overload table and top-level body."""
    parser = _Parser(_split_lines(code))
    top = parser.parse()
    return parser.functions, top


# -- evaluation.


def _step_value(value: _Value, op: str) -> _Value:
    r"""Apply postfix ``+``/``-``, wrapping at 256 (wubyte) or 128 (aschar)."""
    if value.kind == "snuval":
        raise HaltError("cannot apply + or - to a snuval")
    modulus = 256 if value.kind == "wubyte" else 128
    delta = 1 if op == "+" else -1
    return _Value(value.kind, (value.code + delta) % modulus)


def _compare(left: _Value, right: _Value) -> bool:
    r"""Whether two values are equal; different types are never equal."""
    return left.kind == right.kind and left.code == right.code


def _bit(*, flag: bool) -> _Value:
    r"""Return the wubyte ``01``/``00`` a comparison or ``~`` yields."""
    return _Value("wubyte", 1 if flag else 0)


# -- the machine.


@dataclass
class _Frame:
    r"""One executing block: its statements, cursor, and variable scope."""

    body: tuple[_Stmt, ...]
    scope: dict[str, _Value]
    ind: int = 0
    function: _Function | None = None
    pending: _Expr | None = None
    returned: _Value | None = None


# : The whole run state as a.
# : identity, its cursor, and.
# : This is what.
# : is complete -- the overload.
# : parse time, so nothing.
type _Bindings = tuple[tuple[str, str, int], ...]
type _FrameState = tuple[int, int, _Bindings, str, tuple[str, int] | None]
type _State = tuple[tuple[_FrameState, ...], int]


class _Machine:
    r"""One DINAC run: the parsed program, the frame stack, and the ports."""

    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.functions, top = _parse(code)
        self.globals: dict[str, _Value] = {}
        self.frames: list[_Frame] = [_Frame(top, self.globals)]

    @property
    def halted(self) -> bool:
        r"""Whether every frame has run to its end."""
        return not self.frames

    def snapshot(self) -> _State:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Every frame's cursor and.
        # cursor: a lap that consumed a.
        # identified by ``id``, which.
        # block tuple is built once at.
        # .
        # ``pending`` is by *value*: it.
        # so it is freshly built rather.
        # states differing only in how.
        # not the same state.
        return (
            tuple(
                (
                    id(frame.body),
                    frame.ind,
                    tuple(sorted((k, v.kind, v.code) for k, v in frame.scope.items())),
                    repr(frame.pending),
                    None
                    if frame.returned is None
                    else (
                        frame.returned.kind,
                        frame.returned.code,
                    ),
                )
                for frame in self.frames
            ),
            self.io.position(),
        )

    @property
    def ip(self) -> int:
        r"""The innermost frame's statement cursor."""
        return self.frames[-1].ind if self.frames else 0

    @property
    def memory(self) -> list[int]:
        r"""The global scope's values, in declaration order."""
        return [v.code for v in self.globals.values()]

    @property
    def stack(self) -> list[object]:
        r"""The frame stack's depth exposed as the VM's stack view."""
        return [frame.ind for frame in self.frames]

    # -- expression evaluation, the.

    def _eval(self, expr: _Expr, scope: dict[str, _Value]) -> _Value:
        r"""Evaluate an expression in ``scope``, running any calls inline."""
        if expr[0] == "lit":
            return expr[1]
        if expr[0] == "name":
            value = scope.get(expr[1])
            if value is None:
                raise HaltError(f"undeclared name {expr[1]!r}")
            return value
        if expr[0] == "not":
            return _bit(flag=not self._eval(expr[1], scope).truthy())
        if expr[0] == "step":
            return _step_value(self._eval(expr[2], scope), expr[1])
        if expr[0] == "cmp":
            left = self._eval(expr[2], scope)
            right = self._eval(expr[3], scope)
            same = _compare(left, right)
            return _bit(flag=same if expr[1] == "=" else not same)
        # Unreachable: ``step`` pushes.
        # its value in before.
        raise HaltError(  # pragma: no cover - see the comment above
            f"unresolved call to {expr[1]!r}"
        )

    def _resolve(self, function: _Function, values: list[_Value]) -> dict[str, _Value]:
        r"""Bind a call's evaluated arguments to its overload's parameters."""
        # strict: the overload was.
        # two sequences are the same.
        return {
            pname: value
            for (pname, _), value in zip(function.params, values, strict=True)
        }

    def _overload(self, name: str, values: list[_Value]) -> _Function:
        r"""Return the overload ``name`` selects for these argument types."""
        key = (name, tuple(v.kind for v in values))
        function = self.functions.get(key)
        if function is None:
            raise HaltError(f"no overload of {name!r} takes {list(key[1])}")
        return function

    def _checked(self, function: _Function, value: _Value) -> _Value:
        r"""Validate a call's result against the overload's declared type."""
        if function.returns == "snuval":
            return value
        if value.kind != function.returns:
            raise HaltError(
                f"{function.name!r} declares {function.returns} but gave {value.kind}"
            )
        return value

    def _pending_call(self, expr: _Expr) -> _Call | None:
        r"""Return the call ``_eval`` would reach first, or None if there is."""
        if expr[0] == "lit" or expr[0] == "name":
            return None
        if expr[0] == "not":
            return self._pending_call(expr[1])
        if expr[0] == "step":
            return self._pending_call(expr[2])
        if expr[0] == "cmp":
            return self._pending_call(expr[2]) or self._pending_call(expr[3])
        for arg in expr[2]:
            found = self._pending_call(arg)
            if found is not None:
                return found
        return expr

    def _substitute(self, expr: _Expr, target: _Call, value: _Value) -> _Expr:
        r"""Return ``expr`` with ``target`` replaced by the literal ``value``."""
        if expr is target:
            return ("lit", value)
        if expr[0] == "lit" or expr[0] == "name":
            return expr
        if expr[0] == "not":
            return ("not", self._substitute(expr[1], target, value))
        if expr[0] == "step":
            return ("step", expr[1], self._substitute(expr[2], target, value))
        if expr[0] == "cmp":
            return (
                "cmp",
                expr[1],
                self._substitute(expr[2], target, value),
                self._substitute(expr[3], target, value),
            )
        return (
            "call",
            expr[1],
            tuple(self._substitute(arg, target, value) for arg in expr[2]),
        )

    # -- the simple statements,.

    def _simple(self, stmt: _Stmt, scope: dict[str, _Value]) -> None:
        r"""Execute a statement with no body: OUT, IN, SET, or an assignment."""
        if stmt[0] == "out":
            self.io.print_str(self._eval(stmt[1], scope).render())
        elif stmt[0] == "callstmt":
            self._eval(stmt[1], scope)  # run for its effects; the.
        elif stmt[0] == "in":
            self._read(stmt[1], scope)
        elif stmt[0] == "set":
            if stmt[1] in scope:
                raise HaltError(f"{stmt[1]!r} is already declared")
            value = self._eval(stmt[2], scope)
            if value.kind == "snuval":
                raise HaltError(f"SET {stmt[1]!r} needs a typed initial value")
            scope[stmt[1]] = value
        # The outer dispatch sends.
        # chain is exhaustive and the.
        elif stmt[0] == "assign":  # pragma: no branch
            current = scope.get(stmt[1])
            if current is None:
                raise HaltError(f"undeclared name {stmt[1]!r}")
            value = self._eval(stmt[2], scope)
            if value.kind != "snuval" and value.kind != current.kind:
                raise HaltError(
                    f"{stmt[1]!r} is {current.kind}, cannot take a {value.kind}"
                )
            scope[stmt[1]] = value

    def _read(self, name: str, scope: dict[str, _Value]) -> None:
        r"""Read one line into ``name``, per its declared type."""
        current = scope.get(name)
        if current is None:
            raise HaltError(f"undeclared name {name!r}")
        if current.kind == "snuval":
            raise HaltError(f"{name!r} has no type to read into")
        try:
            line = self.io.input_str()
        except EOFError:
            scope[name] = _Value(current.kind, 0)
            return
        if current.kind == "aschar":
            # An empty line is legal and.
            # package-wide answer, the same.
            code = ord(line[0]) if line else 0
            scope[name] = _Value("aschar", code if code < 128 else 0)
            return
        scope[name] = _Value("wubyte", _wubyte_of(line))

    # -- the stepped shell.

    def _finish(self, frame: _Frame) -> None:
        r"""Pop an exhausted frame, delivering a call's value if it was one."""
        self.frames.pop()
        if frame.function is None:
            return
        # A function body that runs out.
        # which ``_checked`` refuses.
        self._deliver(self._checked(frame.function, _SNUVAL))

    def _deliver(self, value: _Value) -> None:
        r"""Hand a finished call's value back to the frame that wanted it."""
        # A call is always made from.
        # itself a frame -- so popping.
        if self.frames:  # pragma: no branch
            self.frames[-1].returned = value

    def _expression_of(self, stmt: _Stmt) -> _Expr | None:
        r"""Return the expression ``stmt`` evaluates, or None if it has none."""
        slot = _EXPR_SLOT.get(stmt[0])
        return None if slot is None else cast("_Expr", stmt[slot])

    def step(self) -> None:
        r"""Execute one statement of the innermost frame."""
        if not self.frames:
            return
        frame = self.frames[-1]
        if frame.ind >= len(frame.body):
            self._finish(frame)
            return
        stmt = frame.body[frame.ind]

        # An expression is re-entered.
        # the calls already resolved;.
        expr = self._expression_of(stmt)
        if expr is not None:
            working = frame.pending if frame.pending is not None else expr
            if frame.returned is not None:
                call = self._pending_call(working)
                # A value is waiting only.
                # stepped, so the same search.
                if call is not None:  # pragma: no branch
                    working = self._substitute(working, call, frame.returned)
                frame.returned = None
            call = self._pending_call(working)
            if call is not None:
                frame.pending = working
                self._push_call(call, frame.scope)
                return
            frame.pending = None
            stmt = self._resolved(stmt, working)

        frame.ind += 1
        if stmt[0] == "if":
            branch = stmt[2] if self._eval(stmt[1], frame.scope).truthy() else stmt[3]
            self.frames.append(_Frame(branch, frame.scope))
        elif stmt[0] == "while":
            if self._eval(stmt[1], frame.scope).truthy():
                # Rewind onto the WHILE itself,.
                # re-tests the condition rather.
                # next lap re-reads the.
                # again rather than reusing.
                frame.ind -= 1
                self.frames.append(_Frame(stmt[2], frame.scope))
        elif stmt[0] == "give":
            self._give(self._eval(stmt[1], frame.scope))
        else:
            self._simple(stmt, frame.scope)

    def _resolved(self, stmt: _Stmt, expr: _Expr) -> _Stmt:
        r"""Return ``stmt`` with its expression replaced by the resolved one."""
        slot = _EXPR_SLOT[stmt[0]]
        parts = list(stmt)
        parts[slot] = expr
        return cast("_Stmt", tuple(parts))

    def _push_call(self, call: _Call, scope: dict[str, _Value]) -> None:
        r"""Start a call: select its overload and push its body as a frame."""
        # Every argument is call-free.
        # innermost call, so any call.
        values = [self._eval(arg, scope) for arg in call[2]]
        function = self._overload(call[1], values)
        self.frames.append(
            _Frame(function.body, self._resolve(function, values), function=function)
        )

    def _give(self, value: _Value) -> None:
        r"""Return ``value`` from the innermost call, unwinding its blocks."""
        while self.frames:
            frame = self.frames.pop()
            if frame.function is not None:
                self._deliver(self._checked(frame.function, value))
                return
        raise HaltError("GIVE outside a function")


def _wubyte_of(line: str) -> int:
    r"""Parse a 1-3 digit decimal wubyte, per the wiki's ``IN`` convention."""
    text = line.strip()
    if not text.isdigit() or len(text) > 3:
        return 0
    value = int(text)
    return value if 0 <= value <= 255 else 0


def run(code: str, io: IO) -> None:
    r"""Run a DINAC program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
