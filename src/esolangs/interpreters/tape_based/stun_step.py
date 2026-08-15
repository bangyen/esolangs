"""Interpreter for Stun Step.

A tape language with four commands: ``+``/``-`` increment and decrement the
current cell, and ``>``/``<`` move the pointer right and left -- but only
while the current cell is nonzero.  Cells are 32-bit words that hold
nonnegative integers, initialized to 1 except the cell the pointer starts
on, which is 0.  There is no explicit flow control: once the program text
is consumed, execution loops back to the start unless the current cell is
0, in which case the machine halts.  Non-halting programs run forever, as
they do in the reference.

The wiki defines no I/O.  This interpreter, like the x86-32 reference in
``extra/assembly/stun-step-riscv.s``, has no input command; on halting it
prints the cells from the start position through the rightmost cell ever
reached as space-separated decimal values with no trailing separator.

The semantics match the reference exactly, including its implementation
artifact.  The reference stores its tape on the stack in the memory just
below the program text, so stepping left past the starting cell reads and
writes the bytes that hold the program's tail: applying ``+``/``-`` there
changes the cell as one little-endian 32-bit word *and* corrupts the
overlapping trailing program bytes, which later scans then read as (usually
non-command) data.  This interpreter reproduces that byte-level overlap
byte for byte, and cells wrap modulo 2**32 just like the reference's
dwords.

Because the reference treats a NUL (0x00) byte as the end of the program,
any NUL in the source truncates it, and every other byte that is not one of
the four commands is skipped.  The one divergence is the reference's fixed
emulated stack size: a program that walks far enough off either edge of the
stack page (a thousand or so cells right of the start, or a few dozen left)
faults on unmapped memory there, while this interpreter models an unbounded
tape and keeps running instead.
"""

import sys

from esolangs.interpreters.io import IO

PLUS, MINUS, RIGHT, LEFT = 43, 45, 62, 60


def run(code: str, io: IO) -> None:
    """Run a Stun Step program, printing the reached cells on halt."""
    data = code.encode()
    n = len(data)
    mem: dict[int, int] = {}
    for i, byte in enumerate(data):
        mem[5 + n - i] = byte
    mem[5] = 0

    def read_word(addr: int) -> int:
        return (
            mem.get(addr, 0)
            | mem.get(addr + 1, 0) << 8
            | mem.get(addr + 2, 0) << 16
            | mem.get(addr + 3, 0) << 24
        )

    def write_word(addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        for i in range(4):
            mem[addr + i] = (value >> (8 * i)) & 0xFF

    write_word(0, read_word(0) - 1)
    cell = 0
    position = 1
    extent = 1
    scan = 5 + n
    while True:
        byte = mem.get(scan, 0)
        if byte == PLUS:
            write_word(cell, read_word(cell) + 1)
        elif byte == MINUS:
            if read_word(cell) != 0xFFFFFFFF:
                write_word(cell, read_word(cell) - 1)
        elif byte == RIGHT:
            if read_word(cell) != 0xFFFFFFFF:
                position += 1
                cell -= 4
                if extent < position:
                    extent = position
        elif byte == LEFT:
            if cell != extent and read_word(cell) != 0xFFFFFFFF:
                position -= 1
                cell += 4
        elif byte == 0:
            if read_word(cell) & 0x80000000:
                break
            scan = 5 + n
            continue
        scan -= 1

    io.print_num((read_word(0) + 1) & 0xFFFFFFFF)
    for k in range(1, extent):
        io.print_str(" ")
        io.print_num((read_word(-4 * k) + 1) & 0xFFFFFFFF)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
