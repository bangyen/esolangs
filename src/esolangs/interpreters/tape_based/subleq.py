"""Subleq with unbounded integer cells and direct branch addresses.

The byte-I/O dialect uses -1 B C for input and A -1 C for output, advancing
after either. EOF raises EOFError. Negative jumps halt; reads beyond loaded
memory yield zero. A jump at or past the end of memory halts; writes past
the end grow memory and reads do not, so only written cells move that end.
Malformed source and negative data addresses raise ValueError. Incomplete
instruction fetches raise HaltError. Writes are effects so a packed table is
not copied at every arithmetic instruction.
"""

from esolangs._drive import drive
from esolangs._validate import check_address
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory
from esolangs.interpreters.source_hints import syntax_error

type _State = tuple[int]


def _advance(
    state: _State, instruction: tuple[int, int, int], values: tuple[int, int]
) -> tuple[_State, tuple[int, int] | None]:
    """Return the next pointer and optional memory write."""
    pc = state[0]
    a, b, c = instruction
    left, right = values
    if a == -1:
        return (pc + 3,), (b, left)
    if b == -1:
        return (pc + 3,), None
    result = right - left
    return (c if result <= 0 else pc + 3,), (b, result)


class _Machine:
    """Self-modifying memory and direct instruction pointer."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.cells = parse_int_memory(code)
        self.state: _State = (0,)
        self.io = io

    @property
    def pc(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        return self.pc < 0 or self.pc >= len(self.cells)

    @property
    def ip(self) -> int:
        return self.pc

    @property
    def memory(self) -> list[int]:
        return list(self.cells)

    def snapshot(self) -> tuple[object, ...]:
        return (tuple(self.cells), self.pc, self.io.position())

    def _read(self, address: int) -> int:
        if address < 0:
            raise syntax_error(
                f"invalid Subleq data address {address}",
                ("use a nonnegative data address; -1 is reserved for I/O"),
            )
        return self.cells[address] if address < len(self.cells) else 0

    def step(self) -> None:
        if self.halted:
            return
        if self.pc + 2 >= len(self.cells):
            raise HaltError(
                "incomplete Subleq instruction",
                hint="provide all three addresses for the fetched Subleq instruction",
            )
        a, b, c = self.cells[self.pc : self.pc + 3]
        if a == -1:
            if b < 0:
                raise syntax_error(
                    "Subleq input requires a nonnegative destination",
                    (
                        "use -1 as the input operand and a valid nonnegative "
                        "destination address"
                    ),
                )
            check_address(b, "Subleq")
            values = (self.io.input_char() % 256, 0)
        elif b == -1:
            value = self._read(a)
            self.io.print_char(chr(value % 256))
            values = (value, 0)
        else:
            values = (self._read(a), self._read(b))
        self.state, write = _advance(self.state, (a, b, c), values)
        if write is not None:
            address, value = write
            check_address(address, "Subleq")
            if address >= len(self.cells):
                self.cells.extend([0] * (address + 1 - len(self.cells)))
            self.cells[address] = value


def run(code: str, io: IO) -> None:
    """Run Subleq with direct jumps and byte I/O."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
