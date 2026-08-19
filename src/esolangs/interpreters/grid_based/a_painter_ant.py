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
executes ``limit`` instructions and then prints the
bounding box of the cells the ant has visited: a rectangle of ``#`` (black)
and ``.`` (white) cells, one row per line.  White space is ignored, any
other instruction is a malformed program (:class:`ValueError`, exit 2), and
the origin cell counts as visited.
"""

import sys

from esolangs.interpreters.io import IO

_MOVE = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}
_INSTRUCTIONS = "nNeEsSwWpP"


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

    def __init__(self, code: str) -> None:
        """Validate ``code`` and reset the machine to the origin."""
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

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (frozenset(self.grid.items()), self.x, self.y, self.ip)

    def step(self) -> None:
        """Execute one instruction, advancing the pointer cyclically."""
        if not self.prog:
            return
        command = self.prog[self.ip]
        if command == "p":
            self.grid[(self.x, self.y)] = 0
        elif command == "P":
            self.grid[(self.x, self.y)] = 1
        else:
            dx, dy = _MOVE[command.lower()]
            target = self.grid.get((self.x + dx, self.y + dy), 0)
            if (target == 1) == command.isupper():
                self.x += dx
                self.y += dy
                self.visited.add((self.x, self.y))
        self.ip = (self.ip + 1) % len(self.prog)

    def render(self) -> str:
        """Render the visited bounding box as a ``#``/``.`` raster."""
        min_x = min(vx for vx, _ in self.visited)
        max_x = max(vx for vx, _ in self.visited)
        min_y = min(vy for _, vy in self.visited)
        max_y = max(vy for _, vy in self.visited)
        return "\n".join(
            "".join(
                "." if self.grid.get((xx, yy), 0) == 1 else "#"
                for xx in range(min_x, max_x + 1)
            )
            for yy in range(min_y, max_y + 1)
        )


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an A Painter Ant program for ``limit`` instructions."""
    machine = _Machine(code)
    for _ in range(limit):
        machine.step()
    io.print_line(machine.render())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
