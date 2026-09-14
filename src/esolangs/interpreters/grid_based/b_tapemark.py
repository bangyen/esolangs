"""Functional interpreter for B-tapemark.

B-tapemark has two unbounded sparse grids, one direction shared by their
position markers, and commands that can swap which grid is executing.  Quoted
comments and the unique direction marker become blank cells when loaded.

The wiki does not define missing or repeated starts, unmatched quotes, or
invalid source symbols; this interpreter raises :class:`ValueError` for them.
Exhausted input raises :class:`EOFError`, following the package convention.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from esolangs.interpreters.io import IO

type _Point = tuple[int, int]
type _Grid = frozenset[tuple[int, int, str]]
type _Grids = tuple[_Grid, _Grid]

_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_MIRRORS = {
    "\\": (1, 0, 3, 2),
    "/": (3, 2, 1, 0),
}
_COMMANDS = frozenset(" \\/!+-*|?%")
_STARTS = ">v<^"


@dataclass(frozen=True)
class _State:
    """One immutable B-tapemark machine state."""

    program: int
    positions: tuple[_Point, _Point]
    direction: int
    grids: _Grids
    halted: bool = False


def _read(grid: _Grid, point: _Point) -> str:
    """Return ``grid``'s symbol at ``point``, or blank."""
    x, y = point
    return next((char for gx, gy, char in grid if (gx, gy) == (x, y)), " ")


def _write(grid: _Grid, point: _Point, char: str) -> _Grid:
    """Return ``grid`` with ``char`` at ``point`` without mutating it."""
    x, y = point
    remaining = frozenset(cell for cell in grid if cell[:2] != point)
    return remaining if char == " " else remaining | {(x, y, char)}


def _move(point: _Point, direction: int) -> _Point:
    """Return the adjacent point in ``direction``."""
    dx, dy = _DIRECTIONS[direction]
    return point[0] + dx, point[1] + dy


def _load(source: str) -> _State:
    """Validate and load ``source`` into an initial immutable state."""
    cells: set[tuple[int, int, str]] = set()
    starts: list[tuple[_Point, int]] = []
    quoted = False
    for y, line in enumerate(source.splitlines()):
        for x, char in enumerate(line):
            if char == '"':
                quoted = not quoted
            elif quoted:
                continue
            elif char in _STARTS:
                starts.append(((x, y), _STARTS.index(char)))
            elif char in _COMMANDS or "0" <= char <= "9" or "A" <= char <= "Z":
                if char != " ":
                    cells.add((x, y, char))
            else:
                raise ValueError(f"invalid B-tapemark symbol: {char!r}")
    if quoted:
        raise ValueError("unmatched quote in B-tapemark program")
    if len(starts) != 1:
        raise ValueError("B-tapemark program needs exactly one start marker")
    point, direction = starts[0]
    return _State(0, (point, point), direction, (frozenset(cells), frozenset()))


def _advance(
    state: _State, input_symbol: str | None = None
) -> tuple[_State, str | None]:
    """Return the next state and optional output without mutating ``state``."""
    if state.halted:
        return state, None

    program = state.program
    data = 1 - program
    positions = state.positions
    direction = state.direction
    grids = state.grids
    command = _read(grids[program], positions[program])
    data_symbol = _read(grids[data], positions[data])
    output = None

    if command == "!":
        return _State(program, positions, direction, grids, halted=True), None
    if command in _MIRRORS:
        direction = _MIRRORS[command][direction]
    elif command == "+":
        output = data_symbol
    elif command == "-" and data_symbol == " ":
        if input_symbol is None:
            raise ValueError("input symbol required for '-' command")
        changed = _write(grids[data], positions[data], input_symbol)
        grids = (grids[0], changed) if data else (changed, grids[1])
    elif command == "*":
        skipped = _move(positions[program], direction)
        positions = (skipped, positions[1]) if program == 0 else (positions[0], skipped)
        if data_symbol == " ":
            copied = _read(grids[program], skipped)
            changed = _write(grids[data], positions[data], copied)
            grids = (grids[0], changed) if data else (changed, grids[1])
    elif command == "|":
        moved = _move(positions[data], direction)
        positions = (positions[0], moved) if data else (moved, positions[1])
    elif (command == "?" and data_symbol == " ") or (
        command == "%" and data_symbol != " "
    ):
        program = data
    elif "0" <= command <= "9" or "A" <= command <= "Z":
        if direction % 2 == 0:
            output = command
        elif data_symbol == command:
            program = data

    moved = _move(positions[program], direction)
    positions = (moved, positions[1]) if program == 0 else (positions[0], moved)
    return _State(program, positions, direction, grids), output


class _Machine:
    """B-tapemark state exposed through the VM protocol."""

    ip_shape = "grid"

    def __init__(self, source: str, io: IO) -> None:
        self.state = _load(source)
        self.io = io

    @property
    def halted(self) -> bool:
        return self.state.halted

    @property
    def ip(self) -> tuple[int, ...]:
        return self.state.positions[self.state.program]

    @property
    def memory(self) -> list[object]:
        return [self.state.grids, self.state.positions, self.state.program]

    @property
    def stack(self) -> list[object]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        program = self.state.program
        data = 1 - program
        command = _read(self.state.grids[program], self.state.positions[program])
        needs_input = (
            command == "-"
            and _read(self.state.grids[data], self.state.positions[data]) == " "
        )
        symbol = chr(self.io.input_char()) if needs_input else None
        self.state, output = _advance(self.state, symbol)
        if output is not None:
            self.io.print_char(output)


def run(source: str, io: IO) -> None:
    """Run a B-tapemark program until ``!`` executes."""
    machine = _Machine(source, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    with open(sys.argv[1]) as file:
        run(file.read(), IO())
