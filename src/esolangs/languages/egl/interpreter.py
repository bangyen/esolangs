"""Interpreter for EGL.

EGL stores unbounded integers in a declared rectangular grid.  A data pointer
moves between cells; ``x`` reads a character code and ``=`` prints a decimal integer.
Parenthesized bodies repeat while the cell on which their opening parenthesis
was executed is nonzero.

A reflection negates a coordinate modulo the grid (``_`` row ``r`` to
``-r % height``), so row 0 is fixed.

Input/output:
    ``x`` reads a character code.  Exhausted input raises (the repo-wide
    convention).

Errors:
    ProgramError: Malformed dimensions (no leading ``width,height:``, or a
        dimension below 1); an unmatched parenthesis; a pointer move outside
        the grid.
    InputExhaustedError: ``x`` at EOF.

Decisions:
    * The wiki does not define malformed dimensions, unmatched loops, or
      movement outside the grid; all three are a ProgramError.  EGL has no
      specified invalid runtime operation requiring HaltError.
    * The spec does not define input representation; ``x`` reads the next
      Unicode character code, including newlines.
    * The page's stated output for ``10,10:v>>_++#`` puts the 2 on the tenth
      line, third column; the mirror ``height - 1 - r`` puts it on the ninth,
      which only the prose ("row 9, column 3", one-indexed) fits; the stated
      output wins.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from esolangs.languages.egl.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.brackets import match_brackets
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

type _State = tuple[int, int, int, tuple[int, ...], tuple[tuple[int, int, int], ...]]
type _Output = int | str | None


def _render_grid(grid: tuple[int, ...], width: int) -> str:
    """Return the grid in EGL's pipe-delimited display format."""
    return "".join(
        "|" + "|".join(map(format_integer, grid[start : start + width])) + "|\n"
        for start in range(0, len(grid), width)
    )


def _advance(
    state: _State,
    code: str,
    pairs: Mapping[int, int],
    width: int,
    height: int,
    value: int | None = None,
) -> tuple[_State, _Output]:
    """Return the state after one command and an optional output value."""
    pc, row, col, grid, loops = state
    command = code[pc]
    cells = list(grid)
    index = row * width + col
    output: _Output = None

    if command == ">":
        col += 1
    elif command == "<":
        col -= 1
    elif command == "^":
        row -= 1
    elif command == "v":
        row += 1
    elif command == "_":
        row = -row % height
    elif command == "|":
        col = -col % width
    elif command == "%":
        row, col = -row % height, -col % width
    elif command == "+":
        cells[index] += 1
    elif command == "-":
        cells[index] -= 1
    elif command == "x" and value is not None:
        cells[index] = value
    elif command == "=":
        output = cells[index]
    elif command == "#":
        output = _render_grid(tuple(cells), width)
    elif command == "(":
        if cells[index] == 0:
            pc = pairs[pc]
        else:
            loops = (*loops, (pc, row, col))
    elif command == ")":
        if not loops:
            raise syntax_error(
                "unmatched ')' in EGL program", "pair each closing ) with an earlier ("
            )
        opening, loop_row, loop_col = loops[-1]
        if cells[loop_row * width + loop_col] != 0:
            pc = opening
        else:
            loops = loops[:-1]

    if not 0 <= row < height or not 0 <= col < width:
        raise syntax_error(
            "EGL pointer moved outside the grid",
            (
                "keep pointer movements within the declared width and "
                "height, or enlarge the grid"
            ),
        )
    return (pc + 1, row, col, tuple(cells), loops), output


_WORKSPACE_MODEL = WorkspaceModel(
    "egl-v1",
    ("instruction", "row", "column", "cells", "loops", "input_cursor", "input_reads"),
)


type _SourceImage = tuple[int, int, str, Mapping[int, int]]


def _prepare_source(code: str) -> _SourceImage:
    match = re.fullmatch(r"(\d+),(\d+):(.*)", code, re.DOTALL)
    if match is None:
        raise syntax_error(
            "EGL program must begin with 'width,height:'",
            "start with positive grid dimensions, for example 2,3:+=",
        )
    width, height = map(parse_integer, match.group(1, 2))
    if width < 1 or height < 1:
        raise syntax_error(
            "EGL grid dimensions must be positive",
            "use dimensions of at least 1, for example 1,1:",
        )
    code = match.group(3)
    try:
        pairs = match_brackets(code, "(", ")")
    except ValueError as error:
        raise syntax_error(
            "unmatched parenthesis in EGL program", "pair every ( with a closing )"
        ) from error
    return width, height, code, MappingProxyType(pairs)


class _Machine:
    """EGL grid and instruction pointer exposed through the VM protocol."""

    def __init__(self, code: str | _SourceImage, io: IO) -> None:
        self.width, self.height, self.code, self.pairs = (
            _prepare_source(code) if isinstance(code, str) else code
        )
        self.io = io
        self._input_reads = 0
        self.state: _State = (
            0,
            0,
            0,
            (0,) * (self.width * self.height),
            (),
        )

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.code)

    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        return self.state[1:3]

    @property
    def memory(self) -> list[int]:
        return list(self.state[3])

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state[0],
            row=self.state[1],
            column=self.state[2],
            cells=self.state[3],
            loops=self.state[4],
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
        )

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress(), self._input_reads)

    def step(self) -> None:
        if self.halted:
            return
        command = self.code[self.state[0]]
        value = None
        if command == "x":
            value = self.io.input_char()
            self._input_reads += 1
        self.state, output = _advance(
            self.state, self.code, self.pairs, self.width, self.height, value
        )
        if isinstance(output, str):
            self.io.print_str(output)
        elif output is not None:
            self.io.print_str(format_integer(output))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain source and jump targets with fresh invocation state."""
    if not isinstance(source, str):
        raise TypeError("egl machines require text source")
    if options:
        raise TypeError("egl machines accept no runtime options")

    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _SourceImage, io: IO) -> CompletionReport:
    """Run an EGL program to the end of its source."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run an EGL program to the end of its source."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
