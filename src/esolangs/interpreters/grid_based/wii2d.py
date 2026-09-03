"""WII2D (Why Is It 2D?) interpreter implementation.

2D esoteric language inspired by Befunge.
Pointer moves on a 2D grid with wrap-around behavior and an accumulator.

The wiki requires exactly one ``!`` start marker; this interpreter rejects
programs that violate that constraint instead of silently tolerating them.

Malformed programs raise :class:`ValueError`.
"""

import copy
import sys
from collections.abc import Callable, Sequence

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw


def init(code: Sequence[str]) -> Callable[[int, int, int], tuple[int, int]]:
    """Initialize movement function for WII2D grid navigation."""
    n = len(code)
    m = len(code[0])
    # Headings as (drow, dcol): North, South, West, East.  Row grows
    # downward, and both axes wrap.
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def move(row: int, col: int, vel: int) -> tuple[int, int]:
        d_row, d_col = directions[vel]
        row = (row + d_row) % n
        col = (col + d_col) % m
        return row, col

    return move


def close(
    code: Sequence[str],
) -> Callable[[int, int], tuple[int, int] | None]:
    """Create a function to find the closest @ command for jump operations."""

    def start(row: int, col: int) -> Callable[[tuple[int, int]], int]:
        """Create a distance function for sorting @ positions."""

        def dist(c: tuple[int, int]) -> int:
            return abs(c[0] - row) + abs(c[1] - col)

        return dist

    # Find all @ positions (excluding the first row)
    at_positions = []
    for row_idx, row in enumerate(code):
        for col_idx, char in enumerate(row):
            if row_idx > 0 and char == "@":
                at_positions.append((row_idx, col_idx))

    def find(row: int, col: int) -> tuple[int, int] | None:
        """Find the closest @ position to the given coordinates."""
        positions = copy.deepcopy(at_positions)
        positions.sort(key=start(row, col))
        current_pos = (row, col)
        if current_pos in positions:
            positions.remove(current_pos)
        return positions[0] if positions else None

    return find


#: One instant of a run: ``(row, col, vel, acc, done)`` -- where the
#: pointer is, which way it is heading, the accumulator, and whether a
#: ``.`` stopped it.  A value :func:`_advance` maps forward rather than
#: editing in place.
#:
#: The grid is not here, and neither are the two functions derived from it:
#: WII2D never writes to its own source, so all three are fixed for the
#: whole run and are passed to a step instead of carried by it.
type _State = tuple[int, int, int, int, bool]


def _accumulate(op: str, acc: int) -> int:
    """Return the accumulator after ``op``, which may not change it.

    ``~`` prints rather than computing, so it lands here as a no-op and the
    caller does the printing; every other non-arithmetic cell is a no-op
    too, which is what makes blank cells traversable.
    """
    if op.isdigit():
        return int(op)
    if op == "+":
        return acc + 1
    if op == "-":
        return acc - 1
    if op == "*":
        return acc * 2
    if op == "/":
        return acc // 2
    if op == "s":
        return acc**2
    return acc


def _advance(
    state: _State,
    op: str,
    move: Callable[[int, int, int], tuple[int, int]],
    find: Callable[[int, int], tuple[int, int] | None],
    turn: int | None = None,
) -> _State:
    """Return the state after executing the cell ``op``.

    Pure: it reads ``state`` and returns a new one.  ``~``'s printing is
    the caller's business, so this only carries the accumulator forward,
    and ``?``'s random heading arrives as ``turn`` rather than being drawn
    here.

    Three cells break the "compute, then move" shape and are preserved as
    they were:

    * ``@`` jumps to the row *above* the closest other ``@`` and returns
      without moving or touching the accumulator, so the next step reads
      that cell rather than stepping over it.
    * ``.`` stops the run, likewise without moving.
    * ``|`` flips between the two axes by nudging the heading one place,
      which works because the headings are ordered N, S, W, E.
    """
    row, col, vel, acc, done = state

    if op in "^v<>":
        vel = "^v<>".index(op)
    elif op == "?":
        vel = turn if turn is not None else vel
    elif op == "|":
        # Headings run N, S, W, E, so +-1 swaps within a pair and the
        # parity of the current heading says which way to step.
        vel = vel - 1 if vel % 2 else vel + 1
    elif op == "@":
        if target := find(row, col):
            # Land above the target so the step after this one reads it.
            return (target[0] - 1, target[1], vel, acc, done)
    elif op == ".":
        return (row, col, vel, acc, True)

    row, col = move(row, col, vel)
    return (row, col, vel, _accumulate(op, acc), done)


class _Machine:
    """Per-run WII2D state: position, velocity, and accumulator.

    ``step()`` executes the cell under the pointer and advances it one cell
    (wrapping around the grid); ``halted`` is true once the pointer hits
    ``.``.  The VM and the state-cycle hang detector expose this object.
    Note that ``?`` draws a random heading, so a program using it is not a
    deterministic machine and the hang detector is unsound on it.
    """

    def __init__(self, code: list[str], io: IO, rng: Randomness | None = None) -> None:
        """Validate the ``!`` marker and start above it, like :func:`run`.

        ``rng`` overrides the ``?`` command's random turn, which is what
        makes a stepped run reproducible; ``None`` draws for real.
        """
        self.io = io
        self._rng = rng
        starts = [(r, row.find("!")) for r, row in enumerate(code) if "!" in row]
        if len(starts) != 1:
            raise ValueError("WII2D program must contain exactly one '!' start marker")
        start_row, start_col = starts[0]

        max_width = max(len(row) for row in code)
        self.code = tuple(row.ljust(max_width) for row in code)

        self._find_closest_at = close(self.code)
        self._move_pointer = init(self.code)

        # start above the ! marker, moving northward
        self.row = start_row - 1
        self.col = start_col
        self.vel = 0  # 0 = north, 1 = south, 2 = west, 3 = east
        self.acc = 0
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the pointer hit ``.``."""
        return self._done

    # The VM's language-shaped view: 2D wrap-around grid.

    @property
    def ip(self) -> tuple[int, ...]:
        """The current instruction position."""
        return (self.row, self.col, self.vel)

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.row, self.col, self.vel, self.acc, self.io.position())

    def step(self) -> None:
        """Execute the cell under the pointer, then move one cell.

        The two effects live here rather than in the transition: this is
        the shell.  ``~`` prints the accumulator the transition is about to
        carry forward unchanged, and ``?``'s heading is drawn here and
        handed over, which is what lets a seeded source make a run repeat.
        """
        if self._done:
            return
        op = self.code[self.row][self.col]

        if op == "~":
            self.io.print_char(chr(self.acc))
        turn = draw(self._rng, 4) if op == "?" else None

        (self.row, self.col, self.vel, self.acc, self._done) = _advance(
            (self.row, self.col, self.vel, self.acc, self._done),
            op,
            self._move_pointer,
            self._find_closest_at,
            turn,
        )


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Execute a WII2D program.

    ``rng`` overrides ``?``'s random turn, as COD's does: a caller that
    needs the turns to fall a particular way passes a source rather than
    patching this module.
    """
    machine = _Machine(code, io, rng=rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
