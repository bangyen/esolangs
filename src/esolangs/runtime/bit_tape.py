"""Two-sided bit tape, loop control and buffered little-endian byte I/O."""

from typing import NamedTuple

from esolangs.runtime.bits import flush_byte, put_bit, take_bit
from esolangs.runtime.brackets import match_brackets
from esolangs.runtime.io import IO


class _State(NamedTuple):
    pc: int
    ptr: int
    incoming: int  # buffered input byte
    remaining: int  # input bits left in it
    outgoing: int  # output byte under construction
    used: int  # its filled bits


def _advance(state: _State, command: str, bit: int, brackets: dict[int, int]) -> _State:
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

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = match_brackets(code)
        self.state = _State(0, 0, 0, 0, 0, 0)
        self.ones: set[int] = set()

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
        return (self.state, frozenset(self.ones), self.io.progress())

    def step(self) -> None:
        pc, ptr, incoming, remaining, outgoing, used = self.state
        if self.halted:
            return
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
                self.io.print_char(chr(full))
        self.state = _advance(
            _State(pc, ptr, incoming, remaining, outgoing, used),
            command,
            bit,
            self.brackets,
        )
        if self.state.pc >= len(self.code):
            full = flush_byte((outgoing, used))
            if full is not None:
                self.io.print_char(chr(full))
            self.state = _State(
                self.state.pc,
                self.state.ptr,
                self.state.incoming,
                self.state.remaining,
                0,
                0,
            )

    def _set_bit(self, ptr: int) -> None:
        self.ones.symmetric_difference_update((ptr,))

    def _read_bit(self, ptr: int, bit: int, _before: int) -> None:
        if bit:
            self.ones.add(ptr)
        else:
            self.ones.discard(ptr)
