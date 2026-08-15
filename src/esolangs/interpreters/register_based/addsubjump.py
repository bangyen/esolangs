"""Interpreter for AddSubJump (ASJ).

An OISC whose one instruction ``ASJ a b c d`` is ``if (*d > 0) {*a -= *b}
else {*a += *b}; goto c``.  The program is a self-modifying memory: the
source file is a list of integers (whitespace-separated, ``#`` comments
allowed) and the instruction pointer starts at 0, so the instruction at
address ``ip`` is the four cells ``memory[ip]..memory[ip+3]``.  Every cell
is an address into the same memory, and a few addresses are special:
``-1`` is I/O (reading it returns the next input byte, writing to it prints
a byte), ``-2``..``-5`` are the Carry/Zero/Negative/Overflow flags,
``-6``/``-7``/``-8`` are the constants 1/0/-1, and ``-9`` is the flag
update mode (flags are only refreshed while it is nonzero).  Jumping to a
special address, or off the end of memory, halts.

Documented decisions for gaps in the wiki spec:
- memory cells are unbounded integers (the wiki's Turing-completeness
  claim), so the Carry and Overflow flags stay 0 and only Zero/Negative
  are meaningful;
- the flag update mode starts 0, so flags are not updated unless the
  program writes ``-9``;
- writing to ``-1`` prints the operand ``*b`` (the wiki's own example
  ``-1 1 0 -7`` "outputs memory address 1"), and reading ``-1`` consumes
  a byte of input, raising :class:`EOFError` when input runs out (repo-wide
  convention);
- a non-numeric token is malformed (:class:`ValueError`), and a program
  that has not halted after ``limit`` instructions is rejected with
  :class:`HaltError` (the wiki has no termination convention beyond falling
  off the special addresses).
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

_IO = -1
_CF, _ZF, _NF, _OF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an AddSubJump program, halting after ``limit`` instructions."""
    memory = _parse(code)
    cf = zf = nf = of = fum = 0
    ip = 0
    steps = 0

    def read(addr: int) -> int:
        if addr == _IO:
            return io.input_char()
        if addr == _CF:
            return cf
        if addr == _ZF:
            return zf
        if addr == _NF:
            return nf
        if addr == _OF:
            return of
        if addr == _ONE:
            return 1
        if addr == _ZERO:
            return 0
        if addr == _NEG:
            return -1
        if addr == _FUM:
            return fum
        if 0 <= addr < len(memory):
            return memory[addr]
        return 0

    def write(addr: int, value: int) -> None:
        nonlocal fum
        if addr == _IO:
            io.print_char(chr(value & 0xFF))
        elif addr in _SPECIAL:
            if addr == _FUM:
                fum = value
        else:
            if addr >= len(memory):
                memory.extend([0] * (addr + 1 - len(memory)))
            memory[addr] = value

    while steps < limit:
        if ip < 0 or ip >= len(memory):
            return
        a = memory[ip]
        b = memory[ip + 1] if ip + 1 < len(memory) else 0
        c = memory[ip + 2] if ip + 2 < len(memory) else 0
        d = memory[ip + 3] if ip + 3 < len(memory) else 0

        vd = read(d)
        vb = read(b)
        if a == _IO:
            new = vb
            write(_IO, new)
        elif vd > 0:
            new = read(a) - vb
            write(a, new)
        else:
            new = read(a) + vb
            write(a, new)

        if fum:
            zf = 1 if new == 0 else 0
            nf = 1 if new < 0 else 0
            cf = of = 0

        ip = read(c)
        if _FUM <= ip <= _IO:
            return
        steps += 1

    raise HaltError(f"execution exceeded the {limit}-instruction limit")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
