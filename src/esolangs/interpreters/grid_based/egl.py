"""Interpreter for EGL.

EGL stores unbounded integers in a declared rectangular grid.  A data pointer
moves between cells; ``x`` reads a decimal integer and ``=`` prints one.
Parenthesized bodies repeat while the cell on which their opening parenthesis
was executed is nonzero.

The wiki does not define malformed dimensions, unmatched loops, or movement
outside the grid; this interpreter raises :class:`ValueError` for all three.
Exhausted input raises :class:`EOFError` (the repo-wide convention).  EGL has
no specified invalid runtime operation requiring :class:`HaltError`.
"""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.brackets import match_brackets
from esolangs.interpreters.io import IO

type _State = tuple[int, int, int, tuple[int, ...], tuple[tuple[int, int, int], ...]]
type _Output = int | str | None


def _render_grid(grid: tuple[int, ...], width: int) -> str:
    """Return the grid in EGL's pipe-delimited display format."""
    return "".join(
        "|" + "|".join(map(str, grid[start : start + width])) + "|\n"
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
        row = height - 1 - row
    elif command == "|":
        col = width - 1 - col
    elif command == "%":
        row, col = height - 1 - row, width - 1 - col
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
            raise ValueError("unmatched ')' in EGL program")
        opening, loop_row, loop_col = loops[-1]
        if cells[loop_row * width + loop_col] != 0:
            pc = opening
        else:
            loops = loops[:-1]

    if not 0 <= row < height or not 0 <= col < width:
        raise ValueError("EGL pointer moved outside the grid")
    return (pc + 1, row, col, tuple(cells), loops), output


class _Machine:
    """EGL grid and instruction pointer exposed through the VM protocol."""

    def __init__(self, code: str, io: IO) -> None:
        match = re.fullmatch(r"(\d+),(\d+):(.*)", code, re.DOTALL)
        if match is None:
            raise ValueError("EGL program must begin with 'width,height:'")
        self.width, self.height = map(int, match.group(1, 2))
        if self.width < 1 or self.height < 1:
            raise ValueError("EGL grid dimensions must be positive")
        self.code = match.group(3)
        try:
            self.pairs = match_brackets(self.code, "(", ")")
        except ValueError as error:
            raise ValueError("unmatched parenthesis in EGL program") from error
        self.io = io
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

    @property
    def stack(self) -> list[object]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        command = self.code[self.state[0]]
        value = self.io.input_num() if command == "x" else None
        self.state, output = _advance(
            self.state, self.code, self.pairs, self.width, self.height, value
        )
        if isinstance(output, str):
            self.io.print_str(output)
        elif output is not None:
            self.io.print_num(output)


def run(code: str, io: IO) -> None:
    """Run an EGL program to the end of its source."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    with open(sys.argv[1]) as file:
        run(file.read(), IO())
