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


class _Machine:
    """The pointer hierarchy, current axis, and the byte it addresses."""

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


def run(code: str, io: IO) -> None:
    """Run a Dimensional v3.0 program."""
    m = _matches(code)
    machine = _Machine()
    ind = 0
    comment = False

    while ind < len(code):
        c = code[ind]
        ind += 1
        if comment:
            if c == "*":
                comment = False
            continue
        if c == "*":
            comment = True
        elif c == ">":
            dim, ind = _number(code, ind, None)
            machine.move(machine.value() if dim is None else dim, 1)
        elif c == "<":
            dim, ind = _number(code, ind, None)
            machine.move(machine.value() if dim is None else dim, -1)
        elif c == "+":
            machine.set_value(machine.value() + 1)
        elif c == "-":
            machine.set_value(machine.value() - 1)
        elif c == ".":
            io.print_char(chr(machine.value()))
        elif c == ",":
            machine.set_value(io.input_char())
        elif c == "d":
            machine.set_value(io.input_num())
        elif c == "x":
            machine.set_value(int(io.input_str(), 16))
        elif c == ":":
            if ind >= len(code):
                raise ValueError("':' must be followed by a character")
            machine.set_value(ord(code[ind]))
            ind += 1
        elif c == "=":
            if ind + 2 > len(code):
                raise ValueError("'=' must be followed by two hex digits")
            try:
                machine.set_value(int(code[ind : ind + 2], 16))
            except ValueError as exc:
                raise ValueError(
                    f"invalid hex literal {code[ind : ind + 2]!r}"
                ) from exc
            ind += 2
        elif c == "$":
            axis, ind = _number(code, ind, 2)
            machine.axis = max(2, axis if axis is not None else 2)
        elif c == "[":
            if machine.value() == 0:
                ind = m[ind - 1] + 1
        elif c == "]":
            ind = m[ind - 1]
        elif c == "{":
            open_i = ind - 1
            dim, ind = _number(code, ind, 0)
            if machine.coord(dim if dim is not None else 0) == 0:
                ind = m[open_i] + 1
        elif c == "}":
            ind = m[ind - 1]
        elif c == "?":
            dim, ind = _number(code, ind, 0)
            machine.set_value(machine.coord(dim if dim is not None else 0) % 256)
        elif c == "!":
            dim, ind = _number(code, ind, 0)
            machine.clear(dim if dim is not None else 0)
        # any other character is not a command and is ignored


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
