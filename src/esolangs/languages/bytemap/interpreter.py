"""Interpreter for Bytemap: self-modifying byte commands on an unbounded grid.

The source is rows of hex byte pairs; every cell not given reads as ``FF``,
including cells left of and above the source.  The pointer starts at the
first byte and runs rightward: each command reads its operand bytes to its
right and continues after them, unless it jumps.  A byte jump is a
direction byte and a count byte; inside another command it is an operand
measured from that command's first byte.  Multi-byte values read rightward
from the jump's target.

Commands:
    52 54 56 58 n  jump n cells down, left, right or up, and run from there
    00 0A 0F j n   print n bytes from j: signed decimal, characters, hex
    10 1A 1F j n   read an integer, n characters, or n hex pairs into j
    A0..A4 a b w n w = a + b, a - b, a * b, a / b, a % b over n bytes
    C1..C6 a b n t f  compare n bytes (<, <=, ==, >=, >, !=); go to t or f
    FF             halt

Input/output:
    Input is bytes: the UTF-8 encoding of the text.  ``10`` reads a
    whitespace-delimited integer.  At EOF every byte a read would write is
    ``FF``.  Output is unseparated: ``00`` prints the signed value of all n
    bytes, ``0F`` two uppercase hex digits a byte.

Errors:
    ProgramError: a character other than ``0-9``, ``A-F`` or a newline, or
    a row with an odd number of hex digits.
    ArgumentError: a ``10`` token that is not a decimal integer.
    HaltError: a byte with no command run as one, or division or modulus by
    zero.

Decisions:
    * "an even number of rows" means an even number of digits per row: the
      page's Hello World is one row, and every example row is even.
    * Multi-byte values are big-endian in grid order, the order ``0F``
      prints them in; no example depends on it.
    * A command whose operand jump is not ``5[2468]`` and has no stated
      default (an output or input source, an arithmetic destination) is
      skipped whole, as the page rules for output; so is a zero length.
    * A comparison continues after itself if either target is invalid,
      which the page states besides "command is ignored".
    * Division truncates toward zero and a remainder takes the dividend's
      sign, as C's do; the page calls its values "c-like ints".
    * EOF writes ``FF``, the page's value for every byte not specified and
      for invalid hex.
    * Running a byte that names no command halts with an error: only ``FF``
      is said to stop, and guessing a no-op would invent semantics.
    * The column-wise self-replicating example is not pinned: its second
      ``A0`` writes ``5201`` 13 cells left, at column -5, not the row start,
      so it loops on row 0 instead of walking down (and copies 15 of its 18
      bytes); it predates rev. 33278's two-byte jump.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.bytemap.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import (
    WorkspaceModel,
    WorkspaceSnapshot,
    WorkspaceVariant,
    pending_output_cursor,
)
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import trunc_div, trunc_mod
from esolangs.runtime.source_hints import syntax_error

type _Cell = tuple[int, int]
#: Row, column, halted.
type _State = tuple[int, int, bool]
#: What a command needs read first: ``("int"|"char"|"hex", count)``.
type _Read = tuple[str, int] | None
#: Cells to write, then text to print.
type _Effects = tuple[tuple[tuple[_Cell, int], ...], str]

_BLANK = 0xFF
_JUMPS = {0x52: (1, 0), 0x54: (0, -1), 0x56: (0, 1), 0x58: (-1, 0)}
_OPERANDS = {0x0: 3, 0x1: 3, 0xA: 7, 0xC: 9}
_ARITHMETIC: dict[int, Callable[[int, int], int]] = {
    0xA0: lambda a, b: a + b,
    0xA1: lambda a, b: a - b,
    0xA2: lambda a, b: a * b,
    0xA3: trunc_div,
    0xA4: trunc_mod,
}
_COMPARISONS: dict[int, Callable[[int, int], bool]] = {
    0xC1: lambda a, b: a < b,
    0xC2: lambda a, b: a <= b,
    0xC3: lambda a, b: a == b,
    0xC4: lambda a, b: a >= b,
    0xC5: lambda a, b: a > b,
    0xC6: lambda a, b: a != b,
}
_OUTPUTS = {0x00, 0x0A, 0x0F}
_INPUTS = {0x10: "int", 0x1A: "char", 0x1F: "hex"}
_HEX = "0123456789ABCDEF"


def _parse(code: str) -> dict[_Cell, int]:
    """Return the source's bytes by cell; a missing cell is ``FF``."""
    grid: dict[_Cell, int] = {}
    rows = code.replace("\r\n", "\n").split("\n")
    if rows and rows[-1] == "":
        rows.pop()  # a final newline ends the last row
    for r, row in enumerate(rows):
        if bad := next((ch for ch in row if ch not in _HEX), None):
            raise syntax_error(
                f"row {r + 1} has {bad!r}, not an uppercase hex digit",
                "write each byte as two of 0-9 and A-F",
            )
        if len(row) % 2:
            raise syntax_error(
                f"row {r + 1} has an odd number of hex digits",
                "write each byte as two hex digits",
            )
        for c in range(0, len(row), 2):
            grid[r, c // 2] = int(row[c : c + 2], 16)
    return grid


def _target(origin: _Cell, cell: Callable[[_Cell], int], at: int) -> _Cell | None:
    """Return the cell an operand jump at column offset ``at`` names, if valid."""
    r, c = origin
    step = _JUMPS.get(cell((r, c + at)))
    if step is None:
        return None
    count = cell((r, c + at + 1))
    return r + step[0] * count, c + step[1] * count


def _value(cell: Callable[[_Cell], int], start: _Cell, length: int) -> int:
    """Return ``length`` bytes from ``start`` rightward as a signed integer."""
    r, c = start
    raw = int.from_bytes(bytes(cell((r, c + i)) for i in range(length)), "big")
    return raw - (1 << 8 * length) if length and raw >> (8 * length - 1) else raw


def _store(start: _Cell, value: int, length: int) -> tuple[tuple[_Cell, int], ...]:
    """Return the writes putting ``value`` mod 256^length at ``start``."""
    r, c = start
    data = (value % (1 << 8 * length)).to_bytes(length, "big")
    return tuple(((r, c + i), byte) for i, byte in enumerate(data))


def _reads(state: _State, cell: Callable[[_Cell], int]) -> _Read:
    """Name the read the next command makes, if any."""
    r, c, done = state
    op = cell((r, c))
    if done or op not in _INPUTS:
        return None
    length = cell((r, c + 3))
    if _target((r, c), cell, 1) is None or not length:
        return None
    return _INPUTS[op], length


def _advance(
    state: _State, cell: Callable[[_Cell], int], data: tuple[int, ...] = ()
) -> tuple[_State, _Effects]:
    """Return the state after one command, its writes, and its output.

    Pure: ``cell`` only reads the grid, and ``data`` holds the bytes the
    shell read for an input command.
    """
    r, c, done = state
    if done:
        return state, ((), "")
    here = (r, c)
    op = cell(here)
    if op == _BLANK:
        return (r, c, True), ((), "")
    if op in _JUMPS:
        dr, dc = _JUMPS[op]
        count = cell((r, c + 1))
        return (r + dr * count, c + dc * count, False), ((), "")
    width = _OPERANDS.get(op >> 4)
    if width is None or (
        op not in _OUTPUTS
        and op not in _INPUTS
        and op not in _ARITHMETIC
        and op not in _COMPARISONS
    ):
        raise HaltError(
            f"byte {op:02X} at row {r}, column {c} is not a command",
            hint="run only 5x jumps, 0x, 1x, Ax, Cx commands and FF",
        )
    after = (r, c + 1 + width, False)
    if op in _OUTPUTS:
        source, length = _target(here, cell, 1), cell((r, c + 3))
        if source is None or not length:
            return after, ((), "")
        sr, sc = source
        raw = [cell((sr, sc + i)) for i in range(length)]
        if op == 0x00:
            text = str(_value(cell, source, length))
        elif op == 0x0A:
            text = "".join(map(chr, raw))
        else:
            text = "".join(f"{byte:02X}" for byte in raw)
        return after, ((), text)
    if op in _INPUTS:
        dest = _target(here, cell, 1)
        if dest is None or not data:
            return after, ((), "")
        dr0, dc0 = dest
        return after, (tuple(((dr0, dc0 + i), b) for i, b in enumerate(data)), "")
    if op in _ARITHMETIC:
        dest, length = _target(here, cell, 5), cell((r, c + 7))
        if dest is None or not length:
            return after, ((), "")
        first, second = _target(here, cell, 1), _target(here, cell, 3)
        a = 0 if first is None else _value(cell, first, length)
        b = 1 if second is None else _value(cell, second, length)
        if op in (0xA3, 0xA4) and not b:
            raise HaltError(
                f"A{op & 0xF} at row {r}, column {c} divides by zero",
                hint="make the second value nonzero",
            )
        return after, (_store(dest, _ARITHMETIC[op](a, b), length), "")
    first, second = _target(here, cell, 1), _target(here, cell, 3)
    length = cell((r, c + 5))
    when_true, when_false = _target(here, cell, 6), _target(here, cell, 8)
    if when_true is None or when_false is None:
        return after, ((), "")
    a = 0 if first is None else _value(cell, first, length)
    b = 0 if second is None else _value(cell, second, length)
    chosen = when_true if not length or _COMPARISONS[op](a, b) else when_false
    return (*chosen, False), ((), "")


_WORKSPACE_MODEL = WorkspaceModel(
    "bytemap-v1", ("row", "column", "stopped", "writes", "pending", "input_cursor")
)


class _Machine:
    """The pointer, the cells written over the source, and pending input bytes."""

    ip_shape = "grid"
    eof_is_a_value = True

    def __init__(self, code: str | dict[_Cell, int], io: IO) -> None:
        self.source = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.state: _State = (0, 0, False)
        #: Cells whose byte differs from the source's; equal writes drop out.
        self.writes: dict[_Cell, int] = {}
        #: UTF-8 bytes of a character read but not yet written.
        self.pending: tuple[int, ...] = ()
        self._read_prefix: list[int] = []
        self._rejected_input = RejectedInput()
        self._writer = _BufferedOutput()

    def cell(self, at: _Cell) -> int:
        """Return the byte at ``at``."""
        found = self.writes.get(at)
        return self.source.get(at, _BLANK) if found is None else found

    @property
    def halted(self) -> bool:
        return self.state[2]

    @property
    def ip(self) -> tuple[int, int] | None:
        """The pointer's row and column."""
        return None if self.halted else self.state[:2]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = self._rejected_input.snapshot(
            (
                *self.state,
                frozenset(self.writes.items()),
                self._pending_input(),
                self.io.progress(),
            )
        )
        accepted = self._writer.accepted
        return boundary if accepted is None else (*boundary, accepted)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture the pointer, the written cells and the input cursor."""
        cursor = self._rejected_input.cursor(self.io.progress())
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            row=self.state[0],
            column=self.state[1],
            stopped=self.state[2],
            writes=tuple(sorted(self.writes.items())),
            pending=self._pending_input(),
            input_cursor=pending_output_cursor(cursor, accepted),
        )

    def _pending_input(self) -> tuple[int, ...] | WorkspaceVariant:
        if not self._read_prefix:
            return self.pending
        return WorkspaceVariant(
            "pending_read", (self.pending, tuple(self._read_prefix))
        )

    def _byte(self) -> int:
        """Return the next input byte, or ``FF`` at EOF."""
        if not self.pending:
            try:
                char = self.io.input_char()
            except EOFError:
                return _BLANK
            try:
                self.pending = tuple(chr(char).encode())
            except UnicodeEncodeError as error:
                self._rejected_input.remember(error)
                raise
        byte, self.pending = self.pending[0], self.pending[1:]
        return byte

    @staticmethod
    def _hex_pair(first: int, second: int) -> int:
        """Return two input characters as one hex byte; invalid or EOF is FF."""
        digits = bytes((first, second)).decode("latin-1")
        return int(digits, 16) if all(d in _HEX for d in digits.upper()) else _BLANK

    def _read(self, kind: str, count: int) -> tuple[int, ...]:
        if kind in ("char", "hex"):
            self._rejected_input.raise_if_rejected()
            size = count * 2 if kind == "hex" else count
            prefix = self._read_prefix
            while len(prefix) < size:
                prefix.append(self._byte())
            data = (
                tuple(
                    self._hex_pair(prefix[i], prefix[i + 1]) for i in range(0, size, 2)
                )
                if kind == "hex"
                else tuple(prefix)
            )
            prefix.clear()
            return data
        try:
            number = self._rejected_input.read(self.io, self.io.input_num)
        except EOFError:
            return (_BLANK,) * count
        return tuple(byte for _at, byte in _store((0, 0), number, count))

    def step(self) -> None:
        """Run one command: read first if it reads, then write and print."""
        if self.halted:
            return
        read = _reads(self.state, self.cell)
        data = () if read is None else self._read(*read)
        state, (writes, text) = _advance(self.state, self.cell, data)
        if text:
            self._writer.write(self.io, text, first=lambda: self.io.print_str(text))
        for at, byte in writes:
            if self.source.get(at, _BLANK) == byte:
                self.writes.pop(at, None)
            else:
                self.writes[at] = byte
        self.state = state


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once; each IO port receives fresh machine state."""
    source = require_text_source(source, options, "Bytemap")
    grid = _parse(source)
    return RuntimePlan(lambda io: _Machine(grid, io), lambda io: _execute(grid, io))


def _execute(code: str | dict[_Cell, int], io: IO) -> CompletionReport:
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run ``code`` to completion on ``io``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
