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


#: One instant of a run: ``(memory, ip, cf, zf, nf, of, fum)`` -- the
#: self-modifying store, the instruction pointer, the four flags, and the
#: flag-update mode.  A value, not a record: every transition below returns
#: a new one rather than editing one in place, and the memory is a ``tuple``
#: for the same reason.
#:
#: The memory is in the state rather than beside it because this language
#: rewrites it as it runs *and* can extend it: a write past the end grows
#: the store, and ``halted`` compares the pointer against the current
#: length.
type _State = tuple[tuple[int, ...], int, int, int, int, int, int]


def _operands(state: _State) -> tuple[int, int, int, int]:
    """Return the four cells of the instruction under the pointer.

    A trailing instruction that runs off the end reads its missing operands
    as zero.
    """
    memory, ip = state[0], state[1]
    return (
        memory[ip],
        memory[ip + 1] if ip + 1 < len(memory) else 0,
        memory[ip + 2] if ip + 2 < len(memory) else 0,
        memory[ip + 3] if ip + 3 < len(memory) else 0,
    )


def _load(state: _State, addr: int, byte: int | None = None) -> int:
    """Return the value at ``addr``, which may be a special register.

    ``byte`` is what the shell already read from the input port, since the
    port is the one address whose read consumes something.  Everything
    else is a pure lookup, and an address outside the store reads as zero.
    """
    memory, _ip, cf, zf, nf, of, fum = state
    if addr == _IO:
        return byte if byte is not None else 0
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
    return memory[addr] if 0 <= addr < len(memory) else 0


def _too_large(state: _State, addr: int) -> bool:
    """Whether writing ``addr`` would grow the store past what is allowed.

    Cell *values* are unbounded, but the memory holding them is a real
    list: an address that cannot be allocated is a resource the run does
    not have, so the caller halts rather than raising Python's
    ``OverflowError``.
    """
    memory = state[0]
    return (
        addr != _IO
        and addr not in _SPECIAL
        and addr >= len(memory)
        and addr + 1 > _MAX_MEMORY
    )


def _store(state: _State, addr: int, value: int) -> _State:
    """Return ``state`` with ``addr`` set to ``value``.

    Writing the input/output port is an effect and changes no state, so it
    is the shell's; writing a special register other than ``fum`` is
    discarded, as it always was.
    """
    memory, ip, cf, zf, nf, of, fum = state
    if addr == _IO:
        return state
    if addr in _SPECIAL:
        return (memory, ip, cf, zf, nf, of, value) if addr == _FUM else state
    if addr >= len(memory):
        memory = (*memory, *([0] * (addr + 1 - len(memory))))
    memory = (*memory[:addr], value, *memory[addr + 1 :])
    return (memory, ip, cf, zf, nf, of, fum)


def _advance(state: _State, reads: tuple[int, ...]) -> tuple[int, _State]:
    """Return the value the instruction computed, and the state after it.

    Pure: it reads ``state`` and returns a new one.  ``reads`` holds the
    bytes the shell already took from the input port, in the order the
    operands name it, so nothing here consumes anything.

    The value comes back alongside because writing the port is the shell's
    effect and it needs what to write.

    An instruction subtracts when ``memory[d]`` is positive and adds
    otherwise; writing to the port is neither, and simply passes ``vb``
    through.
    """
    pending = list(reads)

    def take(addr: int) -> int:
        return _load(state, addr, pending.pop(0) if addr == _IO else None)

    a, b, c, d = _operands(state)
    vd = take(d)
    vb = take(b)
    if a == _IO:
        value = vb
    else:
        va = take(a)
        value = va - vb if vd > 0 else va + vb

    after = _store(state, a, value)
    memory, _ip, cf, zf, nf, of, fum = after
    if fum:
        zf = 1 if value == 0 else 0
        nf = 1 if value < 0 else 0
        cf = of = 0
    after = (memory, _ip, cf, zf, nf, of, fum)
    return value, (memory, _load(after, c), cf, zf, nf, of, fum)


class _Machine:
    """Per-run ASJ state: the self-modifying memory, ip, and flags.

    ``step()`` executes one instruction; ``halted`` is true once the
    instruction pointer lands on a special address or off the end of memory.
    The VM and the state-cycle hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer and flags."""
        self.io = io
        self.state: _State = (tuple(_parse(code)), 0, 0, 0, 0, 0, 0)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def memory(self) -> list[int]:
        """The self-modifying store."""
        return list(self.state[0])

    @property
    def ip(self) -> int:
        """The instruction pointer."""
        return self.state[1]

    @property
    def cf(self) -> int:
        return self.state[2]

    @property
    def zf(self) -> int:
        return self.state[3]

    @property
    def nf(self) -> int:
        return self.state[4]

    @property
    def of(self) -> int:
        return self.state[5]

    @property
    def fum(self) -> int:
        """Whether the flags follow each instruction's result."""
        return self.state[6]

    @property
    def halted(self) -> bool:
        """Whether the pointer is off the end of memory or a special address."""
        memory, ip = self.state[0], self.state[1]
        return ip < 0 or ip >= len(memory)

    # The VM's language-shaped view: self-modifying memory + instruction
    # pointer.  ``ip`` and ``memory`` above already *are* the view, so only
    # the empty stack needs saying.

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands plus the input cursor: a repeat that
        # ignores consumed input is not a real cycle.
        return (*self.state, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the pointer.

        The two memory-mapped I/O effects and the memory-limit halt live
        here rather than in the transition: this is the shell, so it is
        where an effect or a raise belongs.

        Reading is what makes that awkward.  Address ``-1`` *is* the input
        port, so a read of it consumes a byte -- and one instruction reads
        up to three operands, any of which may name it.  They are taken
        here in the order the transition will use them (``d``, then ``b``,
        then ``a`` unless ``a`` is the port itself, which is written rather
        than read) and passed along, so the transition consumes nothing.
        """
        if self.halted:
            return
        a, b, _c, d = _operands(self.state)
        if _too_large(self.state, a):
            raise HaltError(f"memory address {a} is too large")
        reads = tuple(
            self.io.input_char()
            for addr in ((d, b) if a == _IO else (d, b, a))
            if addr == _IO
        )
        value, self.state = _advance(self.state, reads)
        if a == _IO:
            self.io.print_char(chr(value & 0xFF))


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run an AddSubJump program, halting after ``limit`` instructions."""
    run_with_limit(_Machine(code, io), limit)


if __name__ == "__main__":
    main_with_limit(run)
