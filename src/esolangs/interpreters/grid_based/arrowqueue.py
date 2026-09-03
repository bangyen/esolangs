"""Interpreter for ArrowQueue.

ArrowQueue is a two-dimensional, queue-based tarpit inspired by Re:direction.
The Instruction Pointer (IP) walks a grid; ``*`` turns it clockwise, ``~``
pushes the current direction onto a queue, and ``+`` pops the queue and
points the IP in the popped direction.  All other characters are no-ops.
The program halts when ``+`` pops an empty queue or the IP moves off the
grid.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the grid to the next state, and never
mutates what it is given.  ArrowQueue defines no I/O at all, so unlike the
other languages in this repo the transition needs no effect parameter and
no shell cooperation -- a whole run is a fold of :func:`_advance` over a
starting state, and :class:`_Machine` exists only to supply the mutable
protocol the rest of the library expects.

The halted flag is *in* the state rather than derived from it.  Everywhere
else a machine halts when its cursor passes the end of the program, which
is a fact about the position; here halting is a decision a step makes -- an
empty pop stops the run with the IP still on the grid, and there is no
position that means "stopped".  Two runs can share a position, a heading,
and a queue and differ only in whether one of them has already halted.

:class:`_Machine` holds one ``_State`` and rebinds it each step, so the
mutation lives in exactly one assignment and every rule about what
ArrowQueue *does* stays in the pure layer.

Decisions for gaps in the wiki spec (documented):
- the IP starts in the top-left corner moving right, matching Re:direction
  (the wiki is silent on both);
- clockwise order is right, down, left, up (screen coordinates), so turning
  is ``(dir + 1) % 4``;
- the grid is padded to a rectangle as wide as the longest line, which is
  how the wiki's examples lay out wide rows; an IP that leaves the
  rectangle has moved out of bounds and halts the program.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from esolangs.interpreters.io import IO

# (d_row, d_col) per heading, in the clockwise order right, down, left, up.
DELTA = [(0, 1), (1, 0), (0, -1), (-1, 0)]

#: One instant of a run: ``(row, col, d, queue, done)`` -- the IP's position
#: and heading, the direction queue, and whether the run has stopped.  A
#: value, not a record: every transition below returns a new one rather than
#: editing one in place, and the queue is a ``tuple`` for the same reason.
#:
#: ``done`` has to be carried because halting here is not a property of the
#: position: ``+`` on an empty queue stops the run with the IP still inside
#: the grid, so the same ``(row, col, d, queue)`` can be either live or
#: stopped.  It is deliberately *not* in ``snapshot``, which reports only
#: the four fields it always reported -- the cycle detector compares live
#: states, and a stopped run is not something it is asked about.
#:
#: The grid is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, int, int, tuple[int, ...], bool]


def _outside(row: int, col: int, grid: Sequence[str], width: int) -> bool:
    """Whether ``(row, col)`` is off the padded rectangle.

    The bounds are checked twice per step -- once on entry and once after
    moving -- so the test lives here rather than being spelled out at both
    sites.
    """
    return not (0 <= col < width and 0 <= row < len(grid))


def _advance(state: _State, grid: Sequence[str], width: int) -> _State:
    """Return the state after executing one grid cell.

    Pure, and unusually for this repo it is *total* without any help from a
    shell: ArrowQueue has no I/O, so there is no effect to hoist out and no
    value to pass back in.

    The entry bounds check is not redundant with the one after the move.  A
    machine can be handed a position outside the grid without having moved
    there itself -- a caller may place the IP -- and that has to halt before
    the cell is read, or the read would be out of range.

    Anything that is not one of the three commands is a no-op and falls
    through to the shared move, which is what makes the IP advance exactly
    one cell per call.
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

    ``step()`` advances the IP by one grid cell and ``halted`` says whether
    it has run off the grid or popped an empty queue — the shape the VM
    wrapper and the state-cycle hang detector expect.  :meth:`snapshot`
    returns the position, heading, and queue, so a repeated snapshot proves
    a deterministic run loops forever (the queue stays bounded on the
    rings that sustain).
    """

    __slots__ = ("grid", "state", "width")

    def __init__(
        self,
        code: list[str],
        io: IO | None = None,  # noqa: ARG002 - see ``run``
    ) -> None:
        """Pad ``code`` to a rectangle and reset the machine to the corner.

        ``io`` is accepted and ignored, exactly as :func:`run` accepts it:
        ArrowQueue defines no I/O, and taking the parameter anyway lets
        every caller build a machine the same way.
        """
        self.width = max(map(len, code), default=0)
        self.grid = tuple(line.ljust(self.width) for line in code)
        # An empty program has nowhere to start, so it is stopped already.
        self.state: _State = (0, 0, 0, (), not self.grid)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

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

        The VM and the hang detector drive :meth:`step` directly, so a
        machine can be positioned somewhere a program would never reach --
        including outside the grid, which the transition's entry bounds
        check exists to handle.
        """
        _row, _col, d, queue, done = self.state
        self.state = (row, col, d, queue, done)

    @property
    def halted(self) -> bool:
        """Whether the IP has left the grid or halted on an empty pop."""
        return self.state[4]

    # The VM's language-shaped view: Direction queue; ip is the IP's (row, col,
    # heading).

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
        # The four live fields, exactly as this returned before the halted
        # flag joined the state.  ``done`` stays out: the detector compares
        # states of a running machine, and folding it in would give the
        # last live state and the stopped one two different hashes.
        row, col, d, queue, _done = self.state
        return (row, col, d, queue)

    def step(self) -> None:
        """Execute one grid cell, advancing the IP."""
        if self.state[4]:
            return
        self.state = _advance(self.state, self.grid, self.width)


def run(
    code: list[str],
    io: IO,  # noqa: ARG001 - ArrowQueue defines no I/O; the param follows the
    # repo convention so `esolangs.run` and the example harness pass it uniformly
) -> None:
    """Run an ArrowQueue program, halting on an empty-queue pop or off-grid."""
    machine = _Machine(code)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
