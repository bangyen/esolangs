r"""WII2D (Why Is It 2D?) interpreter implementation."""

import copy
import sys
from collections.abc import Callable, Sequence
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw


def init(code: Sequence[str]) -> Callable[[int, int, int], tuple[int, int]]:
    r"""Initialize movement function for WII2D grid navigation."""
    n = len(code)
    m = len(code[0])
    # Headings as (drow, dcol):.
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
    r"""Create a function to find the closest @ command for jump operations."""

    def start(row: int, col: int) -> Callable[[tuple[int, int]], int]:
        r"""Create a distance function for sorting @ positions."""

        def dist(c: tuple[int, int]) -> int:
            return abs(c[0] - row) + abs(c[1] - col)

        return dist

    # Find all @ positions.
    at_positions = []
    for row_idx, row in enumerate(code):
        for col_idx, char in enumerate(row):
            if row_idx > 0 and char == "@":
                at_positions.append((row_idx, col_idx))

    def find(row: int, col: int) -> tuple[int, int] | None:
        r"""Find the closest @ position to the given coordinates."""
        positions = copy.deepcopy(at_positions)
        positions.sort(key=start(row, col))
        current_pos = (row, col)
        if current_pos in positions:
            positions.remove(current_pos)
        return positions[0] if positions else None

    return find


# : One instant of a run:.
# : pointer is, which way it is.
# : ``.`` stopped it.
#: editing in place.
# :.
# : The grid is not here, and.
# : WII2D never writes to its.
# : whole run and are passed to.
type _State = tuple[int, int, int, int, bool]


def _accumulate(op: str, acc: int) -> int:
    r"""Return the accumulator after ``op``, which may not change it."""
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
    r"""Return the state after executing the cell ``op``."""
    row, col, vel, acc, done = state

    if op in "^v<>":
        vel = "^v<>".index(op)
    elif op == "?":
        vel = turn if turn is not None else vel
    elif op == "|":
        # Headings run N, S, W, E, so.
        # parity of the current heading.
        vel = vel - 1 if vel % 2 else vel + 1
    elif op == "@":
        if target := find(row, col):
            # Land above the target so the.
            return (target[0] - 1, target[1], vel, acc, done)
    elif op == ".":
        return (row, col, vel, acc, True)

    row, col = move(row, col, vel)
    return (row, col, vel, _accumulate(op, acc), done)


class _Machine:
    r"""Per-run WII2D state: position, velocity, and accumulator."""

    def __init__(self, code: list[str], io: IO, rng: Randomness | None = None) -> None:
        r"""Validate the ``!`` marker and start above it, like :func:`run`."""
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

        # start above the .
        self.row = start_row - 1
        self.col = start_col
        self.vel = 0  # 0 = north, 1 = south, 2 =.
        self.acc = 0
        self._done = False

    @property
    def halted(self) -> bool:
        r"""Whether the pointer hit ``.``."""
        return self._done

    # The VM's language-shaped.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The current instruction position."""
        return (self.row, self.col, self.vel)

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (self.row, self.col, self.vel, self.acc, self.io.position())

    def branching_snapshot(self) -> _State:
        r"""Return the starting state for an all-random-outcomes search."""
        return (self.row, self.col, self.vel, self.acc, self._done)

    def branching_halted(self, state: object) -> bool:
        r"""Report whether a branching-search state reached ``.``."""
        return cast(_State, state)[4]

    def branching_successors(self, state: object, _limit: int) -> tuple[_State, ...]:
        r"""Return the state for every legal ``?`` turn at this cell."""
        branch_state = cast(_State, state)
        row, col, _vel, _acc, _done = branch_state
        op = self.code[row][col]
        turns = range(4) if op == "?" else (None,)
        return tuple(
            _advance(
                branch_state,
                op,
                self._move_pointer,
                self._find_closest_at,
                turn,
            )
            for turn in turns
        )

    def step(self) -> None:
        r"""Execute the cell under the pointer, then move one cell."""
        if self._done:
            return
        op = self.code[self.row][self.col]

        if op == "~":
            # ``chr`` raises ``ValueError:.
            # which names neither the.
            # there -- and is the message a.
            # eleven characters.
            if not 0 <= self.acc <= 0x10FFFF:
                raise HaltError(
                    f"'~' at row {self.row}, column {self.col} prints the "
                    f"accumulator as a character and it holds {self.acc}, "
                    f"outside 0..0x10FFFF"
                )
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
    r"""Execute a WII2D program."""
    machine = _Machine(code, io, rng=rng)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
