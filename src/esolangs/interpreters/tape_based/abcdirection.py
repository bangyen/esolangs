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
- since the pointer never leaves a donut, no program stops on its own — the
  wiki has no halt instruction, so the run is capped at ``limit`` executed
  commands and :func:`run` returns there rather than raising.  Reaching the
  cap is how an ABCDirection program ends, not a failure to report, the
  same reading A Painter Ant's implicit loop and Suffolk's infinite rerun
  already get;
- rows shorter than the final line's grid width are a malformed program
  (:class:`ValueError`, exit 2), and longer rows are trimmed to that width;
- exhausted input raises :class:`EOFError` (repo-wide convention), and an
  empty input line raises :class:`IndexError` through
  :meth:`esolangs.interpreters.io.IO.input_char`.

The interpreter runs on a :class:`_Machine` (the grid, tape, queue, code
pointer, and step count), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once ``limit`` steps have run.  Nothing on
the donut grid ever sets ``halted`` early, so it marks the step limit and
nothing else.  :meth:`_Machine.snapshot` still reports the complete state,
so ``esolangs.vm.run_until_halt_or_cycle`` can prove one of these loops for
a caller that wants that -- the hanging tests do -- without :func:`run`
itself depending on it.
"""

from collections import deque

from esolangs.interpreters.io import IO
from esolangs.interpreters.oisc_cli import main_with_limit, run_until_halt

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


class _Machine:
    """Per-run ABCDirection state: the grid, tape, queue, and cursor."""

    def __init__(self, code: str, io: IO, limit: int = 10_000) -> None:
        """Parse ``code``'s grid and start the pointer at the top-left cell."""
        self.io = io
        self.limit = limit
        self.grid = _parse(code)
        self.width = len(self.grid[0])
        self.height = len(self.grid)

        self.tape: dict[int, int] = {}
        self.cell = 0
        self.queue: deque[int] = deque()
        self.out_bits: list[int] = []
        self.in_bits: list[int] = []

        self.x = self.y = 0
        self.d = DOWN
        self.steps = 0

    @property
    def halted(self) -> bool:
        """Whether ``limit`` steps have run.

        The pointer never leaves the donut grid, so this is the only way
        the machine stops.
        """
        return self.steps >= self.limit

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``io.position()`` is part of the state: without it a beam that loops
        through a ``D``-up repeats its machine state every lap while the
        input stream advances, and the detector calls that a hang after
        reading only the first few bytes -- a verdict that is wrong for any
        stream whose later bytes would have steered the beam elsewhere.
        """
        return (
            self.x,
            self.y,
            self.d,
            self.cell,
            tuple(sorted(self.tape.items())),
            tuple(self.queue),
            tuple(self.out_bits),
            tuple(self.in_bits),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, then advance the pointer along the grid."""
        if self.halted:
            return
        c = self.grid[self.y][self.x]
        if c == "A":
            self.d = (self.d + 1) % 4
        elif c == "C":
            if self.d == RIGHT:
                self.cell -= 1
            elif self.d == LEFT:
                self.cell += 1
                self.tape[self.cell] = self.tape.get(self.cell, 0) ^ 1
            elif self.d == UP:
                if self.tape.get(self.cell, 0):
                    self.d = (self.d - 1) % 4
            elif self.d == DOWN:
                self.out_bits.append(self.tape.get(self.cell, 0))
                if len(self.out_bits) == 8:
                    bits = self.out_bits
                    self.io.print_char(chr(sum(b << i for i, b in enumerate(bits))))
                    self.out_bits = []
        elif c == "D":
            if self.d == RIGHT:
                self.queue.append(self.tape.get(self.cell, 0))
            elif self.d == LEFT:
                self.tape[self.cell] = self.queue.popleft() if self.queue else 0
            elif self.d == UP:
                if not self.in_bits:
                    byte = self.io.input_char()
                    self.in_bits = [(byte >> i) & 1 for i in range(8)]
                self.tape[self.cell] = self.in_bits.pop(0)
            elif self.d == DOWN:
                if self.tape.get(self.cell, 0):
                    self.d = DOWN
                elif self.queue.popleft() if self.queue else 0:
                    self.d = UP
                elif self.queue.popleft() if self.queue else 0:
                    self.d = RIGHT
                else:
                    self.d = LEFT

        self.x = (self.x + _DIRS[self.d][0]) % self.width
        self.y = (self.y + _DIRS[self.d][1]) % self.height
        self.steps += 1


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an ABCDirection program for at most ``limit`` commands.

    The language has no halt instruction and the pointer never leaves the
    donut grid, so reaching the limit is how every program ends rather than
    a failure to report: a program does its work and then circles.  This
    follows A Painter Ant and Suffolk, whose specifications also loop
    forever and whose interpreters run a bounded budget and return.
    """
    run_until_halt(_Machine(code, io, limit))


if __name__ == "__main__":
    main_with_limit(run)
