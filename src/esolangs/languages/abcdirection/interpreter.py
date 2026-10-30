"""Interpreter for ABCDirection.

A pointer walks a rectangular grid of ``A``/``B``/``C``/``D`` cells,
starting at the top-left cell headed down; after each command it steps one
cell in its heading.  The tape is an unbounded bit tape and the queue a
FIFO of bits.  The file reader stops after the first line containing
``DDDDDD``; that line is read whole, so the grid is every line up to it.
Later lines are comments.

No command halts, so the machine halts itself once its state provably
repeats with no output, input, or memory write in between: from there it
loops forever and changes nothing observable.  Brent's algorithm over an
O(1) key (pointer, heading, tape position, write count), restarted at
every write, finds that repeat a few steps into the loop.  A write is a
real change: a tape bit taking a new value, an enqueue, a dequeue from a
non-empty queue, a bit output, or an input bit consumed; rewriting the bit
already there, dequeuing an empty queue and reading at EOF are not.  A program that
keeps printing, or keeps writing new state, runs until the caller's
budget stops it.

Commands:
    ``A``: turn the pointer right (clockwise).
    ``B``: no-op.
    ``C`` right: move the tape pointer left.
    ``C`` left: move the tape pointer right and flip the bit there.
    ``C`` up: if the bit is 1, turn left; otherwise go straight.
    ``C`` down: output the bit.
    ``D`` right: enqueue the bit.
    ``D`` left: dequeue into the bit.
    ``D`` up: input into the bit.
    ``D`` down: a 1 bit goes straight on; otherwise dequeue, and a 1 turns
    up; otherwise dequeue again, and a 0 turns left, a 1 right.

Input/output:
    Bitwise: bytes leave and arrive eight bits at a time, least significant
    first, and EOF supplies zero bits.

Errors:
    ProgramError: the grid before the ``DDDDDD`` line is not a rectangle of
    ``A``/``B``/``C``/``D``, or no line contains ``DDDDDD`` (exit 2).

Decisions:
    * The wiki leaves four gaps and suggests each assumption taken here, in
      its "Computational class" section: the edges wrap (a donut, without
      which a program never leaves the leftmost column), the tape starts at
      zero, and an empty queue dequeues zeros.
    * A ``D`` down dequeues the bit it tests ("the front of the queue" read
      as the value just dequeued): under a peek reading its second dequeue
      would always take a 0, and "dequeued is 1, turn right" could never
      fire.
"""

from collections import deque
from typing import NamedTuple

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.bits import put_bit, take_bit
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

# Clockwise from right: turning right is +1, turning left -1.
_STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))
RIGHT, DOWN, LEFT, UP = range(4)

_TERMINATOR = "DDDDDD"

# Deletes every command, so ``row.translate(_STRIP)`` is non-empty exactly
# when the row holds anything else: one C-level pass per row.
_STRIP = str.maketrans("", "", "ABCD")


def _parse(code: str) -> tuple[str, ...]:
    """Return the grid: every line through the first one holding ``DDDDDD``."""
    lines = code.splitlines()
    for index, line in enumerate(lines):
        if _TERMINATOR in line:
            rows = tuple(lines[: index + 1])
            if any(len(row) != len(line) for row in rows):
                raise syntax_error(
                    "program is not a rectangle",
                    "pad every row with B to the width of the DDDDDD line",
                )
            if any(row.translate(_STRIP) for row in rows):
                raise syntax_error(
                    "program must contain only A, B, C, D",
                    "use B where a cell should do nothing",
                )
            return rows
    raise syntax_error(
        "program must contain a line with DDDDDD",
        "end the program with a line holding six consecutive D's",
    )


class _State(NamedTuple):
    """The pointer: grid position, heading, and tape position."""

    x: int
    y: int
    heading: int
    cell: int


class _Effect(NamedTuple):
    """What one command does outside the pointer, for the shell to apply."""

    #: ``(cell, bit)`` to store on the tape.
    write: tuple[int, int] | None = None
    #: How many bits to dequeue (an empty queue yields 0 and stays empty).
    pops: int = 0
    #: A bit to enqueue.
    push: int | None = None
    #: A bit to output.
    emit: int | None = None


_NOTHING = _Effect()


def _advance(
    state: _State,
    grid: tuple[str, ...],
    here: int,
    right: int,
    queue: tuple[int, int],
    read: int | None,
) -> tuple[_State, _Effect]:
    """Return the pointer after one command, and what the command does.

    Pure: ``here`` and ``right`` are the bits at the tape position and one
    right of it, ``queue`` the queue's first two bits (0 past its end), and
    ``read`` the input bit a ``D`` up consumes, read by the shell first.
    """
    x, y, heading, cell = state
    command = grid[y][x]
    effect = _NOTHING
    if command == "A":
        heading = (heading + 1) % 4
    elif command == "C":
        if heading == RIGHT:
            cell -= 1
        elif heading == LEFT:
            cell += 1
            effect = _Effect(write=(cell, 1 - right))
        elif heading == UP:
            if here:
                heading = LEFT
        else:
            effect = _Effect(emit=here)
    elif command == "D":
        if heading == RIGHT:
            effect = _Effect(push=here)
        elif heading == LEFT:
            effect = _Effect(write=(cell, queue[0]), pops=1)
        elif heading == UP:
            effect = _Effect(write=(cell, read or 0))
        elif not here:
            if queue[0]:
                heading, effect = UP, _Effect(pops=1)
            else:
                heading = RIGHT if queue[1] else LEFT
                effect = _Effect(pops=2)
    dx, dy = _STEPS[heading]
    width, height = len(grid[0]), len(grid)
    return _State((x + dx) % width, (y + dy) % height, heading, cell), effect


class _Machine:
    """Per-run ABCDirection state: grid, tape, queue, I/O buffers, pointer."""

    ip_shape = "grid"

    #: Input supplies zero bits once it runs out.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` and start at the top-left cell, headed down."""
        self.io = io
        self.grid = _parse(code)
        self.state = _State(0, 0, DOWN, 0)
        self.ones: set[int] = set()
        self._view: tuple[int, tuple[int, ...]] | None = None
        self.queue: deque[int] = deque()
        self.incoming = (0, 0)
        self.outgoing = (0, 0)
        # Bumped by every write outside the pointer, so equal ``key``\\ s at
        # two times mean equal states: the repeat test costs O(1), not O(tape).
        self.writes = 0
        self.tortoise = self.key
        self.power = self.length = 1
        self._halted = False

    @property
    def halted(self) -> bool:
        """Whether the state has provably repeated with nothing written."""
        return self._halted

    @property
    def ip(self) -> tuple[int, int, int]:
        """Row, column, then heading (0 right, 1 down, 2 left, 3 up)."""
        return (self.state.y, self.state.x, self.state.heading)

    @property
    def memory(self) -> list[int]:
        """The tape from its lowest to highest touched cell."""
        cell = self.state.cell
        lo = min(self.ones | {cell, 0})
        hi = max(self.ones | {cell, 0})
        return [int(i in self.ones) for i in range(lo, hi + 1)]

    @property
    def key(self) -> tuple[_State, int]:
        """The O(1) stand-in for the state that the repeat test compares."""
        return (self.state, self.writes)

    def _tape(self) -> tuple[int, tuple[int, ...]]:
        """Return the tape as its lowest 1 and the bits up to its highest.

        One bit a cell, where the set of 1s' addresses is ``T log T``;
        rebuilt only after a write, so a snapshot per step costs O(1) once
        the table is written.
        """
        if self._view is None:
            lo = min(self.ones, default=0)
            hi = max(self.ones, default=-1)
            self._view = (lo, tuple(int(i in self.ones) for i in range(lo, hi + 1)))
        return self._view

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.state,
            self._tape(),
            tuple(self.queue),
            self.incoming,
            self.outgoing,
            self.io.progress(),
            self.tortoise,
            self.power,
            self.length,
            self._halted,
        )

    def _read(self) -> int:
        """Return the next input bit; EOF supplies zeros without state."""
        incoming, remaining = self.incoming
        if not remaining:
            try:
                incoming = self.io.input_char() % 256
            except EOFError:
                return 0
            remaining = 8
        self.writes += 1
        self.incoming, bit = take_bit((incoming, remaining))
        return bit

    def _apply(self, effect: _Effect) -> None:
        """Perform a command's effects, counting each real change."""
        if effect.write is not None:
            cell, bit = effect.write
            if bit != (cell in self.ones):
                self.writes += 1
                self.ones.symmetric_difference_update((cell,))
                self._view = None
        for _ in range(min(effect.pops, len(self.queue))):
            self.writes += 1
            self.queue.popleft()
        if effect.push is not None:
            self.writes += 1
            self.queue.append(effect.push)
        if effect.emit is not None:
            self.writes += 1
            self.outgoing, full = put_bit(self.outgoing, effect.emit)
            if full is not None:
                self.io.print_char(chr(full))

    def step(self) -> None:
        """Execute the current cell's command, then step one cell."""
        if self._halted:
            return
        x, y, heading, cell = self.state
        read = self._read() if self.grid[y][x] == "D" and heading == UP else None
        size = len(self.queue)
        queue = (self.queue[0] if size else 0, self.queue[1] if size > 1 else 0)
        here = int(cell in self.ones)
        right = int(cell + 1 in self.ones)
        writes = self.writes
        self.state, effect = _advance(self.state, self.grid, here, right, queue, read)
        self._apply(effect)
        # Brent's, restarted at every write: only a write-free stretch repeats.
        if self.writes != writes:
            self.tortoise, self.power, self.length = self.key, 1, 1
        elif self.key == self.tortoise:
            self._halted = True
        elif self.length == self.power:
            self.tortoise, self.power, self.length = self.key, 2 * self.power, 1
        else:
            self.length += 1


def run(code: str, io: IO) -> None:
    """Run an ABCDirection program until it provably repeats in silence."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
