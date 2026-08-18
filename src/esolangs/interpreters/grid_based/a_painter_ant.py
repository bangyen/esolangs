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
from itertools import cycle, islice

from esolangs.interpreters.io import IO

_MOVE = {
    "n": (0, -1),
    "e": (1, 0),
    "s": (0, 1),
    "w": (-1, 0),
}
_INSTRUCTIONS = "nNeEsSwWpP"


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an A Painter Ant program for ``limit`` instructions."""
    prog = "".join(c for c in code if not c.isspace())
    for c in prog:
        if c not in _INSTRUCTIONS:
            raise ValueError(f"unknown instruction {c!r}")

    grid: dict[tuple[int, int], int] = {}
    x = y = 0
    visited = {(x, y)}

    for c in islice(cycle(prog), limit):
        if c == "p":
            grid[(x, y)] = 0
        elif c == "P":
            grid[(x, y)] = 1
        else:
            dx, dy = _MOVE[c.lower()]
            target = grid.get((x + dx, y + dy), 0)
            want = c.isupper()
            if (target == 1) == want:
                x += dx
                y += dy
                visited.add((x, y))

    min_x = min(vx for vx, _ in visited)
    max_x = max(vx for vx, _ in visited)
    min_y = min(vy for _, vy in visited)
    max_y = max(vy for _, vy in visited)
    rows = [
        "".join(
            "." if grid.get((xx, yy), 0) == 1 else "#" for xx in range(min_x, max_x + 1)
        )
        for yy in range(min_y, max_y + 1)
    ]
    io.print_line("\n".join(rows))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
