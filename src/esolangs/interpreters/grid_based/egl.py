"""Interpreter for EGL.

EGL stores unbounded integers in a declared rectangular grid.  A data pointer
moves between cells; ``x`` reads a character code and ``=`` prints a decimal integer.
Parenthesized bodies repeat while the cell on which their opening parenthesis
was executed is nonzero.

The wiki does not define malformed dimensions, unmatched loops, or movement
outside the grid; this interpreter raises :class:`ValueError` for all three.
Exhausted input raises :class:`EOFError` (the repo-wide convention).  EGL has
no specified invalid runtime operation requiring :class:`HaltError`.

The spec does not define input representation; x reads the next Unicode
character code, including newlines.

A reflection negates a coordinate modulo the grid (``_`` row ``r`` to
``-r % height``), so row 0 is fixed.  The page's stated output for
``10,10:v>>_++#`` puts the 2 on the tenth line, third column; the
mirror ``height - 1 - r`` puts it on the ninth, which only the prose
("row 9, column 3", one-indexed) fits; the stated output wins.
"""

from __future__ import annotations

import re

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import match_brackets
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import format_integer, parse_integer
from esolangs.interpreters.source_hints import syntax_error

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
    pairs: dict[int, int],
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


class _Machine:
    """EGL grid and instruction pointer exposed through the VM protocol."""

    def __init__(self, code: str, io: IO) -> None:
        match = re.fullmatch(r"(\d+),(\d+):(.*)", code, re.DOTALL)
        if match is None:
            raise syntax_error(
                "EGL program must begin with 'width,height:'",
                "start with positive grid dimensions, for example 2,3:+=",
            )
        self.width, self.height = map(parse_integer, match.group(1, 2))
        if self.width < 1 or self.height < 1:
            raise syntax_error(
                "EGL grid dimensions must be positive",
                "use dimensions of at least 1, for example 1,1:",
            )
        self.code = match.group(3)
        try:
            self.pairs = match_brackets(self.code, "(", ")")
        except ValueError as error:
            raise syntax_error(
                "unmatched parenthesis in EGL program", "pair every ( with a closing )"
            ) from error
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

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress(), self._input_reads)

    def step(self) -> None:
        if self.halted:
            return
        command = self.code[self.state[0]]
        value = self.io.input_char() if command == "x" else None
        if command == "x":
            self._input_reads += 1
        self.state, output = _advance(
            self.state, self.code, self.pairs, self.width, self.height, value
        )
        if isinstance(output, str):
            self.io.print_str(output)
        elif output is not None:
            self.io.print_str(format_integer(output))


def run(code: str, io: IO) -> None:
    """Run an EGL program to the end of its source."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
