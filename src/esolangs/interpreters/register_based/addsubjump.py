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
  off the special addresses);
- a *value* is an unbounded integer, but a write to an address too large
  to allocate halts with :class:`HaltError`: the cell is unbounded, the
  list of cells is not.

The interpreter runs on a :class:`_Machine` (memory, instruction pointer,
and flags), so it is step-capable: ``step()`` executes one instruction and
``halted`` is true once the pointer lands on a special address or off the
end of memory, making a repeating program a finite-state cycle the state
cycle detector can prove.
"""

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse
from esolangs.interpreters.oisc_cli import main_with_limit, run_with_limit

# The largest memory a run will grow.  Cell values are unbounded, but the
# list backing them is not: past this the allocation is one no machine
# would satisfy, so the run halts instead of raising OverflowError (or
# spending the box's memory finding out).
_MAX_MEMORY = 1 << 24

_IO = -1
_CF, _ZF, _NF, _OF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))


class _Machine:
    """Per-run ASJ state: the self-modifying memory, ip, and flags.

    ``step()`` executes one instruction; ``halted`` is true once the
    instruction pointer lands on a special address or off the end of memory.
    The VM and the state-cycle hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer and flags."""
        self.io = io
        self.memory: list[int] = _parse(code)
        self.cf = self.zf = self.nf = self.of = self.fum = 0
        self.ip = 0

    @property
    def halted(self) -> bool:
        """Whether the pointer is off the end of memory or a special address."""
        return self.ip < 0 or self.ip >= len(self.memory)

    # The VM's language-shaped view: self-modifying memory + instruction
    # pointer.  ``ip`` and ``memory`` above already *are* the view, so only
    # the empty stack needs saying -- the VM copies ``memory`` on the way
    # out, so handing back the live list here is safe.

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.memory),
            self.ip,
            self.cf,
            self.zf,
            self.nf,
            self.of,
            self.fum,
            self.io.position(),
        )

    def _read(self, addr: int) -> int:
        if addr == _IO:
            return self.io.input_char()
        if addr == _CF:
            return self.cf
        if addr == _ZF:
            return self.zf
        if addr == _NF:
            return self.nf
        if addr == _OF:
            return self.of
        if addr == _ONE:
            return 1
        if addr == _ZERO:
            return 0
        if addr == _NEG:
            return -1
        if addr == _FUM:
            return self.fum
        if 0 <= addr < len(self.memory):
            return self.memory[addr]
        return 0

    def _write(self, addr: int, value: int) -> None:
        if addr == _IO:
            self.io.print_char(chr(value & 0xFF))
        elif addr in _SPECIAL:
            if addr == _FUM:
                self.fum = value
        else:
            if addr >= len(self.memory):
                # Cell *values* are unbounded (above), but the memory
                # holding them is a real list: an address that cannot be
                # allocated is a resource the run does not have, so it
                # halts rather than raising Python's OverflowError.
                if addr + 1 > _MAX_MEMORY:
                    raise HaltError(f"memory address {addr} is too large")
                self.memory.extend([0] * (addr + 1 - len(self.memory)))
            self.memory[addr] = value

    def step(self) -> None:
        """Execute one instruction, advancing the pointer."""
        if self.halted:
            return
        a = self.memory[self.ip]
        b = self.memory[self.ip + 1] if self.ip + 1 < len(self.memory) else 0
        c = self.memory[self.ip + 2] if self.ip + 2 < len(self.memory) else 0
        d = self.memory[self.ip + 3] if self.ip + 3 < len(self.memory) else 0

        vd = self._read(d)
        vb = self._read(b)
        if a == _IO:
            new = vb
            self._write(_IO, new)
        elif vd > 0:
            new = self._read(a) - vb
            self._write(a, new)
        else:
            new = self._read(a) + vb
            self._write(a, new)

        if self.fum:
            self.zf = 1 if new == 0 else 0
            self.nf = 1 if new < 0 else 0
            self.cf = self.of = 0

        self.ip = self._read(c)


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an AddSubJump program, halting after ``limit`` instructions."""
    run_with_limit(_Machine(code, io), limit)


if __name__ == "__main__":
    main_with_limit(run)
