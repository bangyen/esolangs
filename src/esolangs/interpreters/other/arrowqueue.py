"""Interpreter for ArrowQueue.

ArrowQueue is a two-dimensional, queue-based tarpit inspired by Re:direction.
The Instruction Pointer (IP) walks a grid; ``*`` turns it clockwise, ``~``
pushes the current direction onto a queue, and ``+`` pops the queue and
points the IP in the popped direction.  All other characters are no-ops.
The program halts when ``+`` pops an empty queue or the IP moves off the
grid.

Decisions for gaps in the wiki spec (documented):
- the IP starts in the top-left corner moving right, matching Re:direction
  (the wiki is silent on both);
- clockwise order is right, down, left, up (screen coordinates), so turning
  is ``(dir + 1) % 4``;
- the grid is padded to a rectangle as wide as the longest line, which is
  how the wiki's examples lay out wide rows; an IP that leaves the
  rectangle has moved out of bounds and halts the program.
"""

import sys

from esolangs.interpreters.io import IO

DELTA = [(1, 0), (0, 1), (-1, 0), (0, -1)]


def run(code: list[str], _io: IO) -> None:
    """Run an ArrowQueue program, halting on an empty-queue pop or off-grid."""
    if not code:
        return
    width = max(len(line) for line in code)
    grid = [line.ljust(width) for line in code]
    x = y = d = 0
    queue: list[int] = []

    while True:
        if not 0 <= x < width or not 0 <= y < len(grid):
            return
        cell = grid[y][x]
        if cell == "*":
            d = (d + 1) % 4
        elif cell == "~":
            queue.append(d)
        elif cell == "+":
            if not queue:
                return
            d = queue.pop(0)
        dx, dy = DELTA[d]
        x += dx
        y += dy


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
