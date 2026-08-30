"""Interpreter for Dimensional v3.0.

Dimensional v3.0 (the current wiki spec) is a hierarchy of pointers: an
``n``-pointer (n > 1) is an infinite-dimensional pointer whose position
contains an ``(n-1)``-slot, and a ``1``-slot holds an unsigned byte.  The
value is the byte reached by following the chain of pointers from the
selected axis down to level 2.  ``$AXIS`` picks which pointer the move and
loop commands act on; moving a higher pointer selects a fresh lower slot, so
moving away and back to the origin restores the previous tape.

The v3.0 wiki leaves some details open; this interpreter resolves them as
follows (documented choices, not part of any written spec):

* The pointer axis defaults to 2 (the innermost pointer, which addresses
  bytes directly), so ``>0``/``<0`` with no ``$AXIS`` is a linear byte tape.
* ``d`` and ``x`` read a decimal/hexadecimal number from input (like ``,``
  reads a character).
* ``$AXIS`` values below 2 are clamped to 2 (there is no 1-pointer).
* A ``:`` or ``=`` at the end of a program, or a malformed ``=`` literal, is
  a :class:`ValueError`; unmatched ``[``/``]`` or ``{``/``}`` brackets are
  rejected, matching the package's other tape interpreters.
* Cells wrap at 8 bits (unsigned bytes).

Commands: ``>d``/``<d`` move the axis pointer along dimension ``d`` (bare
``>``/``<`` use the value as the dimension), ``+``/``-`` adjust the value,
``:CH``/``=HEX`` set it from the source, ``.`` prints it, ``,``/``d``/``x``
read it from input, ``[``/``]`` loop on it, ``{d``/``}`` loop on the axis
pointer's dimension-``d`` coordinate, ``?d``/``!d`` read/clear it, ``$AXIS``
selects the pointer, and ``*`` toggles comment mode.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from typing import cast

from esolangs.interpreters.io import IO


class _Level:
    """One pointer level: its position plus the slots it can select.

    For level 2 the selected "slot" is the byte value itself; for higher
    levels it is the :class:`_Level` one step down the chain.
    """

    __slots__ = ("level", "pos", "slots")

    def __init__(self, level: int) -> None:
        self.level = level
        self.pos: dict[int, int] = {}
        self.slots: dict[tuple[tuple[int, int], ...], object] = {}

    def key(self) -> tuple[tuple[int, int], ...]:
        return tuple(sorted((k, v) for k, v in self.pos.items() if v))

    def child(self) -> object:
        """Return the structure at the current position (fresh if first visit)."""
        key = self.key()
        child = self.slots.get(key)
        if child is None:
            child = _Level(self.level - 1) if self.level > 2 else 0
            self.slots[key] = child
        return child

    def freeze(self) -> tuple[object, ...]:
        """Return a hashable snapshot of this level's position and slots."""
        return (
            self.key(),
            tuple(
                sorted(
                    (k, v.freeze() if isinstance(v, _Level) else v)
                    for k, v in self.slots.items()
                )
            ),
        )


class _Tape:
    """The pointer hierarchy, current axis, and the byte it addresses.

    Not the steppable machine -- that is :class:`_Machine`, which holds one
    of these.  This is the language's memory: a chain of :class:`_Level`
    pointers, each selecting either the byte (at level 2) or the level
    below it.
    """

    def __init__(self) -> None:
        self.axis = 2
        self.top = _Level(2)

    def node_at(self, level: int) -> _Level:
        """Return the level-``level`` pointer on the current path (growing the top)."""
        while self.top.level < level:
            old = self.top
            env = _Level(old.level + 1)
            env.slots[()] = old  # the origin of the envelope holds the old tape
            self.top = env
        node = self.top
        while node.level > level:
            node = cast(_Level, node.child())
        return node

    def value(self) -> int:
        return cast(int, self.node_at(2).child())

    def set_value(self, value: int) -> None:
        node = self.node_at(2)
        node.slots[node.key()] = value % 256

    def move(self, dim: int, delta: int) -> None:
        node = self.node_at(self.axis)
        node.pos[dim] = node.pos.get(dim, 0) + delta

    def coord(self, dim: int) -> int:
        return self.node_at(self.axis).pos.get(dim, 0)

    def clear(self, dim: int) -> None:
        self.node_at(self.axis).pos.pop(dim, None)


def _matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ignoring comment regions."""
    stack_b: list[int] = []
    stack_c: list[int] = []
    res: dict[int, int] = {}
    comment = False
    for i, char in enumerate(code):
        if comment:
            if char == "*":
                comment = False
            continue
        if char == "*":
            comment = True
        elif char == "[":
            stack_b.append(i)
        elif char == "]":
            if not stack_b:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack_b.pop()
            res[open_i] = i
            res[i] = open_i
        elif char == "{":
            stack_c.append(i)
        elif char == "}":
            if not stack_c:
                raise ValueError(f"unmatched '}}' at position {i}")
            open_i = stack_c.pop()
            res[open_i] = i
            res[i] = open_i
    if stack_b:
        raise ValueError(f"unmatched '[' at position {stack_b[-1]}")
    if stack_c:
        raise ValueError(f"unmatched '{{' at position {stack_c[-1]}")
    return res


def _number(code: str, ind: int, default: int | None) -> tuple[int | None, int]:
    """Parse an optional ``~``-prefixed number at ``ind``; ``None`` if absent."""
    if ind >= len(code):
        return default, ind
    neg = False
    if code[ind] == "~":
        neg = True
        ind += 1
    if ind < len(code) and code[ind].isdigit():
        j = ind
        while j < len(code) and code[j].isdigit():
            j += 1
        dim = int(code[ind:j])
        return (-dim if neg else dim), j
    return default, ind


class _Machine:
    """One Dimensional run: the code position, comment mode, and tape.

    The steppable machine, named as every other interpreter names it, so
    that the class carrying ``step``/``halted``/``snapshot`` is the one a
    reader finds by looking for ``_Machine``.  The pointer hierarchy it
    runs on is :class:`_Tape`.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.m = _matches(code)
        self.tape = _Tape()
        self.ind = 0
        self.comment = False

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.comment,
            self.tape.axis,
            self.tape.top.level,
            self.tape.top.freeze(),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command (or comment character), advancing the position."""
        code = self.code
        tape = self.tape
        c = code[self.ind]
        self.ind += 1
        if self.comment:
            if c == "*":
                self.comment = False
            return
        if c == "*":
            self.comment = True
        elif c == ">":
            dim, self.ind = _number(code, self.ind, None)
            tape.move(tape.value() if dim is None else dim, 1)
        elif c == "<":
            dim, self.ind = _number(code, self.ind, None)
            tape.move(tape.value() if dim is None else dim, -1)
        elif c == "+":
            tape.set_value(tape.value() + 1)
        elif c == "-":
            tape.set_value(tape.value() - 1)
        elif c == ".":
            self.io.print_char(chr(tape.value()))
        elif c == ",":
            tape.set_value(self.io.input_char())
        elif c == "d":
            tape.set_value(self.io.input_num())
        elif c == "x":
            tape.set_value(int(self.io.input_str(), 16))
        elif c == ":":
            if self.ind >= len(code):
                raise ValueError("':' must be followed by a character")
            tape.set_value(ord(code[self.ind]))
            self.ind += 1
        elif c == "=":
            if self.ind + 2 > len(code):
                raise ValueError("'=' must be followed by two hex digits")
            try:
                tape.set_value(int(code[self.ind : self.ind + 2], 16))
            except ValueError as exc:
                raise ValueError(
                    f"invalid hex literal {code[self.ind : self.ind + 2]!r}"
                ) from exc
            self.ind += 2
        elif c == "$":
            axis, self.ind = _number(code, self.ind, 2)
            tape.axis = max(2, axis if axis is not None else 2)
        elif c == "[":
            if tape.value() == 0:
                self.ind = self.m[self.ind - 1] + 1
        elif c == "]":
            self.ind = self.m[self.ind - 1]
        elif c == "{":
            open_i = self.ind - 1
            dim, self.ind = _number(code, self.ind, 0)
            if tape.coord(dim if dim is not None else 0) == 0:
                self.ind = self.m[open_i] + 1
        elif c == "}":
            self.ind = self.m[self.ind - 1]
        elif c == "?":
            dim, self.ind = _number(code, self.ind, 0)
            tape.set_value(tape.coord(dim if dim is not None else 0) % 256)
        elif c == "!":
            dim, self.ind = _number(code, self.ind, 0)
            tape.clear(dim if dim is not None else 0)
        # any other character is not a command and is ignored


def run(code: str, io: IO) -> None:
    """Run a Dimensional v3.0 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
