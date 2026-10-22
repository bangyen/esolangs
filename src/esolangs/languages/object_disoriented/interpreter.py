"""Interpreter for Object disoriented.

Every value is an object: a function and two members ``a`` and ``b``,
compared and copied as values.  Calling ``f X Y`` runs ``X``'s function
with ``a``/``b`` naming ``X``'s members, ``s`` naming ``X`` itself, ``p``
naming ``Y`` by reference, and a fresh local ``t``; ``r`` ends it.  There is
no control flow: the input bit ``1`` is ``n fpz rz zz``, an object that
calls its parameter, and ``0`` is ``z``, which does nothing, so ``f i X``
runs ``X`` only on a 1.  The wiki's Delayed cat echoes its input through the
first byte above 128.

Input/output:
    ``o`` prints ``z`` as 0 and anything else as 1; both directions pack bits
    most significant first.  Input at EOF raises.

Errors:
    ProgramError: A form that ends early; a class name or comment with no
    closing ``.``; an empty class name; an unknown object letter; a ``c``
    destination other than ``a b s t p``; a top-level item that is not a
    definition ``d``; a class defined twice; no ``main`` class; an undefined
    class; a class that instantiates itself in its members.
    InputExhaustedError: ``i`` reads a new byte at EOF.

Decisions:
    * An lvalue argument (``a b s t p``) is passed as its place: writes inside
      the call reach it, so ``f a a`` aliases.  Any other argument is a
      temporary that the call may write and the caller never sees.
    * A write to ``s`` lands on the called object's place when its function
      returns; ``a``/``b`` writes land at once.
    * ``t`` starts as ``z``.  ``l"id".`` is the macro the wiki calls it: the
      class's ``n(f)**``, members evaluated where it is written.  ``main`` is
      entered as ``flmain.z``.
    * Objects with the same function and members are equal, so ``n rz zz``
      is ``z`` and prints 0.
    * Whitespace is ignored outside comments; a class name runs to its ``.``
      with whitespace dropped.  Commands are lowercase.
    * A partial output byte at the halt is never printed: a char is printed
      "when the 8th bit is sent".
    * The wiki's Hello world lacks ``r`` in ``p0``/``p1`` and, repaired, prints
      its data backwards ("hello wolrd" reversed, each byte bit-reversed): its
      stack pops last-in first.  The Minifuck interpreter does not parse (``c
      fnrfaz pz t`` leaves ``c`` without a destination).  Both are pinned.
"""

from __future__ import annotations

from typing import NamedTuple

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.persistent import CHUNK, Chunked, append, chunked, get, put

_LVALUES = frozenset("abstp")

#: One instruction: an opcode and its operand (a variable, a code id or 0).
type _Op = tuple[str, object]
#: A parsed rvalue: ``("z",)``, ``("i",)``, ``("v", name)``, ``("f", x, y)``,
#: ``("n", body, a, b)`` or ``("l", name)``.
type _Expr = tuple[object, ...]
#: A parsed function: its statements and the returned expression.
type _Body = tuple[tuple[_Expr, ...], _Expr]


class _Parser:
    """Recursive descent over the prefix grammar; every form starts with a letter."""

    def __init__(self, code: str) -> None:
        self.src = code
        self.pos = 0

    def peek(self) -> str:
        """Return the next command letter, skipping whitespace and comments."""
        src = self.src
        while True:
            while self.pos < len(src) and src[self.pos].isspace():
                self.pos += 1
            if self.pos < len(src) and src[self.pos] == "e":
                self.pos = self._to_dot("comment") + 1
                continue
            return src[self.pos] if self.pos < len(src) else ""

    def take(self) -> str:
        c = self.peek()
        if not c:
            raise ValueError("Object disoriented program ends inside a form")
        self.pos += 1
        return c

    def _to_dot(self, what: str) -> int:
        end = self.src.find(".", self.pos)
        if end < 0:
            raise ValueError(f"Object disoriented {what} has no closing '.'")
        return end

    def name(self) -> str:
        end = self._to_dot("class name")
        name = "".join(self.src[self.pos : end].split())
        self.pos = end + 1
        if not name:
            raise ValueError("Object disoriented class name is empty")
        return name

    def rvalue(self) -> _Expr:
        at = self.pos
        c = self.take()
        if c in _LVALUES:
            return ("v", c)
        if c in "zi":
            return (c,)
        if c == "f":
            return ("f", self.rvalue(), self.rvalue())
        if c == "n":
            return ("n", self.body(), self.rvalue(), self.rvalue())
        if c == "l":
            return ("l", self.name())
        raise ValueError(
            f"Object disoriented {c!r} at {at} is not an object; "
            "the objects are a b s t p z i f n l"
        )

    def body(self) -> _Body:
        stmts: list[_Expr] = []
        while True:
            c = self.peek()
            if c == "r":
                self.take()
                return tuple(stmts), self.rvalue()
            if c == "c":
                self.take()
                source = self.rvalue()
                at = self.pos
                dest = self.take()
                if dest not in _LVALUES:
                    raise ValueError(
                        f"Object disoriented {dest!r} at {at} cannot be written; "
                        "c writes a b s t p"
                    )
                stmts.append(("c", source, dest))
            elif c == "o":
                self.take()
                stmts.append(("o", self.rvalue()))
            else:
                stmts.append(("x", self.rvalue()))

    def program(self) -> dict[str, tuple[_Body, _Expr, _Expr]]:
        classes: dict[str, tuple[_Body, _Expr, _Expr]] = {}
        while self.peek():
            at = self.pos
            if self.take() != "d":
                raise ValueError(f"Object disoriented expects a definition 'd' at {at}")
            name = self.name()
            if name in classes:
                raise ValueError(f"Object disoriented class {name!r} is defined twice")
            classes[name] = (self.body(), self.rvalue(), self.rvalue())
        if "main" not in classes:
            raise ValueError("Object disoriented program defines no 'main' class")
        return classes


class _Compiler:
    """Flatten bodies into op lists, interning each by its ops."""

    def __init__(self, classes: dict[str, tuple[_Body, _Expr, _Expr]]) -> None:
        self.classes = classes
        self.codes: list[tuple[_Op, ...]] = []
        self.code_ids: dict[tuple[_Op, ...], int] = {}
        self.expanding: list[str] = []

    def intern(self, ops: tuple[_Op, ...]) -> int:
        if ops not in self.code_ids:
            self.code_ids[ops] = len(self.codes)
            self.codes.append(ops)
        return self.code_ids[ops]

    def function(self, body: _Body) -> int:
        stmts, ret = body
        ops: list[_Op] = []
        for stmt in stmts:
            self.value(stmt[1], ops)  # type: ignore[arg-type]
            if stmt[0] == "c":
                ops.append(("copy", stmt[2]))
            elif stmt[0] == "o":
                ops.append(("out", 0))
            else:
                ops.append(("drop", 0))
        self.value(ret, ops)
        ops.append(("ret", 0))
        return self.intern(tuple(ops))

    def place(self, expr: _Expr, ops: list[_Op]) -> None:
        """Push a reference: the variable's own place, or a fresh temporary."""
        if expr[0] == "v":
            ops.append(("ref", expr[1]))
        else:
            self.value(expr, ops)
            ops.append(("tmp", 0))

    def value(self, expr: _Expr, ops: list[_Op]) -> None:
        kind = expr[0]
        if kind == "v":
            ops.append(("get", expr[1]))
        elif kind == "z":
            ops.append(("z", 0))
        elif kind == "i":
            ops.append(("in", 0))
        elif kind == "f":
            self.place(expr[1], ops)  # type: ignore[arg-type]
            self.place(expr[2], ops)  # type: ignore[arg-type]
            ops.append(("call", 0))
        elif kind == "n":
            self.value(expr[2], ops)  # type: ignore[arg-type]
            self.value(expr[3], ops)  # type: ignore[arg-type]
            ops.append(("new", self.function(expr[1])))  # type: ignore[arg-type]
        else:
            name = expr[1]
            if name not in self.classes:
                raise ValueError(f"Object disoriented class {name!r} is not defined")
            if name in self.expanding:
                raise ValueError(
                    f"Object disoriented class {name!r} instantiates itself "
                    "in its members"
                )
            self.expanding.append(name)
            body, a, b = self.classes[name]
            self.value(("n", body, a, b), ops)
            self.expanding.pop()


#: ``0`` is ``z``; any other object is ``(code, a, b)``.
type _Obj = int | tuple[int, _Obj, _Obj]
#: A variable's place: a cell index, or ``(place, 1)``/``(place, 2)`` for
#: the ``a``/``b`` member of the object there.
type _Ref = int | tuple[_Ref, int]
#: ``(code, pc, self, param, base, pending, stack)``: ``base`` is the
#: frame's ``t`` cell, its temporaries above it.
type _Frame = tuple[int, int, _Ref, _Ref, int, _Obj | None, tuple[object, ...]]
#: The running calls, innermost first, as a linked list.
type _Frames = tuple[_Frame, _Frames] | None


class _Program(NamedTuple):
    """The compiled bodies, ``z``'s body first, and the input's 1 bit."""

    codes: tuple[tuple[_Op, ...], ...]
    one: _Obj


class _State(NamedTuple):
    """One instant: the calls, the cells, and the partial input/output bytes.

    Refs only point into callers' cells, so a returning call's cells are
    dead: the store is a stack, cut back to ``base`` on every return.
    """

    frames: _Frames
    store: Chunked[_Obj]
    size: int
    in_bits: tuple[int, ...]
    out_bits: tuple[int, ...]


def _obj(code: int, a: _Obj, b: _Obj) -> _Obj:
    """Build an object; ``z``'s own function and members make ``z``."""
    return 0 if code == 0 and a == 0 and b == 0 else (code, a, b)


def _load(store: Chunked[_Obj], ref: _Ref) -> _Obj:
    if isinstance(ref, int):
        return get(store, ref)
    held = _load(store, ref[0])
    return 0 if held == 0 else held[ref[1]]  # type: ignore[index]


def _write(store: Chunked[_Obj], ref: _Ref, value: _Obj) -> Chunked[_Obj]:
    if isinstance(ref, int):
        return put(store, ref, value)
    parent, slot = ref
    held = _load(store, parent)
    code, a, b = (0, 0, 0) if held == 0 else held  # type: ignore[misc]
    rebuilt = _obj(code, value, b) if slot == 1 else _obj(code, a, value)
    return _write(store, parent, rebuilt)


def _truncate(store: Chunked[_Obj], size: int) -> Chunked[_Obj]:
    """Keep the first ``size`` cells; cells are only appended, so chunks are full."""
    whole, part = divmod(size, CHUNK)
    return store[:whole] + ((store[whole][:part],) if part else ())


def _place(frame: _Frame, var: object) -> _Ref:
    _, _, self_ref, param, base, _, _ = frame
    if var == "t":
        return base
    if var == "p":
        return param
    if var == "s":
        return self_ref
    return (self_ref, 1 if var == "a" else 2)


def _advance(
    state: _State, program: _Program, byte: int | None = None
) -> tuple[_State, str | None]:
    """Run one op of the innermost call; return the state and any printed char.

    Pure: an input byte the op needs arrives as ``byte``.
    """
    frames, store, size, in_bits, out_bits = state
    assert frames is not None
    frame, rest = frames
    code, pc, self_ref, param, base, pending, stack = frame
    op, arg = program.codes[code][pc]
    pc += 1
    out = None
    if op == "get":
        stack = (*stack, _load(store, _place(frame, arg)))
    elif op == "ref":
        stack = (*stack, _place(frame, arg))
    elif op == "z":
        stack = (*stack, 0)
    elif op == "in":
        if not in_bits:
            assert byte is not None
            in_bits = tuple((byte >> k) & 1 for k in range(7, -1, -1))
        stack = (*stack, program.one if in_bits[0] else 0)
        in_bits = in_bits[1:]
    elif op == "tmp":
        store = append(store, stack[-1])  # type: ignore[arg-type]
        stack = (*stack[:-1], size)
        size += 1
    elif op == "new":
        a, b = stack[-2:]
        stack = (*stack[:-2], _obj(arg, a, b))  # type: ignore[arg-type]
    elif op == "call":
        target, given = stack[-2:]
        held = _load(store, target)  # type: ignore[arg-type]
        callee = 0 if held == 0 else held[0]  # type: ignore[index]
        caller: _Frame = (code, pc, self_ref, param, base, pending, stack[:-2])
        entered: _Frame = (callee, 0, target, given, size, None, ())  # type: ignore[assignment]
        return _State(
            ((entered, (caller, rest))), append(store, 0), size + 1, in_bits, out_bits
        ), None
    elif op == "copy":
        if arg == "s":
            pending = stack[-1]  # type: ignore[assignment]
        else:
            store = _write(store, _place(frame, arg), stack[-1])  # type: ignore[arg-type]
        stack = stack[:-1]
    elif op == "out":
        out_bits = (*out_bits, 0 if stack[-1] == 0 else 1)
        stack = stack[:-1]
        if len(out_bits) == 8:
            out = chr(int("".join(map(str, out_bits)), 2))
            out_bits = ()
    elif op == "drop":
        stack = stack[:-1]
    else:  # ret: the s write lands, the call's cells die, the value goes up
        value = stack[-1]
        if pending is not None:
            store = _write(store, self_ref, pending)
        store = _truncate(store, base)
        if rest is None:
            return _State(None, store, base, in_bits, out_bits), None
        (c, p, s, q, b, w, st), outer = rest
        return _State(
            ((c, p, s, q, b, w, (*st, value)), outer), store, base, in_bits, out_bits
        ), None
    return _State(
        ((code, pc, self_ref, param, base, pending, stack), rest),
        store,
        size,
        in_bits,
        out_bits,
    ), out


class _Machine:
    """The shell around :func:`_advance`: it reads bytes and prints chars."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        compiler = _Compiler(_Parser(code).program())
        compiler.function(((), ("z",)))  # z's body: code 0
        one = compiler.function(((("x", ("f", ("v", "p"), ("z",))),), ("z",)))
        boot = compiler.function(((("x", ("f", ("l", "main"), ("z",))),), ("z",)))
        self.program = _Program(tuple(compiler.codes), (one, 0, 0))
        # The boot call runs ``flmain.z``; its self and parameter are its ``t``.
        self.state = _State(
            (((boot, 0, 0, 0, 0, None, ())), None), chunked([0]), 1, (), ()
        )

    @property
    def halted(self) -> bool:
        return self.state.frames is None

    @property
    def ip(self) -> tuple[int, int] | None:
        """The innermost call's code id and op index."""
        if self.state.frames is None:
            return None
        frame = self.state.frames[0]
        return frame[0], frame[1]

    @property
    def stack(self) -> list[object]:
        """The running calls' code ids, innermost last."""
        codes: list[object] = []
        frames = self.state.frames
        while frames is not None:
            codes.append(frames[0][0])
            frames = frames[1]
        return codes[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Execute one op, reading a byte first if it needs one."""
        frames = self.state.frames
        if frames is None:
            return
        code, pc = frames[0][0], frames[0][1]
        byte = None
        if self.program.codes[code][pc][0] == "in" and not self.state.in_bits:
            byte = self.io.input_char() % 256
        self.state, out = _advance(self.state, self.program, byte)
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    """Run an Object disoriented program from ``main``."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
