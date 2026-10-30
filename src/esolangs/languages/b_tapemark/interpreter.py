"""Functional interpreter for B-tapemark.

B-tapemark has two unbounded sparse grids, one direction shared by their
position markers, and commands that can swap which grid is executing.  Quoted
comments and the unique direction marker become blank cells when loaded.

Source rows use LF, CRLF or CR; other characters occupy a column.

Input/output:
    ``-`` on a blank data cell reads one symbol.  Input symbols are
    consecutive Unicode characters, including newlines; the spec does not
    define their encoding or framing.

Errors:
    ProgramError: an invalid source symbol outside quotes (as the wiki
    requires), a missing or repeated start marker, an unmatched quote.
    InputExhaustedError: ``-`` on a blank data cell at EOF, following the
    package convention.

Decisions:
    * An input symbol that is no command runs as a blank once a swap puts it
      on the first grid: the wiki rejects other symbols only "when the
      program is loaded".
    * After a swap, the marker that moves is the new first grid's: the wiki
      says only "the position marker".  Moving the old one's instead hangs
      generated programs (n=2 ``0110``, every row; 2026-10-30).
"""

from __future__ import annotations

from dataclasses import dataclass

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

type _Point = tuple[int, int]


class _Grid:
    """The marks on one grid, keyed by the point each sits on.

    A map from point to symbol, not a set of ``(x, y, char)`` triples: a data
    grid runs to hundreds of thousands of marks, and a triple set scanned all
    of them to read one cell.

    Immutable: a write returns a new grid, so a state can be compared with an
    earlier one and a hang proved.  The copy is a C-level ``dict`` copy, not
    a Python comprehension.
    """

    __slots__ = ("_cells", "_digest")

    #: Workspace sampling counts a grid once a run: each write's new grids
    #: tuple re-walked the unchanged program grid, 99% of an n = 8 check.
    snapshot_immutable = True

    def __init__(self, cells: dict[tuple[int, int], str]) -> None:
        """Take ownership of ``cells``; callers must not keep a reference."""
        self._cells = cells
        self._digest: int | None = None

    def at(self, point: tuple[int, int]) -> str:
        """Return the symbol at ``point``, or a blank where there is none."""
        return self._cells.get(point, " ")

    def marked(self, point: tuple[int, int], char: str) -> _Grid:
        """Return this grid with ``char`` at ``point``.

        A blank erases, which is what keeps a grid's size the count of its
        marks rather than of every cell ever written.
        """
        cells = dict(self._cells)
        if char == " ":
            cells.pop(point, None)
        else:
            cells[point] = char
        return _Grid(cells)

    def __eq__(self, other: object) -> bool:
        """Grids are equal when they carry the same marks."""
        if not isinstance(other, _Grid):
            return NotImplemented
        return self._cells == other._cells

    def __hash__(self) -> int:
        """Hash the marks, computed once.

        The cycle detector compares snapshots rather than hashing them, so
        this is for callers that want a grid in a set; it is memoized
        because a grid never changes after it is built.
        """
        if self._digest is None:
            self._digest = hash(frozenset(self._cells.items()))
        return self._digest


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


def _move(point: _Point, direction: int) -> _Point:
    """Return the adjacent point in ``direction``."""
    dx, dy = _DIRECTIONS[direction]
    return point[0] + dx, point[1] + dy


def _load(source: str) -> _State:
    """Validate and load ``source`` into an initial immutable state."""
    cells: dict[tuple[int, int], str] = {}
    starts: list[tuple[_Point, int]] = []
    quoted = False
    for y, line in enumerate(
        source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ):
        for x, char in enumerate(line):
            if char == '"':
                quoted = not quoted
            elif quoted:
                continue
            elif char in _STARTS:
                starts.append(((x, y), _STARTS.index(char)))
            elif char in _COMMANDS or "0" <= char <= "9" or "A" <= char <= "Z":
                if char != " ":
                    cells[x, y] = char
            else:
                raise syntax_error(
                    f"invalid B-tapemark symbol: {char!r}",
                    (
                        "use B-tapemark commands, digits or uppercase letters; put "
                        "comments inside double quotes"
                    ),
                )
    if quoted:
        raise syntax_error(
            "unmatched quote in B-tapemark program",
            "close each double-quoted comment with another double quote",
        )
    if len(starts) != 1:
        raise syntax_error(
            "B-tapemark program needs exactly one start marker",
            "keep exactly one direction start marker outside comments",
        )
    point, direction = starts[0]
    return _State(0, (point, point), direction, (_Grid(cells), _Grid({})))


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
    command = grids[program].at(positions[program])
    data_symbol = grids[data].at(positions[data])
    output = None

    if command == "!":
        return _State(program, positions, direction, grids, halted=True), None
    if command in _MIRRORS:
        direction = _MIRRORS[command][direction]
    elif command == "+":
        output = data_symbol
    elif command == "-" and data_symbol == " ":
        if input_symbol is None:
            raise syntax_error(
                "input symbol required for '-' command",
                "supply a character of input before executing -",
            )
        changed = grids[data].marked(positions[data], input_symbol)
        grids = (grids[0], changed) if data else (changed, grids[1])
    elif command == "*":
        skipped = _move(positions[program], direction)
        positions = (skipped, positions[1]) if program == 0 else (positions[0], skipped)
        if data_symbol == " ":
            copied = grids[program].at(skipped)
            changed = grids[data].marked(positions[data], copied)
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

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        program = self.state.program
        data = 1 - program
        command = self.state.grids[program].at(self.state.positions[program])
        needs_input = (
            command == "-"
            and self.state.grids[data].at(self.state.positions[data]) == " "
        )
        symbol = chr(self.io.input_char()) if needs_input else None
        self.state, output = _advance(self.state, symbol)
        if output is not None:
            self.io.print_char(output)


def run(source: str, io: IO) -> None:
    """Run a B-tapemark program until ``!`` executes."""
    machine = _Machine(source, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
