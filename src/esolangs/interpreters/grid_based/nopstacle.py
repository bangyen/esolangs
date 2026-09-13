"""Pure-state interpreter for Nopstacle.

The program rectangle repeats infinitely to the right and down; cells above
or left of it are obstacles. The IP starts at the empty top-left cell moving
down. It moves into an empty cell, or stays put and turns anticlockwise when
an obstacle blocks it. Repeating a position and direction without leaving
the current copy halts.

Malformed rectangles raise :class:`ValueError`: a program needs at least one
cell, may contain only spaces and ``#``, and must leave its top-left cell empty.
"""

from __future__ import annotations

from collections.abc import Sequence

from esolangs.interpreters.io import IO

# Up, left, down, right: adding one is an anticlockwise turn in screen
# coordinates.
_DELTA = ((0, -1), (-1, 0), (0, 1), (1, 0))
_DOWN = 2

type _Local = tuple[int, int, int]
type _State = tuple[int, int, int, frozenset[_Local], bool]


def _copy(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    """Return which repeated program copy contains ``(x, y)``."""
    return (x // width, y // height)


def _local(x: int, y: int, direction: int, width: int, height: int) -> _Local:
    """Return a state relative to its repeated program copy."""
    return (x % width, y % height, direction)


def _advance(state: _State, grid: tuple[str, ...], width: int, height: int) -> _State:
    """Return the next immutable execution state."""
    x, y, direction, seen, halted = state
    if halted:
        return state

    old_copy = _copy(x, y, width, height)
    dx, dy = _DELTA[direction]
    nx, ny = x + dx, y + dy
    blocked = nx < 0 or ny < 0 or grid[ny % height][nx % width] == "#"
    if blocked:
        direction = (direction + 1) % 4
    else:
        x, y = nx, ny

    here = _local(x, y, direction, width, height)
    if _copy(x, y, width, height) != old_copy:
        return (x, y, direction, frozenset({here}), False)
    if here in seen:
        return (x, y, direction, seen, True)
    return (x, y, direction, seen | {here}, False)


class _Machine:
    """A Nopstacle run whose behavior is defined by :func:`_advance`."""

    ip_shape = "grid"

    def __init__(self, code: Sequence[str], io: IO | None = None) -> None:
        """Validate and pad ``code``, then place the IP at the origin."""
        if not code or max(map(len, code), default=0) == 0:
            raise ValueError("Nopstacle program must contain a cell")
        if any(set(row) - {" ", "#"} for row in code):
            raise ValueError("Nopstacle cells must be spaces or '#'")
        if code[0].startswith("#"):
            raise ValueError("Nopstacle's top-left cell must be empty")
        self.io = io if io is not None else IO()
        self.width = max(map(len, code))
        self.height = len(code)
        self.grid = tuple(row.ljust(self.width) for row in code)
        start = _local(0, 0, _DOWN, self.width, self.height)
        self.state: _State = (0, 0, _DOWN, frozenset({start}), False)

    @property
    def halted(self) -> bool:
        """Whether the IP repeated a state within its current copy."""
        return self.state[4]

    @property
    def ip(self) -> tuple[int, int, int]:
        """Return the absolute IP position and direction."""
        return self.state[:3]

    @property
    def memory(self) -> list[object]:
        """Return Nopstacle's empty mutable store."""
        return []

    @property
    def stack(self) -> list[object]:
        """Return Nopstacle's empty stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return exact state, folding only a statically open forward ray."""
        x, y, direction, seen, _halted = self.state
        local_x, local_y = x % self.width, y % self.height
        if direction == 3 and all(cell == " " for cell in self.grid[local_y]):
            return ("open-right-ray", local_y)
        if direction == 2 and all(row[local_x] == " " for row in self.grid):
            return ("open-down-ray", local_x)
        return (x, y, direction, seen)

    def step(self) -> None:
        """Advance one attempted move using the pure transition."""
        self.state = _advance(self.state, self.grid, self.width, self.height)


def run(code: list[str], io: IO) -> None:
    """Run a Nopstacle program until its mandated local-cycle halt."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
