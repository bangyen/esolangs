"""Interpreter for 3D Brainfuck.

Byte cells (wrapping 0-255) on a 3D grid, blocks on a 3D grid.
``+``/``-``/``.``/``,`` act on the array cell; ``n``/``s``/``e``/``w``/
``u``/``d`` move the array pointer; ``N``/``S``/``E``/``W``/``U``/``D``
set the instruction pointer's heading; ``[``/``]`` loop, matched over
the source like brainfuck.

Gaps decided (the wiki gives no block placement or generation
semantics): block ``i`` is at (i, 0, 0); the instruction pointer starts
at the origin heading +X, executes, then advances, halting on a cell
with no block; a heading block only changes the heading, so every
heading but +X/-X halts and ``S`` runs back along the line, so a program
can bounce forever; the array is unbounded, created on demand; the
generation pointer is not modelled, so ``^``/``V``/``>``/``<``/``"``/
``'`` are comments; ``,`` raises :class:`EOFError` at end of input and
an unbalanced bracket is :class:`ValueError`.  ``halted`` is true once
the instruction pointer leaves the source line; an exact-state loop is
proved by the hang detector, unbounded growth by the ``run()`` backstop.
"""

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
    """Return ``point`` moved by ``delta``, one component at a time.

    Unpacking both triples names each component once; a site reading the
    wrong index used to behave identically, since the instruction pointer
    never leaves ``y = z = 0`` alive.
    """
    x, y, z = point
    dx, dy, dz = delta
    return (x + dx, y + dy, z + dz)


#: One instant of a run: ``(cells, ap, pos, heading)`` -- the sparse cell
#: map, the array pointer, the instruction pointer, and the direction the
#: instruction pointer is travelling.
#:
#: The heading is state because a turn outlives the command that made it:
#: an uppercase ``N``/``E``/``U`` sets it and every later step follows it,
#: which is what makes the program a path through the grid rather than a
#: line of text.
#:
#: The grid and its bracket table stay out -- 3D Brainfuck never rewrites
#: its own source -- so a step is handed them.
type _Cells = dict[_Point, int]
type _State = tuple[_Cells, _Point, _Point, _Point]


def _advance(
    state: _State,
    grid: Mapping[_Point, str],
    match: Mapping[int, int],
    byte: int | None = None,
) -> _State:
    """Return the state after executing the block under the pointer.

    Pure; ``,``'s byte arrives as ``byte``.  A taken loop lands at the
    start of the line after its partner, since brackets match by *row*.
    """
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
        pass  # printed by the caller; the cell is unchanged
    elif char == ",":
        cells = {**cells, ap: byte if byte is not None else 0}
    elif char == "[":
        if cells.get(ap, 0) == 0:
            return (cells, ap, (match[pos[0]] + 1, 0, 0), heading)
    elif char == "]" and cells.get(ap, 0) != 0:
        return (cells, ap, (match[pos[0]] + 1, 0, 0), heading)

    return (cells, ap, _moved(pos, heading), heading)


class _Machine:
    """Per-run 3D Brainfuck state: the blocks, the array, and the pointers."""

    def __init__(self, code: str, io: IO) -> None:
        """Lay the blocks along +X and start the pointers at the origin."""
        self.io = io
        self.grid = {(i, 0, 0): char for i, char in enumerate(code)}
        self.m = _matches(code)
        self.cells: dict[tuple[int, int, int], int] = {}
        self.ap = (0, 0, 0)
        self.pos = (0, 0, 0)
        self.heading = (1, 0, 0)

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has left the source line."""
        return self.pos not in self.grid

    # The VM's language-shaped view.  The instruction pointer is held as
    # ``pos`` -- the name LaserFuck gives the same thing -- because ``ip``
    # here is the position *and* the heading, and one name cannot be both.
    # ``ap`` keeps its own name: it is the array pointer, not this.

    #: ``ip`` is a position, but not one on the source text: a 3-D point and a 3-D
    #: heading.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """The instruction pointer's position and heading, flattened.

        A position alone would match the same cell from six directions.
        """
        return (*self.pos, *self.heading)

    @property
    def memory(self) -> list[int]:
        """The cells that have been touched, in address order."""
        return [v for _, v in sorted(self.cells.items())]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(sorted(self.cells.items())),
            self.ap,
            self.pos,
            self.heading,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.cells, self.ap, self.pos, self.heading)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        cells, self.ap, self.pos, self.heading = state
        self.cells = cells

    def step(self) -> None:
        """Execute one block, moving the instruction pointer."""
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
    """Run a 3D Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
