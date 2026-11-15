"""Interpreter for Balik.

A two-dimensional program over a right-infinite tape of trits (0, 1, 2).
The instruction pointer starts at the top-left cell heading east, runs the
command under it, then moves one cell; it halts on leaving the grid.

Commands:
    ``+``  increment the current cell, 2 wrapping to 0
    ``>``  move the tape pointer right
    ``<``  move the tape pointer left
    ``*``  turn the instruction pointer 90 degrees clockwise
    ``@``  reverse the instruction pointer if the current cell is 0
    ``.``  print the current cell
    ``,``  read a ternary digit and add it to the current cell, mod 3

Input/output:
    ``,`` reads one character, skipping whitespace, and needs ``0``, ``1``
    or ``2``; a read at EOF raises.  ``.`` prints the cell's digit.

Errors:
    ProgramError: a character that is neither a command nor a space.
    InputExhaustedError: ``,`` at EOF.
    ArgumentError: ``,`` given a character that is not a ternary digit.
    HaltError: ``<`` on the leftmost cell.

Decisions:
    * The pointer starts at the top-left heading east; the page's loop
      diagram is entered from the left of its top line.
    * The grid is the program's lines padded with spaces to the longest,
      so a short line does not end the run early: "out of bounds" is the
      program's rectangle.
    * The page's Reversible Brainfuck diagram, traced here, enters its body
      when the cell is 0 and repeats it while the cell is nonzero; ``@``
      reverses on 0 as the command list says, and the test pins the trace.
    * ``<`` on the leftmost cell is an error: the tape is right-infinite.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.balik.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

_COMMANDS = frozenset("+<>*@., ")
#: Row and column steps for east, south, west, north: ``*`` adds one.
_STEPS = ((0, 1), (1, 0), (0, -1), (-1, 0))

#: ``(row, col, heading, pointer)``; the tape is the shell's.
type _State = tuple[int, int, int, int]


def _advance(
    state: _State, c: str, cell: int, read: int | None = None
) -> tuple[_State, int, int | None]:
    """Return the state after command ``c``, the cell's new value and output.

    Pure: the shell passes the current cell and any read, and writes the
    returned value back to the tape.
    """
    row, col, heading, pointer = state
    out = None
    if c == "+":
        cell = (cell + 1) % 3
    elif c == ">":
        pointer += 1
    elif c == "<":
        pointer -= 1
    elif c == "*":
        heading = (heading + 1) % 4
    elif c == "@" and cell == 0:
        heading = (heading + 2) % 4
    elif c == ".":
        out = cell
    elif c == "," and read is not None:
        cell = (cell + read) % 3
    dr, dc = _STEPS[heading]
    return (row + dr, col + dc, heading, pointer), cell, out


_WORKSPACE_MODEL = WorkspaceModel(
    "balik-v1", ("row", "column", "heading", "pointer", "tape", "input_cursor")
)


def _prepare_grid(code: str) -> tuple[str, ...]:
    lines = code.split("\n")
    width = max(len(line) for line in lines)
    for line in lines:
        for c in line:
            if c not in _COMMANDS:
                raise syntax_error(
                    f"unknown command {c!r}",
                    "use + < > * @ . , and spaces",
                )
    return tuple(line.ljust(width) for line in lines)


class _Machine:
    """The run state: position, heading, tape pointer and the tape."""

    ip_shape = "grid"

    def __init__(self, code: str | tuple[str, ...], io: IO) -> None:
        self.grid = _prepare_grid(code) if isinstance(code, str) else code
        self.io = io
        self._writer = _BufferedOutput()
        self.state: _State = (0, 0, 0, 0)
        self._rejected_input: str | None = None
        # Mutable and shell-owned: the tape grows one cell per ``>``.
        self.tape = [0]

    @property
    def halted(self) -> bool:
        row, col = self.state[:2]
        return not (0 <= row < len(self.grid) and 0 <= col < len(self.grid[row]))

    @property
    def ip(self) -> tuple[int, ...]:
        """The current cell and heading."""
        return self.state[:3]

    @property
    def memory(self) -> list[int]:
        """The tape cells visited so far."""
        return self.tape

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        cursor = self.io.progress()
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            row=self.state[0],
            column=(
                WorkspaceVariant("pending_output", (self.state[1], accepted))
                if accepted
                else self.state[1]
            ),
            heading=self.state[2],
            pointer=self.state[3],
            tape=tuple(self.tape),
            input_cursor=(
                cursor
                if self._rejected_input is None
                else WorkspaceVariant("rejected_input", (cursor, self._rejected_input))
            ),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        state = (*self.state, tuple(self.tape), self.io.progress())
        if self._rejected_input is not None:
            return (*state, self._rejected_input)
        accepted = self._writer.accepted
        return (*state, accepted) if accepted else state

    def _read_ternary(self) -> int:
        digit = self._rejected_input
        if digit is None:
            digit = chr(self.io.input_char())
            while digit.isspace():
                digit = chr(self.io.input_char())
        if digit not in "012":
            self._rejected_input = digit
            raise syntax_error(
                f"input must be a ternary digit, got {digit!r}",
                "supply the characters 0, 1 or 2",
                error_type=ArgumentError,
            )
        return int(digit)

    def step(self) -> None:
        """Run the command under the pointer, then move one cell."""
        if self.halted:
            return
        row, col, _heading, pointer = self.state
        c = self.grid[row][col]
        if c == "<" and pointer == 0:
            raise HaltError(
                f"'<' at row {row}, column {col} on the leftmost cell",
                hint="the tape is right-infinite; move right before moving left",
            )
        read = self._read_ternary() if c == "," else None
        state, value, out = _advance(self.state, c, self.tape[pointer], read)
        if out is not None:
            self._writer.write(self.io, str(out), first=partial(self.io.print_num, out))
        self.state = state
        self.tape[pointer] = value
        if self.state[3] == len(self.tape):
            self.tape.append(0)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the prepared grid and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("balik machines require text source")
    if options:
        raise TypeError("balik machines accept no runtime options")

    image = _prepare_grid(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | tuple[str, ...], io: IO) -> CompletionReport:
    """Run a Balik program until the pointer leaves the grid."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Balik program until the pointer leaves the grid."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
