r"""Interpreter for ABCDirection.

A pointer travels a rectangular grid of ``A``/``B``/``C``/``D`` cells,
starting at the top-left cell headed down.  ``A`` turns the code pointer
right (clockwise), ``B`` is a no-op, and ``C`` and ``D`` dispatch on the
current code direction:

- ``C`` right: move the tape pointer left.
- ``C`` left: move the tape pointer right and flip the bit.
- ``C`` up: if the bit at the tape pointer is 1, turn the code pointer left.
- ``C`` down: output the bit like Boolfuck.
- ``D`` right: enqueue the bit at the tape pointer into the queue.
- ``D`` left: dequeue a bit into the tape cell.
- ``D`` up: input a bit like Boolfuck.
- ``D`` down: if the cell is 1 go straight (down); otherwise dequeue — a 1
  turns the code pointer up, a 0 dequeues again, a second 0 turns left and a
  second 1 turns right.

The tape is an unbounded Boolfuck-style bit tape (all cells start 0), the
queue is a FIFO of bits, and Boolfuck I/O is little-endian: the output bits
are grouped eight at a time into bytes LSB-first, and input supplies a
byte's eight bits LSB-first.  The source file is a rectangle of ``A``/``B``/
``C``/``D`` that ends at the first run of six consecutive ``D``\ s, which
terminates the file reader; anything after that run on the line is a
comment.

Documented decisions for gaps the wiki leaves undefined (the author suggests
each of these assumptions in the "Computational class" section):

- the grid edges are connected, so the code pointer wraps around the grid as
  a donut (needed to reach anywhere but the leftmost column);
- the queue is treated as containing zeros when it is empty;
- the tape is initialized to zeros;
- since the pointer never leaves a donut, every program runs forever; the
  interpreter stops after ``limit`` executed commands with
  :class:`HaltError` (exit 3) — the wiki has no halt instruction;
- rows shorter than the final line's grid width are a malformed program
  (:class:`ValueError`, exit 2), and longer rows are trimmed to that width;
- exhausted input raises :class:`EOFError` (repo-wide convention), and an
  empty input line raises :class:`IndexError` through
  :meth:`esolangs.interpreters.io.IO.input_char`.
"""

import sys
from collections import deque

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# Clockwise order: right, down, left, up — turn right is +1, turn left is -1.
_DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
RIGHT, DOWN, LEFT, UP = 0, 1, 2, 3

_TERMINATOR = "DDDDDD"

# Deletes every valid command character, so ``row.translate(_STRIP)`` is
# non-empty exactly when the row contains a character outside ABCD (far
# faster than a per-character scan for the multi-megabyte generated grids).
_STRIP = str.maketrans("", "", "ABCD")


def _parse(code: str) -> list[str]:
    """Split ``code`` into the program's grid of rows."""
    lines = code.splitlines()
    for index, line in enumerate(lines):
        pos = line.find(_TERMINATOR)
        if pos != -1:
            width = pos + len(_TERMINATOR)
            rows = [ln[:width] for ln in lines[: index + 1]]
            if any(len(ln) < width for ln in rows):
                raise ValueError("program is not a rectangle")
            if any(ln.translate(_STRIP) for ln in rows):
                raise ValueError("program must contain only A, B, C, D")
            return rows
    raise ValueError("program must contain a line with DDDDDD")


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an ABCDirection program, halting after ``limit`` commands."""
    grid = _parse(code)
    width = len(grid[0])
    height = len(grid)

    tape: dict[int, int] = {}
    cell = 0
    queue: deque[int] = deque()
    out_bits: list[int] = []
    in_bits: list[int] = []

    x = y = 0
    d = DOWN
    steps = 0

    while steps < limit:
        c = grid[y][x]
        if c == "A":
            d = (d + 1) % 4
        elif c == "C":
            if d == RIGHT:
                cell -= 1
            elif d == LEFT:
                cell += 1
                tape[cell] = tape.get(cell, 0) ^ 1
            elif d == UP:
                if tape.get(cell, 0):
                    d = (d - 1) % 4
            elif d == DOWN:
                out_bits.append(tape.get(cell, 0))
                if len(out_bits) == 8:
                    io.print_char(chr(sum(b << i for i, b in enumerate(out_bits))))
                    out_bits = []
        elif c == "D":
            if d == RIGHT:
                queue.append(tape.get(cell, 0))
            elif d == LEFT:
                tape[cell] = queue.popleft() if queue else 0
            elif d == UP:
                if not in_bits:
                    byte = io.input_char()
                    in_bits = [(byte >> i) & 1 for i in range(8)]
                tape[cell] = in_bits.pop(0)
            elif d == DOWN:
                if tape.get(cell, 0):
                    d = DOWN
                elif queue.popleft() if queue else 0:
                    d = UP
                elif queue.popleft() if queue else 0:
                    d = RIGHT
                else:
                    d = LEFT

        x = (x + _DIRS[d][0]) % width
        y = (y + _DIRS[d][1]) % height
        steps += 1

    raise HaltError(f"execution exceeded the {limit}-command limit")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
