r"""Interpreter for S*bleq.

S*bleq is a derivative of Subleq, an OISC whose single instruction subtracts
and branches when the result is less than or equal to zero.  Each instruction
is three addresses ``a b c``:

    mem[a] = mem[a] - mem[b]
    if mem[a] <= 0: ip = mem[c]     # indirect: jump to the value at c

The instruction pointer advances by three otherwise.  Three special addresses
take the place of I/O and the instruction pointer (and never appear in ``c``):

    -1  the instruction pointer itself
    -2  the next byte of user input
    -3  output the value at the other address in the instruction

The base S*bleq stores the difference in ``a``.  The wiki defines three
variations that only change the store target or add indirection: ``S*bl*q``
stores in both ``a`` and ``b``, ``Subl*q`` stores in ``b``, and the
``S**bleq`` family reads/writes through ``*a`` and ``*b``.  This interpreter
implements the base language; a ``store`` parameter selects the base or the
two store-target variations.

Programs are read as whitespace-separated integers and loaded into memory at
address zero.  Memory is unbounded; reads past the end of the program return
zero, matching the Subleq convention that an OISC memory is an infinite array
of cells.  Execution halts when the instruction pointer runs off the end of
the program, or when a ``c`` address holds a negative target (jumping to a
negative address).


Reading input (``-2``) past the end of the stream returns zero
at EOF (per the wiki); malformed programs raise :class:`ValueError`.
"""

import sys
from dataclasses import dataclass, field

from esolangs.interpreters.io import IO


@dataclass
class _Machine:
    io: IO
    mem: list[int] = field(default_factory=list)
    ip: int = 0
    store: str = "a"
    _halted: bool = field(default=False, init=False)

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has run off the program."""
        return self._halted or not (0 <= self.ip < len(self.mem) - 2)

    def read(self, addr: int) -> int:
        """Read a value: a special address or a memory cell."""
        if addr == -1:
            return self.ip
        if addr == -2:
            return self.input_byte()
        if addr >= 0:
            return self.mem[addr] if addr < len(self.mem) else 0
        raise ValueError(f"invalid address {addr}")

    def write(self, addr: int, value: int) -> None:
        if addr >= 0:
            while len(self.mem) <= addr:
                self.mem.append(0)
            self.mem[addr] = value
        elif addr == -1:
            self.ip = value
        # -2 (input) and -3 (output) are read-only special addresses

    def input_byte(self) -> int:
        # -2 returns the next byte of input; EOF reads as zero
        try:
            return ord(self.io.input_str()[0])
        except (EOFError, IndexError):
            return 0

    def output(self, value: int) -> None:
        self.io.print_char(chr(value & 0xFF))

    def step(self) -> None:
        """Execute one instruction (``a b c``), advancing or branching."""
        a = self.mem[self.ip]
        b = self.mem[self.ip + 1]
        c = self.mem[self.ip + 2]

        if a == -3:
            self.output(self.read(b))
            self.ip += 3
            return
        if b == -3:
            self.output(self.read(a))
            self.ip += 3
            return

        diff = self.read(a) - self.read(b)
        self.write(a, diff)
        if self.store in ("ab", "b") and b >= 0:
            self.write(b, diff)

        if diff <= 0:
            target = self.read(c)
            if target < 0:
                self._halted = True  # jumping to a negative address halts
                return
            self.ip = target
        else:
            self.ip += 3


def run(code: str, io: IO, store: str = "a") -> None:
    """Execute an S*bleq program.

    ``store`` selects the storage variant: ``"a"`` (base S*bleq), ``"ab"``
    (S*bl*q, stores in both a and b), or ``"b"`` (Subl*q, stores in b).
    """
    mach = _Machine(io=io, mem=[int(tok) for tok in code.split()], store=store)

    while not mach.halted:
        mach.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
