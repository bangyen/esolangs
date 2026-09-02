"""Interpreter for 3D Brainfuck.

A brainfuck variant whose memory array is a three-dimensional grid of byte
cells (wrapping 0-255) and whose blocks are placed on a three-dimensional
grid.  ``+``/``-``/``.``/``,`` operate on the array cell at the array
pointer; ``n``/``s``/``e``/``w``/``u``/``d`` move the array pointer along the
six axes; ``N``/``S``/``E``/``W``/``U``/``D`` set the instruction pointer's
heading; ``^``/``V``/``>``/``<``/``"``/``'`` set the generation pointer's
heading; and ``[``/``]`` loop on the array cell, matched by nesting over the
source like brainfuck.

The wiki (``esolangs.org/wiki/3D_Brainfuck``) specifies the instruction set
but not how blocks are initially placed or what the generation pointer emits.
Documented decisions filling those gaps:
- the source is a straight line of blocks along +X, block ``i`` at (i, 0, 0);
- the instruction pointer starts at (0, 0, 0) heading +X, executes the block
  at its cell, then advances one cell in its heading; moving onto a cell with
  no block halts the program;
- a heading block (``N``/``S``/``E``/``W``/``U``/``D``) only changes the
  heading; a heading other than +X immediately walks the pointer off the
  source line and halts;
- the array grid is unbounded, cells are created on demand and wrap 0-255;
- no blocks are ever emitted (the wiki's generation semantics are
  unspecified), so the generation pointer has no observable state and is not
  modelled: ``^``/``V``/``>``/``<``/``"``/``'`` are no-ops like any other
  non-command character, which is a comment;
- ``,`` raises :class:`EOFError` when input runs out (repo-wide convention);
  an unbalanced bracket pair is malformed (:class:`ValueError`).

The interpreter runs on a :class:`_Machine` (the block grid, the array
cells, and the two pointers), so it is step-capable: ``step()`` executes one
block and ``halted`` is true once the instruction pointer leaves the source
line.  A loop that returns to an exact state (e.g. a bracket pair around a
cell that wraps) is a cycle the state-cycle hang detector proves; the
``run()`` backstop stays for the unbounded-growth class (a loop whose body
keeps growing the array).
"""

import sys

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


def _advance(point: _Point, delta: _Point) -> _Point:
    """Return ``point`` moved by ``delta``, one component at a time.

    Both pointers move this way, so they share it.  Spelled out at each site
    the sum names ``[0]``, ``[1]`` and ``[2]`` explicitly -- and the
    instruction pointer never leaves the ``y = z = 0`` line alive, since a
    heading block walks it off the source and halts it, so a site that read
    the wrong one of those two behaved identically and nothing could tell.
    Unpacking both triples names each component once instead.
    """
    x, y, z = point
    dx, dy, dz = delta
    return (x + dx, y + dy, z + dz)


class _Machine:
    """Per-run 3D Brainfuck state: the blocks, the array, and the pointers.

    ``step()`` executes one block; ``halted`` is true once the instruction
    pointer leaves the source line.  The VM and the state-cycle hang detector
    expose this object.
    """

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

    @property
    def ip(self) -> tuple[int, ...]:
        """The instruction pointer's position and heading, flattened.

        Where the pointer is does not say where it goes next: the heading
        is a separate 3D vector, and a breakpoint on a position alone would
        match the same cell entered from six directions.
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

    def step(self) -> None:
        """Execute one block, moving the instruction pointer."""
        if self.halted:
            return
        char = self.grid[self.pos]
        if char in _HEADING:
            self.heading = _HEADING[char]
        elif char in _ARRAY:
            self.ap = _advance(self.ap, _ARRAY[char])
        elif char in "+-.,":
            if char == "+":
                self.cells[self.ap] = (self.cells.get(self.ap, 0) + 1) % 256
            elif char == "-":
                self.cells[self.ap] = (self.cells.get(self.ap, 0) - 1) % 256
            elif char == ".":
                self.io.print_char(chr(self.cells.get(self.ap, 0)))
            else:
                self.cells[self.ap] = self.io.input_char()
        elif char == "[":
            if self.cells.get(self.ap, 0) == 0:
                self.pos = (self.m[self.pos[0]] + 1, 0, 0)
                return
        elif char == "]" and self.cells.get(self.ap, 0) != 0:
            self.pos = (self.m[self.pos[0]] + 1, 0, 0)
            return
        self.pos = _advance(self.pos, self.heading)


def run(code: str, io: IO) -> None:
    """Run a 3D Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
