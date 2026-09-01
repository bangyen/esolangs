"""Interpreter for A Painter Ant.

A single ant moves over an infinite grid of black or white cells (all black
to start).  The lowercase instructions ``n``/``e``/``s``/``w`` move the ant
one cell in that direction only if the destination cell is black; the
uppercase ``N``/``E``/``S``/``W`` move it only if the destination is white.
``p`` paints the cell under the ant black and ``P`` paints it white.  The
program runs in an implicit loop: after the final instruction, the pointer
returns to the first.

The wiki defines no I/O, so following the repo convention for
interpreter-only languages (Minsky Swap prints its registers), :func:`run`
executes ``cycles`` whole passes of the program and then prints the
bounding box of the cells the ant has visited: a rectangle of ``#`` (white)
and ``.`` (black) cells, one row per line, with the ant's own cell drawn as
``@`` on white or ``o`` on black.  White space is ignored, any other
instruction is a malformed program (:class:`ValueError`, exit 2), and the
origin cell counts as visited.

The glyphs are ink, not colour names: every cell starts black, and ``P`` is
what paints one white, so white is the mark the ant has *made* and gets the
dense character.  A painted structure therefore shows up as ink on a blank
field -- the boolean generator's two leaves read as solid diamonds -- rather
than as scattered gaps in a field of ``#``.

Two details of that output are deliberate.

The unit is a *whole cycle*, not a step count.  The program is an implicit
infinite loop, so there is no halt to run to, and a raw instruction budget
stops wherever it happens to land: the previous default of 10,000
instructions cut the boolean generator's AND2 program at 95.24 cycles,
mid-pass, with the ant somewhere in the middle of its walk.  A whole cycle
is the language's own natural unit, and the programs that have an answer to
report are cycle-stable fixed points -- their grid and the ant's resting
cell are the same after one pass as after ten -- so one cycle is enough and
more changes nothing.  This is a unit, not a safety limit: a program that
diverges runs as long as it is asked to, the way a real interpreter should.

The ant is drawn because otherwise it is invisible.  The raster used to
show painted cells only, which is enough to see *what* the ant drew but not
*where it stopped* -- and for the boolean generator, where it stopped is
the answer (its two leaves are painted rings that look identical, and the
result is which one the ant is resting in).
"""

import sys
from typing import Literal

from esolangs.interpreters.io import IO

# The heading an instruction moves along, as (dx, dy).  The ant's plane is
# an unbounded sparse grid rather than rows of text, so x really is the
# horizontal axis here.  Naming the four keeps a heading distinct from the
# instruction characters that spell it in either case.
_Heading = Literal["n", "e", "s", "w"]

_MOVE: dict[_Heading, tuple[int, int]] = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}

# An instruction is a heading in either case -- lowercase moves onto a
# black cell, uppercase onto a white one -- or a paint.  Deriving the
# validation string from _MOVE keeps it in step with the headings the move
# branch can actually look up.
_INSTRUCTIONS = "".join(h + h.upper() for h in _MOVE) + "pP"

# The same headings keyed by their own spelling, so the move branch
# can turn a parsed character into a _Heading without asserting it.
_HEADING: dict[str, _Heading] = {h: h for h in _MOVE}


class _Machine:
    """Per-run A Painter Ant state.

    Holds the grid, the ant's position, and the implicit-loop instruction
    pointer.  ``step()`` executes one instruction (paint or conditional
    move) and advances the instruction pointer cyclically; ``halted`` is
    always ``False`` because the program runs in an implicit loop forever,
    so the VM and the state-cycle hang detector treat a repeated
    :meth:`snapshot` as the proof of a loop.  Every program the boolean
    generator emits is exactly such a cycle.
    """

    def __init__(
        self,
        code: str,
        io: IO | None = None,  # noqa: ARG002 - see ``run``
    ) -> None:
        """Validate ``code`` and reset the machine to the origin.

        ``io`` is accepted and ignored: the language writes only the final
        render, which :func:`run` prints, and taking the parameter anyway
        lets every caller build a machine the same way.
        """
        self.prog = "".join(c for c in code if not c.isspace())
        for c in self.prog:
            if c not in _INSTRUCTIONS:
                raise ValueError(f"unknown instruction {c!r}")
        self.grid: dict[tuple[int, int], int] = {}
        self.visited: set[tuple[int, int]] = {(0, 0)}
        self.x = self.y = 0
        self.ip = 0

    @property
    def halted(self) -> bool:
        """The implicit loop never halts; only a repeated state proves a loop."""
        return False

    # The VM's language-shaped view: 2D grid; ip is the instruction cursor, memory the
    # cell colours.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for _, v in sorted(self.grid.items())]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (frozenset(self.grid.items()), self.x, self.y, self.ip)

    def step(self) -> None:
        """Execute one instruction, advancing the pointer cyclically."""
        # ``run`` steps ``cycles * len(prog)`` times, so an empty program is
        # never stepped at all; this keeps a direct caller from indexing it.
        if not self.prog:  # pragma: no cover - run() never steps an empty program
            return
        command = self.prog[self.ip]
        if command == "p":
            self.grid[(self.x, self.y)] = 0
        elif command == "P":
            self.grid[(self.x, self.y)] = 1
        else:
            # Not a move command at all unless the lowercased character is
            # one of the four headings, which is what the lookup requires.
            heading = _HEADING.get(command.lower())
            if heading is None:  # pragma: no cover - _INSTRUCTIONS admits no other
                raise ValueError(f"unknown command {command!r}")
            dx, dy = _MOVE[heading]
            target = self.grid.get((self.x + dx, self.y + dy), 0)
            if (target == 1) == command.isupper():
                self.x += dx
                self.y += dy
                self.visited.add((self.x, self.y))
        self.ip = (self.ip + 1) % len(self.prog)

    def render(self) -> str:
        """Render the visited bounding box, marking the ant's cell.

        Four glyphs, one per (cell colour, ant present) pair: ``#`` white
        and ``.`` black, with the ant's own cell as ``@`` on white or ``o``
        on black.  Density tracks the colour in both pairs -- ``#`` and
        ``@`` are the dense ones -- and both ant glyphs are round, so the
        ant reads as one thing at a glance while its colour stays legible.
        """
        min_x = min(vx for vx, _ in self.visited)
        max_x = max(vx for vx, _ in self.visited)
        min_y = min(vy for _, vy in self.visited)
        max_y = max(vy for _, vy in self.visited)
        return "\n".join(
            "".join(self._glyph(xx, yy) for xx in range(min_x, max_x + 1))
            for yy in range(min_y, max_y + 1)
        )

    def _glyph(self, xx: int, yy: int) -> str:
        """Return one cell's character: its colour, and whether the ant is on it."""
        white = self.grid.get((xx, yy), 0) == 1
        if (xx, yy) == (self.x, self.y):
            return "@" if white else "o"
        return "#" if white else "."


def run(code: str, io: IO, cycles: int = 1) -> None:
    """Run an A Painter Ant program for ``cycles`` whole passes."""
    machine = _Machine(code)
    for _ in range(cycles * len(machine.prog)):
        machine.step()
    io.print_str(machine.render())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), cycles=int(sys.argv[2]))
            else:
                run(data, IO())
