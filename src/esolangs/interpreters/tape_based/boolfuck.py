"""Boolfuck with a two-sided bit tape and little-endian byte I/O.

EOF supplies zero bits. Partial output bytes are padded at halt. Noncommands
are ignored; unmatched brackets raise ValueError. Unicode input is reduced
modulo 256, matching the package's byte interfaces.
"""

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import match_brackets
from esolangs.interpreters.io import IO

# pc, pointer, buffered input byte, remaining input bits, output byte, output bits
type _State = tuple[int, int, int, int, int, int]


def _advance(state: _State, command: str, bit: int, brackets: dict[int, int]) -> _State:
    """Advance control; tape writes and byte I/O are shell effects."""
    pc, ptr, incoming, remaining, outgoing, used = state
    if command == ">":
        ptr += 1
    elif command == "<":
        ptr -= 1
    elif command == "[" and not bit:
        pc = brackets[pc]
    elif command == "]":
        return (brackets[pc], ptr, incoming, remaining, outgoing, used)
    return (pc + 1, ptr, incoming, remaining, outgoing, used)


class _Machine:
    """Bit tape and buffered byte streams."""

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = match_brackets(code)
        self.state: _State = (0, 0, 0, 0, 0, 0)
        self.ones: set[int] = set()

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.code)

    @property
    def ip(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def memory(self) -> list[int]:
        lo = min(self.ones | {self.state[1], 0})
        hi = max(self.ones | {self.state[1], 0})
        return [int(i in self.ones) for i in range(lo, hi + 1)]

    @property
    def stack(self) -> list[object]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, frozenset(self.ones), self.io.position())

    def step(self) -> None:
        pc, ptr, incoming, remaining, outgoing, used = self.state
        if self.halted:
            return
        command = self.code[pc]
        bit = int(ptr in self.ones)
        if command == "+":
            self.ones.symmetric_difference_update((ptr,))
        elif command == ",":
            if not remaining:
                try:
                    incoming = self.io.input_char() % 256
                except EOFError:
                    incoming = 0
                remaining = 8
            if incoming & 1:
                self.ones.add(ptr)
            else:
                self.ones.discard(ptr)
            incoming >>= 1
            remaining -= 1
        elif command == ";":
            outgoing |= bit << used
            used += 1
            if used == 8:
                self.io.print_char(chr(outgoing))
                outgoing = used = 0
        self.state = _advance(
            (pc, ptr, incoming, remaining, outgoing, used), command, bit, self.brackets
        )
        if self.state[0] >= len(self.code) and used:
            self.io.print_char(chr(outgoing))
            pc, ptr, incoming, remaining, _outgoing, _used = self.state
            self.state = (pc, ptr, incoming, remaining, 0, 0)


def run(code: str, io: IO) -> None:
    """Execute Boolfuck and flush its final partial byte."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
