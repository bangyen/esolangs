"""Interpreter for Forbin.

An imperative language whose only datatypes are functions and bits:
functions with bit arguments and nested definitions, iteration and range
for-loops (a range loop ``for i:1..0`` doubles as an if-statement), the NOT
operator, and the ``in``/``out`` builtins that read one bit and write one
byte as eight bit arguments (most significant first).

Decisions for gaps in the wiki spec (documented):
- the entry point is the function ``main``, called with a single dummy
  argument 0 (the examples always call ``main 0``);
- extra call arguments are discarded (``main 0`` passes a dummy), and
  unpassed parameters are set to 0;
- ``in`` reads the next bit and raises :class:`EOFError` when the input is
  exhausted (as the Brainfuck interpreter does); the wiki's cat example is
  not reproduced because its range-loop "while" (``for _:0..1`` runs twice)
  doubles every byte — it was never run, Forbin being unimplemented;
- statements may omit the trailing ``;`` before a closing ``}`` (the wiki's
  cat example writes ``shouldLoop = 1`` with no semicolon);
- a trailing statement semicolon is otherwise optional, matching the wiki's
  loose examples;
- a call that resolves to no function is an invalid operation
  (:class:`~esolangs.exceptions.HaltError`), and malformed syntax raises
  :class:`ValueError`.
"""

from __future__ import annotations

import sys
from typing import Any, NoReturn, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# -- parser ---------------------------------------------------------------

_RETURN = ("return",)


_Node = tuple[Any, ...]


class _Function:
    """A parsed function: name, parameter names, body, nested definitions."""

    __slots__ = ("args", "body", "name", "nested")

    def __init__(self, name: str, args: list[str]) -> None:
        self.name = name
        self.args = args
        self.body: list[_Node] = []
        self.nested: dict[str, _Function] = {}


class _Parser:
    """Recursive-descent parser for Forbin source text."""

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

    def _value(self) -> _Node:
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
        if c == "{":  # a bare {code} block is a function literal (no args)
            body, nested = self._block()
            fn = _Function("", [])
            fn.body, fn.nested = body, nested
            return ("fnlit", fn)
        if c == "(":
            self.i += 1
            save = self.i
            first = self._ident()
            self._skip_ws()
            if self._peek() == "@":  # anonymous function literal
                params = [first]
                self._expect("@")
                body, nested = self._block()
                self._expect(")")
                fn = _Function("", params)
                fn.body, fn.nested = body, nested
                return ("fnlit", fn)
            self.i = save
            callee = ("var", self._ident())
            args: list[_Node] = []
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

    def _values(self) -> list[_Node]:
        values = [self._value()]
        while self._peek() == ",":
            self.i += 1
            values.append(self._value())
        return values

    def _semi(self) -> None:
        self._skip_ws()
        if self._peek() == ";":
            self.i += 1

    def _pattern(self) -> _Node:
        self._skip_ws()
        if self._peek() == "*":
            self.i += 1
            return ("*",)
        return ("value", self._value())

    def _pattern_group(self) -> _Node:
        self._expect("(")
        pats: list[_Node] = []
        while self._peek() != ")":
            if pats:
                self._expect(",")
            pats.append(self._pattern())
        self._expect(")")
        return ("group", pats)

    def _for_spec(self) -> _Node:
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
            items: list[_Node] = []
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
        """Parse ``name [param (, param)*]``, stopping before any ``{``."""
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

    def _block(self) -> tuple[list[_Node], dict[str, _Function]]:
        self._expect("{")
        stmts: list[_Node] = []
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
            stmt = self._statement()
            if stmt is not None:
                stmts.append(stmt)

    def _statement(self) -> _Node | None:
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
            ids = [first]
            while self._peek() == ",":
                self.i += 1
                ids.append(self._value())
            self._skip_ws()
            if self._peek() != "=":
                self._fail("expected '=' after assignment targets")
            self.i += 1
            if not all(v[0] == "var" for v in ids):
                self._fail("assignment target must be a variable")
            rhs = self._values()
            self._semi()
            return ("assign", [v[1] for v in ids], rhs)
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


# -- runtime --------------------------------------------------------------


class _BitReader:
    """Serves the input one bit at a time, most significant first."""

    def __init__(self, io: IO) -> None:
        self.io = io
        self.bits: list[int] = []

    def read(self) -> int:
        if not self.bits:
            byte = self.io.input_char()
            self.bits = [(byte >> k) & 1 for k in range(7, -1, -1)]
        return self.bits.pop(0)


class _Frame:
    """One function invocation: its function, the caller, and its locals."""

    __slots__ = ("fn", "locals", "parent")

    def __init__(self, fn: _Function, parent: _Frame | None) -> None:
        self.fn = fn
        self.parent = parent
        self.locals: dict[str, object] = {}


def _lookup(frame: _Frame | None, name: str, globals_: dict[str, _Function]) -> object:
    """Resolve a variable, builtin, or function name from ``frame`` outward."""
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
    node: _Node,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object:
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "not":
        value = _eval(node[1], frame, globals_, reader, depth)
        if value in (0, 1):
            return 1 - value
        raise HaltError("! needs a bit")
    if kind == "var":
        return _lookup(frame, node[1], globals_)
    if kind == "fnlit":
        return node[1]
    if kind == "call":
        callee = _eval(node[1], frame, globals_, reader, depth)
        args = [_eval(a, frame, globals_, reader, depth) for a in node[2]]
        return _call(callee, args, frame, globals_, reader, depth)
    raise AssertionError(f"unexpected value node {node!r}")


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
        # unpassed parameters are set to 0 (per the wiki)
        for name in callee.args:
            frame.locals[name] = 0
        for name, value in zip(callee.args, args, strict=False):
            frame.locals[name] = value
        result = _run(frame, globals_, reader, depth + 1)
        return result if result is not None else 0
    if isinstance(callee, str):
        if callee == "in":
            return reader.read()
        if callee == "out":
            if len(args) != 8:
                raise HaltError("out needs exactly 8 bit arguments")
            byte = 0
            for bit in args:
                byte = byte * 2 + cast(int, bit)
            reader.io.print_char(chr(byte))
            return 0
    raise HaltError("called value is not a function")


def _run(
    frame: _Frame, globals_: dict[str, _Function], reader: _BitReader, depth: int = 0
) -> object | None:
    # each level costs about three Python frames (_call, _run, _exec_stmt), so
    # 250 stays well under the interpreter's own recursion limit and fires
    # before a raw RecursionError leaks out
    if depth > 250:
        raise HaltError("recursion limit exceeded")
    for stmt in frame.fn.body:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def _exec_stmt(
    stmt: _Node,
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    """Execute one statement, returning its value if it was a ``return``."""
    kind = stmt[0]
    if kind == "return":
        return _eval(stmt[1], frame, globals_, reader, depth)
    if kind == "assign":
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
    if kind == "call":
        callee = _eval(stmt[1], frame, globals_, reader, depth)
        args = [_eval(a, frame, globals_, reader, depth) for a in stmt[2]]
        _call(callee, args, frame, globals_, reader, depth)
        return None
    if kind == "for":
        spec, body = stmt[1], stmt[2]
        rows: list[list[object]]
        if spec[0] == "range":
            _, name, start_node, end_node = spec
            start = _eval(start_node, frame, globals_, reader, depth)
            end = _eval(end_node, frame, globals_, reader, depth)
            rows = (
                [[v] for v in range(cast(int, start), cast(int, end) + 1)]
                if cast(int, start) <= cast(int, end)
                else []
            )
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
            for name, value in zip(names, row, strict=False):
                if name != "_":
                    frame.locals[name] = value
            got = _exec_block(body, frame, globals_, reader, depth)
            if got is not None:
                return got
        return None
    raise AssertionError(f"unexpected statement {stmt!r}")


def _exec_block(
    stmts: list[_Node],
    frame: _Frame,
    globals_: dict[str, _Function],
    reader: _BitReader,
    depth: int,
) -> object | None:
    """Run a block of statements in ``frame``'s scope; None unless a return fired."""
    for stmt in stmts:
        got = _exec_stmt(stmt, frame, globals_, reader, depth)
        if got is not None:
            return got
    return None


def run(code: str, io: IO) -> None:
    """Run a Forbin program, calling ``main`` with a dummy argument."""
    funcs = _Parser(code).parse()
    if "main" not in funcs:
        raise ValueError("Forbin program has no main function")
    reader = _BitReader(io)
    _call(funcs["main"], [0], None, funcs, reader, 0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
