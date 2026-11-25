"""Bifunge walks a grid of 2x2 bit commands with a bit stack.

Source lines come in pairs with two ASCII characters per command across
each pair. Odd characters encode 1. The IP starts at the top left heading
right. Unwritten cells are NOPs with no wrapping. An empty stack pops 0.

Input/output:
    Bytes map to Latin-1 code points, MSB first. EOF raises. A partial
    output byte is dropped at halt.

Errors:
    ProgramError: empty source or an incomplete or non-ASCII grid.
    InputExhaustedError: a byte read at EOF.
    ArgumentError: an input character outside Latin-1.
"""

from __future__ import annotations

from functools import partial
from operator import and_, or_, xor
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError
from esolangs.languages.bifunge._commands import Command
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_split_source
from esolangs.runtime.io import _BufferedOutput
from esolangs.runtime.source_hints import syntax_error

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping
    from typing import Any

    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO

type _Grid = tuple[bytes, ...]

_DIRECTIONS: dict[int, tuple[int, int]] = {
    Command.RIGHT: (1, 0),
    Command.DOWN: (0, 1),
    Command.LEFT: (-1, 0),
    Command.UP: (0, -1),
}
_BINARY: dict[int, Callable[[int, int], int]] = {
    Command.AND: and_,
    Command.OR: or_,
    Command.XOR: xor,
}
_WORKSPACE = WorkspaceModel(
    "bifunge-v1",
    ("ip", "stack", "input_buffer", "output_buffer", "stopped", "input_cursor"),
)


def _parse(code: list[str]) -> _Grid:
    if not code or not code[0]:
        raise syntax_error("Bifunge program cannot be empty", "provide a 2x2 command")
    if len(code) % 2:
        raise syntax_error(
            "Bifunge needs pairs of source rows", "complete the last pair"
        )
    rows = []
    for top, bottom in zip(code[::2], code[1::2], strict=True):
        if len(top) != len(bottom) or len(top) % 2:
            raise syntax_error(
                "Bifunge commands must be complete 2x2 blocks",
                "give both rows of each pair the same even width",
            )
        if (top and not top.isascii()) or (bottom and not bottom.isascii()):
            raise syntax_error("Bifunge source must be ASCII", "write bits as 0 and 1")
        bits = zip(top[::2], top[1::2], bottom[::2], bottom[1::2], strict=True)
        rows.append(
            bytes(
                (ord(a) & 1) << 3 | (ord(b) & 1) << 2 | (ord(c) & 1) << 1 | (ord(d) & 1)
                for a, b, c, d in bits
            )
        )
    return tuple(rows)


def _advance(
    command: int, cursor: tuple[int, int, int, int], top: int, under: int
) -> tuple[tuple[int, int, int, int], int, int | None]:
    """Return the next cursor and the opcode's pure stack edit."""
    x, y, dx, dy = cursor
    pops, result = 0, None
    if command in _BINARY:
        pops, result = 2, _BINARY[command](top, under)
    elif command in _DIRECTIONS:
        dx, dy = _DIRECTIONS[command]
    else:
        match command:
            case Command.HORIZONTAL:
                dx, dy, pops = 1 - 2 * top, 0, 1
            case Command.VERTICAL:
                dx, dy, pops = 0, 1 - 2 * top, 1
            case Command.NOT:
                pops, result = 1, 1 - top
            case Command.ZERO | Command.ONE:
                result = command - Command.ZERO
    return (x + dx, y + dy, dx, dy), pops, result


class _Machine:
    def __init__(self, grid: _Grid, io: IO) -> None:
        self.grid = grid
        self.io = io
        self.x = self.y = 0
        self.dx, self.dy = 1, 0
        self.halted = False
        self.stack: list[int] = []
        self.input_byte = self.input_bits = 0
        self.output_byte = self.output_bits = 0
        self._rejected = RejectedInput()
        self._writer = _BufferedOutput()

    @property
    def ip(self) -> tuple[int, int, int, int] | None:
        return None if self.halted else (self.y, self.x, self.dx, self.dy)

    def _state(self) -> tuple[Hashable, ...]:
        cursor = self._rejected.cursor(self.io.progress())
        accepted = self._writer.accepted
        return (
            (self.y, self.x, self.dx, self.dy),
            tuple(self.stack),
            (self.input_byte, self.input_bits),
            (self.output_byte, self.output_bits),
            self.halted,
            cursor
            if accepted is None
            else WorkspaceVariant("pending_output", (cursor, accepted)),
        )

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self._state())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(_WORKSPACE, self._state())

    def _pop(self) -> int:
        return self.stack.pop() if self.stack else 0

    def _read_bit(self) -> None:
        if not self.input_bits:
            value = self._rejected.read(self.io, self.io.input_char)
            if value > 255:
                error = ArgumentError("Bifunge input characters must fit one byte")
                self._rejected.remember(error)
                raise error
            self.input_byte, self.input_bits = value, 8
        self.input_bits -= 1
        self.stack.append(self.input_byte >> self.input_bits & 1)
        if not self.input_bits:
            self.input_byte = 0

    def _write_bit(self) -> None:
        byte = (self.output_byte << 1) | (self.stack[-1] if self.stack else 0)
        if self.output_bits == 7:
            char = chr(byte)
            self._writer.write(self.io, char, first=partial(self.io.print_char, char))
            self.output_byte = self.output_bits = 0
        else:
            self.output_byte = byte
            self.output_bits += 1
        self._pop()

    def step(self) -> None:
        if self.halted:
            return
        row = self.grid[self.y] if 0 <= self.y < len(self.grid) else b""
        command = row[self.x] if 0 <= self.x < len(row) else Command.NOP
        if command == Command.HALT:
            self.halted = True
            return
        if command == Command.INPUT:
            self._read_bit()
        elif command == Command.OUTPUT:
            self._write_bit()
        top = self.stack[-1] if self.stack else 0
        under = self.stack[-2] if len(self.stack) >= 2 else 0
        cursor, pops, result = _advance(
            command, (self.x, self.y, self.dx, self.dy), top, under
        )
        if pops:
            del self.stack[-pops:]
        if result is not None:
            self.stack.append(result)
        self.x, self.y, self.dx, self.dy = cursor


def _drive(grid: _Grid, io: IO) -> CompletionReport:
    return drive(_Machine(grid, io), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the decoded playfield across invocations."""
    source = require_split_source(source, options, "Bifunge")
    grid = _parse(source)
    return RuntimePlan(partial(_Machine, grid), partial(_drive, grid))


def _execute(code: list[str], io: IO) -> CompletionReport:
    return _drive(_parse(code), io)


def run(code: list[str], io: IO) -> None:
    """Execute a Bifunge playfield."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run, shape="strip")
