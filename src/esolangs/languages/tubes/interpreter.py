"""Interpreter for Tubes.

A program is a grid of characters.  The function pointer starts on the one
``▶`` heading right and enters one cell per step.  An operator runs and the
pointer keeps its heading; a box-drawing mover turns it.  Memory is a
plane of cells holding 0 to 3, all 0 at first, under a memory pointer.

Commands:
    ``◇``  read: skip input characters until a digit 0-3 and store it
    ``◆``  print the cell as a digit 0-3
    ``◉``  add 1 to the cell, 3 wrapping to 0
    ``▷``  halt
    ``▶``  start; a no-op when entered again
    mover  drop the arm the pointer came in by and list the rest in the
           order right, down, left, up; leave by the arm the cell modulo
           their count indexes.  A double-lined exit arm also moves the
           memory pointer one cell that way.

Input/output:
    Input is characters; output is the digits printed.

Errors:
    ProgramError: no ``▶``, or more than one.
    InputExhaustedError: a ``◇`` at EOF.
    HaltError: entering any other character, a blank or the outside of the
    grid, or a mover with no arm toward the cell the pointer left.  The
    message is that character, as the page prints it.

Decisions:
    * ``╜`` is a mover: the page's list omits it, but its Turing machine
      uses it, and every other single/double combination is listed.
    * Input and output are the digits 0-3.  The page offers ASCII-art
      input only "depending on implementation"; EOF raises, as the page
      gives it no value.
    * Outside the drawn lines is blank, an unknown character: the page
      bounds nothing, and a pointer that leaves the code aborts.
"""

from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.tubes.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

#: Headings in the page's priority order: right, down, left, up.
_STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _arms(spec: str) -> tuple[int, ...]:
    """Decode ``spec``'s right/down/left/up digits: 0 none, 1 single, 2 double."""
    return tuple(int(c) for c in spec)


#: Each mover's arms, right/down/left/up.  ``test_movers_match_unicode_names``
#: checks every entry against its Unicode name.
_MOVERS = {
    glyph: _arms(spec)
    for glyph, spec in {
        "─": "1010",
        "│": "0101",
        "┌": "1100",
        "┐": "0110",
        "└": "1001",
        "┘": "0011",
        "├": "1101",
        "┤": "0111",
        "┬": "1110",
        "┴": "1011",
        "┼": "1111",
        "═": "2020",
        "║": "0202",
        "╒": "2100",
        "╓": "1200",
        "╔": "2200",
        "╕": "0120",
        "╖": "0210",
        "╗": "0220",
        "╘": "2001",
        "╙": "1002",
        "╚": "2002",
        "╛": "0021",
        "╜": "0012",
        "╝": "0022",
        "╞": "2101",
        "╟": "1202",
        "╠": "2202",
        "╡": "0121",
        "╢": "0212",
        "╣": "0222",
        "╤": "2120",
        "╥": "1210",
        "╦": "2220",
        "╧": "2021",
        "╨": "1012",
        "╩": "2022",
        "╪": "2121",
        "╫": "1212",
        "╬": "2222",
    }.items()
}

#: ``(x, y, heading, memory x, memory y)``: where the function pointer stands.
type _State = tuple[int, int, int, int, int]


def _cell(grid: tuple[str, ...], x: int, y: int) -> str:
    return grid[y][x] if 0 <= y < len(grid) and 0 <= x < len(grid[y]) else " "


def _ahead(grid: tuple[str, ...], state: _State) -> str:
    """Return the character the pointer enters next."""
    x, y, way, _, _ = state
    dx, dy = _STEPS[way]
    return _cell(grid, x + dx, y + dy)


def _advance(
    state: _State,
    grid: tuple[str, ...],
    memory: Mapping[tuple[int, int], int],
    read: int | None = None,
) -> tuple[_State, str | None, int | None, bool]:
    """Enter the next cell; return the new state, its print and store, and halt.

    The store is the cell's new value, ``None`` if unchanged.

    Pure: a ``◇`` digit arrives as ``read``; ``memory`` is only read.
    """
    x, y, way, mx, my = state
    dx, dy = _STEPS[way]
    x, y = x + dx, y + dy
    glyph = _cell(grid, x, y)
    value = memory.get((mx, my), 0)
    arms = _MOVERS.get(glyph)
    if arms is not None:
        back = (way + 2) % 4
        if not arms[back]:
            raise HaltError(glyph)
        exits = [arm for arm in range(4) if arms[arm] and arm != back]
        way = exits[value % len(exits)]
        if arms[way] == 2:
            mx, my = mx + _STEPS[way][0], my + _STEPS[way][1]
        return (x, y, way, mx, my), None, None, False
    state = (x, y, way, mx, my)
    if glyph == "◇":
        return state, None, read, False
    if glyph == "◆":
        return state, str(value), None, False
    if glyph == "◉":
        return state, None, (value + 1) % 4, False
    if glyph == "▷":
        return state, None, None, True
    if glyph == "▶":
        return state, None, None, False
    raise HaltError(glyph)


def _start(code: str) -> tuple[tuple[str, ...], _State]:
    """Split ``code`` into rows and locate the one ``▶``."""
    grid = tuple(code.split("\n"))
    starts = [
        (x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == "▶"
    ]
    if not starts:
        raise syntax_error(
            "no ▶ start",
            "draw one ▶ where execution begins",
            error_type=ProgramError,
        )
    if len(starts) > 1:
        raise syntax_error(
            f"{len(starts)} ▶ starts",
            "the page allows at most one ▶",
            error_type=ProgramError,
        )
    ((x, y),) = starts
    return grid, (x, y, 0, 0, 0)


_WORKSPACE_MODEL = WorkspaceModel(
    "tubes-v1", ("pointer", "heading", "memory_pointer", "memory", "input_cursor")
)


class _Machine:
    """A Tubes run: the function pointer, the memory pointer and the plane."""

    ip_shape = "grid"

    def __init__(self, code: str | tuple[tuple[str, ...], _State], io: IO) -> None:
        self.grid, self.state = _start(code) if isinstance(code, str) else code
        self.io = io
        self.cells: dict[tuple[int, int], int] = {}
        self.halted = False
        self._writer = _BufferedOutput()

    @property
    def ip(self) -> tuple[int, ...]:
        """The function pointer's ``(row, col, heading)``."""
        x, y, way, _, _ = self.state
        return (y, x, way)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        x, y, way, mx, my = self.state
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            pointer=(
                WorkspaceVariant("pending_output", ((x, y), accepted))
                if accepted
                else (x, y)
            ),
            heading=way,
            memory_pointer=(mx, my),
            memory=frozenset(self.cells.items()),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        accepted = self._writer.accepted
        boundary = (
            self.halted,
            self.state,
            tuple(sorted(self.cells.items())),
            self.io.progress(),
        )
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Enter one cell; a ``◇`` reads here."""
        if self.halted:
            return
        read = None
        if _ahead(self.grid, self.state) == "◇":
            read = self._read()
        state, out, store, self.halted = _advance(
            self.state, self.grid, self.cells, read
        )
        if out is not None:
            self._writer.write(self.io, out)
        if store is not None:
            key = self.state[3:]
            if store:
                self.cells[key] = store
            else:
                self.cells.pop(key, None)
        self.state = state

    def _read(self) -> int:
        while not 48 <= (c := self.io.input_char()) <= 51:
            pass
        return c - 48


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Locate the start once and allocate state per invocation."""
    source = require_text_source(source, options, "tubes")
    image = _start(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | tuple[tuple[str, ...], _State], io: IO) -> CompletionReport:
    """Run a Tubes program until ``▷``."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Tubes program until ``▷``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
