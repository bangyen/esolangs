"""Two-sided bit tape, loop control and buffered little-endian byte I/O."""

from collections.abc import Mapping
from typing import NamedTuple

from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.bits import put_bit, take_bit
from esolangs.runtime.brackets import BracketProgram, match_brackets
from esolangs.runtime.io import IO, _BufferedOutput


class _State(NamedTuple):
    pc: int
    ptr: int
    incoming: int  # buffered input byte
    remaining: int  # input bits left in it
    outgoing: int  # output byte under construction
    used: int  # its filled bits


type _PendingFlush = tuple[_State, bool]


def _advance(
    state: _State, command: str, bit: int, brackets: Mapping[int, int]
) -> _State:
    """Advance control; tape writes and byte I/O are shell effects."""
    pc, ptr = state.pc, state.ptr
    if command == ">":
        ptr += 1
    elif command == "<":
        ptr -= 1
    elif command == "[" and not bit:
        pc = brackets[pc]
    elif command == "]":
        return _State(
            brackets[pc],
            state.ptr,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
    return _State(
        pc + 1, ptr, state.incoming, state.remaining, state.outgoing, state.used
    )


class _BitTapeMachine:
    """Bit tape and buffered byte streams."""

    eof_is_a_value = True
    set_command = "+"
    _workspace_model: WorkspaceModel

    def __init__(self, code: str | BracketProgram, io: IO) -> None:
        if isinstance(code, BracketProgram):
            self.code, self.brackets = code.source, code.brackets
        else:
            self.code, self.brackets = code, match_brackets(code)
        self.io = io
        self.state = _State(0, 0, 0, 0, 0, 0)
        self.ones: set[int] = set()
        self._writer = _BufferedOutput()
        self._pending_flush: _PendingFlush | None = None

    @property
    def halted(self) -> bool:
        return self.state.pc >= len(self.code)

    @property
    def ip(self) -> int:
        return self.state.pc

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def memory(self) -> list[int]:
        lo = min(self.ones | {self.state.ptr, 0})
        hi = max(self.ones | {self.state.ptr, 0})
        return [int(i in self.ones) for i in range(lo, hi + 1)]

    def snapshot(self) -> tuple[object, ...]:
        boundary = (self.state, frozenset(self.ones), self.io.progress())
        pending = self._output_progress()
        return boundary if pending is None else (*boundary, pending)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic control/buffers, set cells and consumed input."""
        state = self.state
        control = (
            state.pc,
            state.ptr,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
        pending = self._output_progress()
        return self._workspace_model.capture(
            control=(
                control
                if pending is None
                else WorkspaceVariant("pending_output", (control, pending))
            ),
            ones=frozenset(self.ones),
            input_cursor=self.io.progress(),
        )

    def _output_progress(self) -> tuple[object, ...] | int | None:
        accepted = self._writer.accepted or 0
        if self._pending_flush is not None:
            return (*self._pending_flush, accepted)
        return accepted or None

    def _write_byte(self, value: int) -> None:
        char = chr(value)
        self._writer.write(self.io, char, first=lambda: self.io.print_char(char))

    def _finish_flush(self, pending: _PendingFlush) -> None:
        state, changed_bit = pending
        self._write_byte(state.outgoing)
        if changed_bit:
            self.ones.symmetric_difference_update((self.state.ptr,))
        self.state = _State(state.pc, state.ptr, state.incoming, state.remaining, 0, 0)
        self._pending_flush = None

    def step(self) -> None:
        if self.halted:
            return
        if (pending := self._pending_flush) is not None:
            self._finish_flush(pending)
            return
        pc, ptr, incoming, remaining, outgoing, used = self.state
        command = self.code[pc]
        bit = int(ptr in self.ones)
        if command == self.set_command:
            self._set_bit(ptr)
        elif command == ",":
            if not remaining:
                try:
                    incoming = self.io.input_char() % 256
                except EOFError:
                    incoming = 0
                remaining = 8
            (incoming, remaining), read = take_bit((incoming, remaining))
            self._read_bit(ptr, read, bit)
        elif command == ";":
            (outgoing, used), full = put_bit((outgoing, used), bit)
            if full is not None:
                self._write_byte(full)
        state = _advance(
            _State(pc, ptr, incoming, remaining, outgoing, used),
            command,
            bit,
            self.brackets,
        )
        if used and state.pc >= len(self.code):
            # The final command may already have read a byte or changed a cell.
            # Stage both effects so retrying the flush cannot run it twice.
            changed_bit = bit != int(ptr in self.ones)
            if changed_bit:
                self.ones.symmetric_difference_update((ptr,))
            pending = (state, changed_bit)
            self._pending_flush = pending
            self._finish_flush(pending)
        else:
            self.state = state

    def _set_bit(self, ptr: int) -> None:
        self.ones.symmetric_difference_update((ptr,))

    def _read_bit(self, ptr: int, bit: int, _before: int) -> None:
        if bit:
            self.ones.add(ptr)
        else:
            self.ones.discard(ptr)
