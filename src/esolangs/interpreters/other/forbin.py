r"""Interpreter for Forbin."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal, NoReturn

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# -- parser.

# The parse tree, as tuples.
# families, because the grammar.
# spec that heads a for-loop,.
# holds a spec, a spec holds.
# aliases quote their forward.
_Lit = tuple[Literal["lit"], int]
_Not = tuple[Literal["not"], "_ValueNode"]
_Var = tuple[Literal["var"], str]
_FnLit = tuple[Literal["fnlit"], "_Function"]
_CallNode = tuple[Literal["call"], "_ValueNode", list["_ValueNode"]]
_ValueNode = _Lit | _Not | _Var | _FnLit | _CallNode

# ``*`` is a wildcard standing.
# one-tuple: reading [1] off.
_Star = tuple[Literal["*"]]
_ValuePat = tuple[Literal["value"], _ValueNode]
_Group = tuple[Literal["group"], list["_Star | _ValuePat"]]
_Pattern = _Star | _ValuePat | _Group

_Range = tuple[Literal["range"], str, _ValueNode, _ValueNode]
_Iter = tuple[Literal["iter"], list[str], list[_Pattern]]
_ForSpec = _Range | _Iter

_Return = tuple[Literal["return"], _ValueNode]
_Assign = tuple[Literal["assign"], list[str], list[_ValueNode]]
_For = tuple[Literal["for"], _ForSpec, list["_Statement"]]
_Statement = _Return | _Assign | _CallNode | _For


class _Function:
    r"""A parsed function: name, parameter names, body, nested definitions."""

    __slots__ = ("args", "body", "name", "nested")

    def __init__(self, name: str, args: list[str]) -> None:
        self.name = name
        self.args = args
        self.body: list[_Statement] = []
        self.nested: dict[str, _Function] = {}


class _Parser:
    r"""Recursive-descent parser for Forbin source text."""

    def __init__(self, text: str) -> None:
        self.t = text
        self.i = 0
        self.n = len(text)

    def _skip_ws(self) -> None:
        while self.i < self.n:
            c = self.t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "/" and self.i + 1 < self.n and self.t[self.i + 1] == "/":
                while self.i < self.n and self.t[self.i] not in "\r\n":
                    self.i += 1
            else:
                return

    def _peek(self) -> str:
        self._skip_ws()
        return self.t[self.i] if self.i < self.n else ""

    def _fail(self, msg: str) -> NoReturn:
        raise ValueError(f"{msg} at position {self.i}")

    def _expect(self, ch: str) -> None:
        self._skip_ws()
        if self.i >= self.n or self.t[self.i] != ch:
            self._fail(f"expected {ch!r}")
        self.i += 1

    def _ident(self) -> str:
        self._skip_ws()
        if self.i >= self.n or not (self.t[self.i].isalpha() or self.t[self.i] == "_"):
            self._fail("expected an identifier")
        start = self.i
        self.i += 1
        while self.i < self.n and (self.t[self.i].isalnum() or self.t[self.i] == "_"):
            self.i += 1
        return self.t[start : self.i]

    def _value(self) -> _ValueNode:
        self._skip_ws()
        if self.i >= self.n:
            self._fail("expected a value")
        c = self.t[self.i]
        if c == "!":
            self.i += 1
            return ("not", self._value())
        if c in "01":
            self.i += 1
            return ("lit", int(c))
        if c == "{":  # a bare {code} block is a.
            body, nested = self._block()
            fn = _Function("", [])
            fn.body, fn.nested = body, nested
            return ("fnlit", fn)
        if c == "(":
            self.i += 1
            save = self.i
            first = self._ident()
            self._skip_ws()
            if self._peek() == "@":  # anonymous function literal.
                params = [first]
                self._expect("@")
                body, nested = self._block()
                self._expect(")")
                fn = _Function("", params)
                fn.body, fn.nested = body, nested
                return ("fnlit", fn)
            self.i = save
            callee: _Var = ("var", self._ident())
            args: list[_ValueNode] = []
            self._skip_ws()
            while self._peek() != ")":
                if args:
                    self._expect(",")
                args.append(self._value())
            self._expect(")")
            return ("call", callee, args)
        if not (c.isalpha() or c == "_"):
            self._fail(f"unexpected character {c!r}")
        return ("var", self._ident())

    def _values(self) -> list[_ValueNode]:
        values = [self._value()]
        while self._peek() == ",":
            self.i += 1
            values.append(self._value())
        return values

    def _semi(self) -> None:
        self._skip_ws()
        if self._peek() == ";":
            self.i += 1

    def _pattern(self) -> _Star | _ValuePat:
        self._skip_ws()
        if self._peek() == "*":
            self.i += 1
            return ("*",)
        return ("value", self._value())

    def _pattern_group(self) -> _Pattern:
        self._expect("(")
        pats: list[_Star | _ValuePat] = []
        while self._peek() != ")":
            if pats:
                self._expect(",")
            pats.append(self._pattern())
        self._expect(")")
        return ("group", pats)

    def _for_spec(self) -> _ForSpec:
        self._skip_ws()
        if self._peek() == "(":
            self.i += 1
            vars_ = [self._ident()]
            while self._peek() == ",":
                self.i += 1
                vars_.append(self._ident())
            self._expect(")")
        else:
            vars_ = [self._ident()]
        self._expect(":")
        self._skip_ws()
        if self._peek() == "(":
            self.i += 1
            items: list[_Pattern] = []
            while self._peek() != ")":
                if items:
                    self._expect(",")
                if len(vars_) == 1:
                    items.append(self._pattern())
                else:
                    items.append(self._pattern_group())
            self._expect(")")
            return ("iter", vars_, items)
        start = self._value()
        self._skip_ws()
        if not self.t.startswith("..", self.i):
            self._fail("expected '..' or an iteration list")
        self.i += 2
        end = self._value()
        return ("range", vars_[0], start, end)

    def _header(self) -> tuple[str, list[str]]:
        r"""Parse ``name [param (, param)*]``, stopping before any ``{``."""
        name = self._ident()
        params: list[str] = []
        while True:
            self._skip_ws()
            if self._peek() == ",":
                self.i += 1
                self._skip_ws()
                if self.i < self.n and (
                    self.t[self.i].isalpha() or self.t[self.i] == "_"
                ):
                    params.append(self._ident())
                    continue
                break
            if self.i < self.n and (self.t[self.i].isalpha() or self.t[self.i] == "_"):
                params.append(self._ident())
                continue
            break
        return name, params

    def _block(self) -> tuple[list[_Statement], dict[str, _Function]]:
        self._expect("{")
        stmts: list[_Statement] = []
        nested: dict[str, _Function] = {}
        while True:
            self._skip_ws()
            if self.i >= self.n:
                self._fail("unterminated block, expected '}'")
            if self.t[self.i] == "}":
                self.i += 1
                return stmts, nested
            c = self.t[self.i]
            if c.isalpha() or c == "_":
                save = self.i
                name, params = self._header()
                self._skip_ws()
                if self._peek() == "{":
                    fn = _Function(name, params)
                    fn.body, fn.nested = self._block()
                    nested[name] = fn
                    continue
                self.i = save
            stmts.append(self._statement())

    def _statement(self) -> _Statement:
        self._skip_ws()
        if self.t.startswith("return", self.i):
            j = self.i + 6
            if j >= self.n or not (self.t[j].isalnum() or self.t[j] == "_"):
                self.i = j
                value = self._value()
                self._semi()
                return ("return", value)
        if self.t.startswith("for", self.i):
            j = self.i + 3
            if j >= self.n or not (self.t[j].isalnum() or self.t[j] == "_"):
                self.i = j
                spec = self._for_spec()
                body, _ = self._block()
                return ("for", spec, body)
        first = self._value()
        self._skip_ws()
        if self._peek() == "=":
            if first[0] != "var":
                self._fail("assignment target must be a variable")
            self.i += 1
            rhs = self._values()
            self._semi()
            return ("assign", [first[1]], rhs)
        if self._peek() == ",":
            values = [first]
            while self._peek() == ",":
                self.i += 1
                values.append(self._value())
            self._skip_ws()
            if self._peek() != "=":
                self._fail("expected '=' after assignment targets")
            self.i += 1
            # Collecting the names as they.
            # list typed, which an.
            names: list[str] = []
            for v in values:
                if v[0] != "var":
                    self._fail("assignment target must be a variable")
                names.append(v[1])
            rhs = self._values()
            self._semi()
            return ("assign", names, rhs)
        if first[0] not in ("var", "call"):
            self._fail("statement must be a call, assignment, or return")
        args = (
            self._values() if self._peek() in "01!(_" or self._peek().isalpha() else []
        )
        self._semi()
        return ("call", first, args)

    def parse(self) -> dict[str, _Function]:
        funcs: dict[str, _Function] = {}
        while True:
            self._skip_ws()
            if self.i >= self.n:
                return funcs
            name, params = self._header()
            self._skip_ws()
            if self._peek() != "{":
                self._fail("expected '{' after function name")
            fn = _Function(name, params)
            fn.body, fn.nested = self._block()
            funcs[fn.name] = fn


# -- runtime.


class _BitReader:
    r"""Serves the input one bit at a time, most significant first."""

    def __init__(self, io: IO) -> None:
        self.io = io
        self.bits: list[int] = []

    def read(self) -> int:
        if not self.bits:
            byte = self.io.input_char()
            self.bits = [(byte >> k) & 1 for k in range(7, -1, -1)]
        return self.bits.pop(0)


class _Frame:
    r"""One function invocation: its function, the caller, and its locals."""

    __slots__ = (
        "body",
        "fn",
        "for_body",
        "for_body_pos",
        "for_ind",
        "for_names",
        "for_rows",
        "locals",
        "parent",
        "pos",
    )

    def __init__(self, fn: _Function, parent: _Frame | None) -> None:
        self.fn = fn
        self.parent = parent
        self.locals: dict[str, object] = {}
        self.body = fn.body
        self.pos = 0
        self.for_rows: list[list[object]] | None = None
        self.for_names: list[str] = []
        self.for_ind = 0
        self.for_body: list[_Statement] = []
        self.for_body_pos = 0

    def at(self, **fields: object) -> _Frame:
        r"""Return a copy of this frame with ``fields`` replaced."""
        copy = _Frame.__new__(_Frame)
        for slot in _Frame.__slots__:
            object.__setattr__(copy, slot, getattr(self, slot))
        for name, value in fields.items():
            object.__setattr__(copy, name, value)
        return copy


def _lookup(frame: _Frame | None, name: str, globals_: dict[str, _Function]) -> object:
    r"""Resolve a variable, builtin, or function name from ``frame``."""
    while frame is not None:
        if name in frame.locals:
            return frame.locals[name]
        if name in frame.fn.nested:
            return frame.fn.nested[name]
        frame = frame.parent
    if name in ("in", "out"):
        return name
    if name in globals_:
        return globals_[name]
    raise HaltError(f"undeclared identifier {name!r}")


def _eval(
    node: _ValueNode,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object:
    if node[0] == "lit":
        return node[1]
    if node[0] == "not":
        value = _eval(node[1], frame, globals_, reader, depth)
        if value in (0, 1):
            return 1 - value
        raise HaltError("! needs a bit")
    if node[0] == "var":
        return _lookup(frame, node[1], globals_)
    if node[0] == "fnlit":
        return node[1]
    callee = _eval(node[1], frame, globals_, reader, depth)
    args = [_eval(a, frame, globals_, reader, depth) for a in node[2]]
    return _call(callee, args, frame, globals_, reader, depth)


def _bound(value: object, which: str) -> int:
    r"""Return a ``for`` range bound, halting if it is not a number."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise HaltError(f"for {which} bound must be a number, got {value!r}")
    return value


def _call(
    callee: object,
    args: list[object],
    caller: _Frame | None,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object:
    if isinstance(callee, _Function):
        frame = _Frame(callee, caller)
        # unpassed parameters are set.
        for name in callee.args:
            frame.locals[name] = 0
        for name, value in zip(callee.args, args, strict=False):
            frame.locals[name] = value
        result = _run(frame, globals_, reader, depth + 1)
        return result if result is not None else 0
    if isinstance(callee, str):
        if callee == "in":
            return reader.read()
        # A name only evaluates to a.
        # ``("in", "out")`` test in.
        # ``out`` and needs no test of.
        if len(args) != 8:
            raise HaltError("out needs exactly 8 bit arguments")
        byte = 0
        for bit in args:
            # Same rule as ``!`` above: a.
            # else has no byte to.
            if bit == 0:
                byte *= 2
            elif bit == 1:
                byte = byte * 2 + 1
            else:
                raise HaltError("out needs bit arguments")
        reader.io.print_char(chr(byte))
        return 0
    raise HaltError("called value is not a function")


def _run(
    frame: _Frame, globals_: dict[str, _Function], reader: _BitReader, depth: int = 0
) -> object | None:
    r"""Run ``frame``'s body to completion, natively recursing into any."""
    for stmt in frame.fn.body:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _exec_stmt(
    stmt: _Statement,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    r"""Execute one statement, returning its value if it was a ``return``."""
    if stmt[0] == "return":
        return _eval(stmt[1], frame, globals_, reader, depth)
    if stmt[0] == "assign":
        targets, rhs = stmt[1], stmt[2]
        if len(rhs) == 1:
            for name in targets:
                if name != "_":
                    frame.locals[name] = _eval(rhs[0], frame, globals_, reader, depth)
        else:
            for name, value in zip(targets, rhs, strict=False):
                if name != "_":
                    frame.locals[name] = _eval(value, frame, globals_, reader, depth)
        return None
    if stmt[0] == "call":
        callee = _eval(stmt[1], frame, globals_, reader, depth)
        args = [_eval(a, frame, globals_, reader, depth) for a in stmt[2]]
        _call(callee, args, frame, globals_, reader, depth)
        return None
    # The three arms above are the.
    # left is a ``for``.
    spec, body = stmt[1], stmt[2]
    rows: list[list[object]]
    if spec[0] == "range":
        _, name, start_node, end_node = spec
        start = _eval(start_node, frame, globals_, reader, depth)
        end = _eval(end_node, frame, globals_, reader, depth)
        lo, hi = _bound(start, "start"), _bound(end, "end")
        rows = [[v] for v in range(lo, hi + 1)] if lo <= hi else []
        names = [name]
    else:
        _, names, patterns = spec
        rows = []
        for pat in patterns:
            items = pat[1] if pat[0] == "group" else [pat]
            wilds = [j for j, p in enumerate(items) if p[0] == "*"]
            if not wilds:
                rows.append(
                    [
                        (
                            _eval(p[1], frame, globals_, reader, depth)
                            if p[0] == "value"
                            else 0
                        )
                        for p in items
                    ]
                )
            else:
                import itertools

                for combo in itertools.product((0, 1), repeat=len(wilds)):
                    row: list[object] = []
                    w = 0
                    for p in items:
                        if p[0] == "*":
                            row.append(combo[w])
                            w += 1
                        else:
                            row.append(_eval(p[1], frame, globals_, reader, depth))
                    rows.append(row)
    for row in rows:
        for name, bound in zip(names, row, strict=False):
            if name != "_":
                frame.locals[name] = bound
        got = _exec_block(body, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _exec_block(
    stmts: list[_Statement],
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    r"""Run a block of statements in ``frame``'s scope; None unless a."""
    for stmt in stmts:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _for_rows(
    spec: _ForSpec,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> tuple[list[list[object]], list[str]]:
    r"""Compute a ``for`` statement's iteration rows and bound variable."""
    if spec[0] == "range":
        _, name, start_node, end_node = spec
        start = _eval(start_node, frame, globals_, reader, depth)
        end = _eval(end_node, frame, globals_, reader, depth)
        lo, hi = _bound(start, "start"), _bound(end, "end")
        range_rows: list[list[object]] = (
            [[v] for v in range(lo, hi + 1)] if lo <= hi else []
        )
        return range_rows, [name]
    _, names, patterns = spec
    rows: list[list[object]] = []
    for pat in patterns:
        items = pat[1] if pat[0] == "group" else [pat]
        wilds = [j for j, p in enumerate(items) if p[0] == "*"]
        if not wilds:
            rows.append(
                [
                    (
                        _eval(p[1], frame, globals_, reader, depth)
                        if p[0] == "value"
                        else 0
                    )
                    for p in items
                ]
            )
        else:
            import itertools

            for combo in itertools.product((0, 1), repeat=len(wilds)):
                row: list[object] = []
                w = 0
                for p in items:
                    if p[0] == "*":
                        row.append(combo[w])
                        w += 1
                    else:
                        row.append(_eval(p[1], frame, globals_, reader, depth))
                rows.append(row)
    return rows, names


def _start_statement_call(
    stmt: _Statement,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
) -> _Frame | None:
    r"""Evaluate a statement-position call and return a pushed frame, if."""
    if stmt[0] != "call":
        return None
    callee = _eval(stmt[1], frame, globals_, reader, 0)
    if not isinstance(callee, _Function):
        return None
    args = [_eval(a, frame, globals_, reader, 0) for a in stmt[2]]
    new_frame = _Frame(callee, frame)
    # unpassed parameters are set.
    for name in callee.args:
        new_frame.locals[name] = 0
    for name, value in zip(callee.args, args, strict=False):
        new_frame.locals[name] = value
    return new_frame


@dataclass
class _State:
    r"""The live call frames and buffered bit reader of a Forbin run."""

    frames: list[_Frame]
    reader: _BitReader


class _Machine:
    r"""One Forbin run: an explicit stack of resumable call frames."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        # Where the source ends, kept.
        # position once every frame has.
        self._length = len(code)
        self.globals = _Parser(code).parse()
        if "main" not in self.globals:
            raise ValueError("Forbin program has no main function")
        reader = _BitReader(io)
        main_fn = self.globals["main"]
        main_frame = _Frame(main_fn, None)
        # unpassed parameters are set.
        # with a single dummy argument.
        for name in main_fn.args:
            main_frame.locals[name] = 0
        self.state = _State([main_frame], reader)

    @property
    def reader(self) -> _BitReader:
        return self.state.reader

    @property
    def frames(self) -> list[_Frame]:
        return self.state.frames

    @property
    def halted(self) -> bool:
        r"""Whether the frame stack has emptied (``main`` returned or ended)."""
        return not self.frames

    # The VM's language-shaped.
    # the innermost frame's integer.

    # : ``ip`` is a position, but.
    #: position.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""Each live frame's statement position, outermost first."""
        frames = self.frames
        return tuple(f.pos for f in frames) if frames else (self._length,)

    @property
    def memory(self) -> list[int]:
        r"""The innermost frame's integer locals."""
        if not self.frames:
            return []
        return [v for v in self.frames[-1].locals.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language; calls use explicit frames."""
        return []

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        r"""Return what ``frame`` is about to run, for the ancestor check."""
        return (
            frame.fn.name,
            tuple(sorted((k, repr(v)) for k, v in frame.locals.items())),
            self.io.position(),
        )

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(
                (
                    f.fn.name,
                    f.pos,
                    tuple(sorted((k, repr(v)) for k, v in f.locals.items())),
                    f.for_ind if f.for_rows is not None else -1,
                    f.for_body_pos if f.for_rows is not None else -1,
                )
                for f in self.frames
            ),
            self.io.position(),
        )

    def step(self) -> None:
        r"""Execute one statement, one ``for``-loop row, or advance a call."""
        try:
            self._step_once()
        except RecursionError:
            raise HaltError(
                "expression-position recursion exceeded the host's depth limit"
            ) from None

    def _step_once(self) -> None:
        r"""Execute one statement, one ``for``-loop row, or advance a call."""
        if self.halted:
            return
        frame = self.frames[-1]

        if frame.for_rows is not None:
            self._step_for(frame)
            return

        if frame.pos >= len(frame.body):
            self._pop()
            return

        stmt = frame.body[frame.pos]
        if stmt[0] == "for":
            spec = stmt[1]
            rows, names = _for_rows(spec, frame, self.globals, self.reader, 0)
            self.frames[-1] = frame.at(for_rows=rows, for_names=names, for_ind=0)
            return

        pushed = _start_statement_call(stmt, frame, self.globals, self.reader)
        if pushed is not None:
            self.frames[-1] = frame.at(pos=frame.pos + 1)
            self.frames.append(pushed)
            return
        got = _exec_stmt(stmt, frame, self.globals, self.reader, 0)
        self.frames[-1] = frame.at(pos=frame.pos + 1)
        if got is not None:
            self._pop()

    def _step_for(self, frame: _Frame) -> None:
        r"""Advance a ``for`` loop already in progress."""
        if frame.for_body_pos < len(frame.for_body):
            stmt = frame.for_body[frame.for_body_pos]
            pushed = _start_statement_call(stmt, frame, self.globals, self.reader)
            if pushed is not None:
                self.frames[-1] = frame.at(for_body_pos=frame.for_body_pos + 1)
                self.frames.append(pushed)
                return
            got = _exec_stmt(stmt, frame, self.globals, self.reader, 0)
            self.frames[-1] = frame.at(for_body_pos=frame.for_body_pos + 1)
            if got is not None:
                self._pop()
            return
        if frame.for_ind >= len(frame.for_rows or []):
            self.frames[-1] = frame.at(for_rows=None, pos=frame.pos + 1)
            return
        row = frame.for_rows[frame.for_ind] if frame.for_rows is not None else []
        frame = frame.at(for_ind=frame.for_ind + 1)
        self.frames[-1] = frame
        for name, value in zip(frame.for_names, row, strict=False):
            if name != "_":
                frame.locals[name] = value
        # This method only runs while.
        # rows it is walking, so the.
        # The tag is checked rather.
        # union is what lets.
        # ``if`` would make a broken.
        # silently instead of saying so.
        # keeps the check under.
        # The message names the tag.
        # line carries mutants no test.
        # at three for a constant.
        # spelling is chosen for what.
        current = frame.body[frame.pos]
        if current[0] != "for":
            raise AssertionError(f"cursor left the for statement: {current[0]}")
        self.frames[-1] = frame.at(for_body=current[2], for_body_pos=0)

    def _pop(self) -> None:
        r"""Pop the finished top frame."""
        self.frames.pop()


def run(code: str, io: IO) -> None:
    r"""Run a Forbin program, calling ``main`` with a dummy argument."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
