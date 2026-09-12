r"""Interpreter for ArrowQueue."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.interpreters.io import IO

# (d_row, d_col) per heading,.
DELTA = [(0, 1), (1, 0), (0, -1), (-1, 0)]

# : One instant of a run:.
# : and heading, the direction.
# : value, not a record: every.
# : editing one in place, and.
# :.
# : ``done`` has to be carried.
# : position: ``+`` on an empty.
# : the grid, so the same.
# : stopped.
# : the four fields it always.
# : states, and a stopped run.
# :.
# : The grid is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, int, int, tuple[int, ...], bool]


def _outside(row: int, col: int, grid: Sequence[str], width: int) -> bool:
    r"""Whether ``(row, col)`` is off the padded rectangle."""
    return not (0 <= col < width and 0 <= row < len(grid))


def _advance(state: _State, grid: Sequence[str], width: int) -> _State:
    r"""Return the state after executing one grid cell."""
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
            # An empty pop stops the run.
            return (row, col, d, queue, True)
        d, queue = queue[0], queue[1:]
    d_row, d_col = DELTA[d]
    row += d_row
    col += d_col
    return (row, col, d, queue, _outside(row, col, grid, width))


class _Machine:
    r"""An ArrowQueue run: one immutable ``_State``, rebound per step."""

    # : Whether the queue is.
    # : belongs to the language,.
    # : its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: list[str], io: IO | None = None) -> None:
        r"""Pad ``code`` to a rectangle and reset the machine to the corner."""
        self.io = io if io is not None else IO()
        self.width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(self.width) for line in code)
        # An empty program has nowhere.
        self.state: _State = (0, 0, 0, (), not self.grid)
        # Out of ``_State``: the dump.
        # keep hashing the four live.
        self._dumped = False

    # The language's own names.
    # than fields of their own, so.

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
        r"""Move the IP to ``(row, col)`` without running a step."""
        _row, _col, d, queue, done = self.state
        self.state = (row, col, d, queue, done)

    @property
    def halted(self) -> bool:
        r"""Whether the IP has left the grid or halted on an empty pop."""
        return self.state[4]

    @property
    def dumped(self) -> bool:
        r"""Whether the end-of-run queue dump has already been printed."""
        return self._dumped

    # The VM's language-shaped.
    # heading).

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The current instruction position."""
        row, col, d, _queue, _done = self.state
        return (row, col, d)

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is elsewhere."""
        return []

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.state[3])

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The four live fields, exactly.
        # flag joined the state.
        # states of a running machine,.
        # last live state and the.
        row, col, d, queue, _done = self.state
        return (row, col, d, queue)

    def step(self) -> None:
        r"""Execute one grid cell, or dump the queue on the post-halt step."""
        if self.state[4]:
            if not self.dumped:
                self.io.print_str(" ".join(map(str, self.queue)))
                self._dumped = True
            return
        self.state = _advance(self.state, self.grid, self.width)


def run(code: list[str], io: IO) -> None:
    r"""Run an ArrowQueue program and print the queue when it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
