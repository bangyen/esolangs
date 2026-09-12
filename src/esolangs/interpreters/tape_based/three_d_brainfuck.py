r"""Interpreter for 3D Brainfuck."""

import sys
from collections.abc import Mapping

from esolangs.interpreters.brackets import match_brackets as _matches
from esolangs.interpreters.io import IO

_HEADING = {
    "N": (1, 0, 0),
    "S": (-1, 0, 0),
    "E": (0, 0, 1),
    "W": (0, 0, -1),
    "U": (0, 1, 0),
    "D": (0, -1, 0),
}
_ARRAY = {
    "n": (1, 0, 0),
    "s": (-1, 0, 0),
    "e": (0, 0, 1),
    "w": (0, 0, -1),
    "u": (0, 1, 0),
    "d": (0, -1, 0),
}
_Point = tuple[int, int, int]


def _moved(point: _Point, delta: _Point) -> _Point:
    r"""Return ``point`` moved by ``delta``, one component at a time."""
    x, y, z = point
    dx, dy, dz = delta
    return (x + dx, y + dy, z + dz)


# : One instant of a run:.
# : map, the array pointer, the.
# : instruction pointer is.
# :.
# : The heading is state.
# : an uppercase.
# : which is what makes the.
#: line of text.
# :.
# : The grid and its bracket.
# : its own source -- so a step.
type _Cells = dict[_Point, int]
type _State = tuple[_Cells, _Point, _Point, _Point]


def _advance(
    state: _State,
    grid: Mapping[_Point, str],
    match: Mapping[int, int],
    byte: int | None = None,
) -> _State:
    r"""Return the state after executing the block under the pointer."""
    cells, ap, pos, heading = state
    char = grid[pos]

    if char in _HEADING:
        heading = _HEADING[char]
    elif char in _ARRAY:
        ap = _moved(ap, _ARRAY[char])
    elif char == "+":
        cells = {**cells, ap: (cells.get(ap, 0) + 1) % 256}
    elif char == "-":
        cells = {**cells, ap: (cells.get(ap, 0) - 1) % 256}
    elif char == ".":
        pass  # printed by the caller; the.
    elif char == ",":
        cells = {**cells, ap: byte if byte is not None else 0}
    elif char == "[":
        if cells.get(ap, 0) == 0:
            return (cells, ap, (match[pos[0]] + 1, 0, 0), heading)
    elif char == "]" and cells.get(ap, 0) != 0:
        return (cells, ap, (match[pos[0]] + 1, 0, 0), heading)

    return (cells, ap, _moved(pos, heading), heading)


class _Machine:
    r"""Per-run 3D Brainfuck state: the blocks, the array, and the pointers."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Lay the blocks along +X and start the pointers at the origin."""
        self.io = io
        self.grid = {(i, 0, 0): char for i, char in enumerate(code)}
        self.m = _matches(code)
        self.cells: dict[tuple[int, int, int], int] = {}
        self.ap = (0, 0, 0)
        self.pos = (0, 0, 0)
        self.heading = (1, 0, 0)

    @property
    def halted(self) -> bool:
        r"""Whether the instruction pointer has left the source line."""
        return self.pos not in self.grid

    # The VM's language-shaped view.
    # ``pos`` -- the name LaserFuck.
    # here is the position *and*.
    # ``ap`` keeps its own name: it.

    # : ``ip`` is a position, but.
    #: heading.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The instruction pointer's position and heading, flattened."""
        return (*self.pos, *self.heading)

    @property
    def memory(self) -> list[int]:
        r"""The cells that have been touched, in address order."""
        return [v for _, v in sorted(self.cells.items())]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted(self.cells.items())),
            self.ap,
            self.pos,
            self.heading,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.cells, self.ap, self.pos, self.heading)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        cells, self.ap, self.pos, self.heading = state
        self.cells = cells

    def step(self) -> None:
        r"""Execute one block, moving the instruction pointer."""
        if self.halted:
            return
        char = self.grid[self.pos]

        byte = None
        if char == ".":
            self.io.print_char(chr(self.cells.get(self.ap, 0)))
        elif char == ",":
            byte = self.io.input_char()

        self._restore(_advance(self._state, self.grid, self.m, byte))


def run(code: str, io: IO) -> None:
    r"""Run a 3D Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
