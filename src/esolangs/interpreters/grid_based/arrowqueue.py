"""Interpreter for ArrowQueue.

A 2D queue-based tarpit after Re:direction: ``*`` turns the IP clockwise,
``~`` pushes the current direction, ``+`` pops and points the IP that way;
the program halts on an empty pop or off the grid.  Decisions: the IP
starts top-left moving right; clockwise is right, down, left, up; the
grid is padded to the longest line, and leaving it halts.  No I/O, so
:func:`_advance` is pure and total; the halted flag is *in* the state
(an empty pop stops the run with the IP still on the grid).  The one
effect is the end-of-run queue dump in :func:`run`.
"""

from __future__ import annotations

from collections.abc import Sequence

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

# (d_row, d_col) per heading, in the clockwise order right, down, left, up.
DELTA = [(0, 1), (1, 0), (0, -1), (-1, 0)]

#: ``(row, col, d, queue, done)``: an immutable value, rebound per step.
#: ``done`` is state because ``+`` on an empty queue stops the run with the
#: IP still inside the grid; it stays out of ``snapshot``.  The grid is a
#: parameter, not a field, so the cycle detector stores no constants.
type _State = tuple[int, int, int, tuple[int, ...], bool]


def _outside(row: int, col: int, grid: Sequence[str], width: int) -> bool:
    """Whether ``(row, col)`` is off the padded rectangle."""
    return not (0 <= col < width and 0 <= row < len(grid))


def _advance(state: _State, grid: Sequence[str], width: int) -> _State:
    """Return the state after executing one grid cell.

    The entry bounds check is not redundant: a caller may place the IP
    outside the grid, and that must halt before the cell is read.
    """
    row, col, d, queue, _done = state
    if _outside(row, col, grid, width):
        return (row, col, d, queue, True)
    cell = grid[row][col]
    if cell == "*":
        d = (d + 1) % 4
    elif cell == "~":
        queue = (*queue, d)
    elif cell == "+":
        if not queue:
            # An empty pop stops the run where it stands, without moving.
            return (row, col, d, queue, True)
        d, queue = queue[0], queue[1:]
    d_row, d_col = DELTA[d]
    row += d_row
    col += d_col
    return (row, col, d, queue, _outside(row, col, grid, width))


class _Machine:
    """An ArrowQueue run: one immutable ``_State``, rebound per step.

    :meth:`snapshot` is position, heading and queue; the queue stays bounded
    on the rings that sustain, so a repeat proves the loop.
    """

    #: The queue is dumped on the step *after* the halt; a caller who stops
    #: at ``halted`` holds no output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: list[str], io: IO | None = None) -> None:
        """Pad ``code`` to a rectangle and reset the machine to the corner.

        ``io`` defaults to a fresh :class:`IO` for step-only callers.
        """
        self.io = io if io is not None else IO()
        self.width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(self.width) for line in code)
        # An empty program has nowhere to start, so it is stopped already.
        self.state: _State = (0, 0, 0, (), not self.grid)
        # Out of ``_State``: the dump is the shell's, and ``snapshot`` must
        # keep hashing the four live fields it always has.
        self._dumped = False

    # Views on the state.

    @property
    def row(self) -> int:
        return self.state[0]

    @property
    def col(self) -> int:
        return self.state[1]

    @property
    def d(self) -> int:
        return self.state[2]

    @property
    def queue(self) -> tuple[int, ...]:
        return self.state[3]

    def place(self, row: int, col: int) -> None:
        """Move the IP to ``(row, col)`` without running a step.

        Including outside the grid, which the entry bounds check handles.
        """
        _row, _col, d, queue, done = self.state
        self.state = (row, col, d, queue, done)

    @property
    def halted(self) -> bool:
        """Whether the IP has left the grid or halted on an empty pop."""
        return self.state[4]

    @property
    def dumped(self) -> bool:
        """Whether the end-of-run queue dump has already been printed."""
        return self._dumped

    # VM view: ip is (row, col, heading), the queue the store.

    #: ``ip`` is (row, col, heading) in the program rectangle.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position."""
        row, col, d, _queue, _done = self.state
        return (row, col, d)

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is elsewhere."""
        return []

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.state[3])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Four live fields; ``done`` stays out.
        row, col, d, queue, _done = self.state
        return (row, col, d, queue)

    def step(self) -> None:
        """Execute one grid cell, or dump the queue on the post-halt step.

        ``dumped`` keeps it to one dump, as Minsky Swap and Bitdeque do.
        """
        if self.state[4]:
            if not self.dumped:
                self.io.print_str(" ".join(map(str, self.queue)))
                self._dumped = True
            return
        self.state = _advance(self.state, self.grid, self.width)


def run(code: list[str], io: IO) -> None:
    """Run an ArrowQueue program and print the queue when it halts.

    The dump follows the interpreter-only convention: the queued headings as
    :data:`DELTA` indices (0 right, 1 down, 2 left, 3 up), space-separated,
    no trailing newline -- the repo's spelling, not the spec's.  An
    empty-pop halt dumps nothing; a walk off the grid dumps what is loaded.
    The dump is :meth:`_Machine.step`'s post-halt step.
    """
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the queue


if __name__ == "__main__":
    script_main(run, shape="keep")
