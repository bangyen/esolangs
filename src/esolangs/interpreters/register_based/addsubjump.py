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
- a non-numeric token is malformed (:class:`ValueError`);
- the wiki has no termination convention beyond falling off the special
  addresses, so a program can loop without one.  There is no per-run
  instruction cap here: ``esolangs.run``'s ``timeout`` is the uniform
  wall-clock guard every language shares, and a per-language step cap
  duplicated it -- raising the same :class:`HaltError`, in the one
  process that already offers it.  A caller stepping this machine
  directly still has the state-cycle detector for the loops that revisit
  a state, and a self-modifying memory can also grow without one -- that
  class has no guard except the caller's own bound;
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

# The largest memory a run will grow.  Cell values are unbounded, but the
# list backing them is not: past this the allocation is one no machine
# would satisfy, so the run halts instead of raising OverflowError (or
# spending the box's memory finding out).
_MAX_MEMORY = 1 << 24

_IO = -1
_CF, _ZF, _NF, _VF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))


#: One instant of a run: ``(memory, ip, cf, zf, nf, vf, fum)`` -- the
#: self-modifying store, the instruction pointer, the four flags, and the
#: flag-update mode.  A value, not a record: every transition below returns
#: a new one rather than editing one in place, and the memory is copied on
#: write for the same reason.
#:
#: The memory is in the state rather than beside it because this language
#: rewrites it as it runs *and* can extend it: a write past the end grows
#: the store, and ``halted`` compares the pointer against the current
#: length.
#:
#: It is *sparse* -- ``(non-zero cells, allocated length)`` -- because the
#: addresses a program uses are unrelated to how many cells it fills: one
#: writing cell 999999 allocates a million and leaves all but a handful
#: zero.  The length is carried explicitly because it stays semantic (it is
#: what ``halted`` and the allocation cap test) and can no longer be read
#: off the container.  A ``dict`` is unhashable, so :meth:`_Machine.snapshot`
#: is what freezes it for the cycle detector.
type _Cells = tuple[dict[int, int], int]
type _State = tuple[_Cells, int, int, int, int, int, int]


def _pack(values: list[int]) -> _Cells:
    """Return ``values`` as the sparse store: non-zero cells, and the length.

    Zeros are dropped rather than stored, the same rule :func:`_store`
    applies to a write, so a parsed zero and a written zero are one state.
    """
    return ({i: v for i, v in enumerate(values) if v}, len(values))


def _operands(state: _State) -> tuple[int, int, int, int]:
    """Return the four cells of the instruction under the pointer.

    A trailing instruction that runs off the end reads its missing operands
    as zero.
    """
    (cells, length), ip = state[0], state[1]
    return (
        cells.get(ip, 0),
        cells.get(ip + 1, 0) if ip + 1 < length else 0,
        cells.get(ip + 2, 0) if ip + 2 < length else 0,
        cells.get(ip + 3, 0) if ip + 3 < length else 0,
    )


def _load(state: _State, addr: int, byte: int | None = None) -> int:
    """Return the value at ``addr``, which may be a special register.

    ``byte`` is what the shell already read from the input port, since the
    port is the one address whose read consumes something.  Everything
    else is a pure lookup, and an address outside the store reads as zero.
    """
    (cells, length), _ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return byte if byte is not None else 0
    if addr == _CF:
        return cf
    if addr == _ZF:
        return zf
    if addr == _NF:
        return nf
    if addr == _VF:
        return vf
    if addr == _ONE:
        return 1
    if addr == _ZERO:
        return 0
    if addr == _NEG:
        return -1
    if addr == _FUM:
        return fum
    return cells.get(addr, 0) if 0 <= addr < length else 0


def _too_large(state: _State, addr: int) -> bool:
    """Whether writing ``addr`` would grow the store past what is allowed.

    Cell *values* are unbounded, but the memory holding them is a real
    list: an address that cannot be allocated is a resource the run does
    not have, so the caller halts rather than raising Python's
    ``OverflowError``.
    """
    _cells, length = state[0]
    return (
        addr != _IO
        and addr not in _SPECIAL
        and addr >= length
        and addr + 1 > _MAX_MEMORY
    )


def _store(state: _State, addr: int, value: int) -> _State:
    """Return ``state`` with ``addr`` set to ``value``.

    Writing the input/output port is an effect and changes no state, so it
    is the shell's; writing a special register other than ``fum`` is
    discarded, as it always was.

    The store is sparse -- a dict of the non-zero cells plus the allocated
    length -- because the memory is addressed, not packed: a program that
    writes cell 999999 allocates a million cells and leaves all but a
    handful zero, and rebuilding a dense tuple per write cost 4.6ms a step.
    Copy-on-write over the non-zero cells is O(live cells) instead.

    A zero **deletes** its key rather than storing it, so that a cell
    written to zero and a cell never written compare and hash alike; two
    equal memories that disagreed on which keys exist would break the state
    cycle detector silently.  :func:`_pack` applies the same rule to the
    initial parse.
    """
    (cells, length), ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return state
    if addr in _SPECIAL:
        return (state[0], ip, cf, zf, nf, vf, value) if addr == _FUM else state
    if addr >= length:
        length = addr + 1
    new = dict(cells)
    if value:
        new[addr] = value
    else:
        new.pop(addr, None)
    return ((new, length), ip, cf, zf, nf, vf, fum)


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
    memory, _ip, cf, zf, nf, vf, fum = after
    if fum:
        zf = 1 if value == 0 else 0
        nf = 1 if value < 0 else 0
        cf = vf = 0
    after = (memory, _ip, cf, zf, nf, vf, fum)
    return value, (memory, _load(after, c), cf, zf, nf, vf, fum)


class _Machine:
    """Per-run ASJ state: the self-modifying memory, ip, and flags.

    ``step()`` executes one instruction; ``halted`` is true once the
    instruction pointer lands on a special address or off the end of memory.
    The VM and the state-cycle hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer and flags."""
        self.io = io
        self.state: _State = (_pack(list(_parse(code))), 0, 0, 0, 0, 0, 0)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def memory(self) -> list[int]:
        """The self-modifying store, densified.

        The state holds it sparsely; this materializes every cell, so it
        is a debugging and test view rather than something a step uses.
        """
        cells, length = self.state[0]
        return [cells.get(i, 0) for i in range(length)]

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
    def vf(self) -> int:
        """The Overflow flag (``VF``, address -5)."""
        return self.state[5]

    @property
    def fum(self) -> int:
        """Whether the flags follow each instruction's result."""
        return self.state[6]

    @property
    def halted(self) -> bool:
        """Whether the pointer is off the end of memory or a special address."""
        (_cells, length), ip = self.state[0], self.state[1]
        return ip < 0 or ip >= length

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
        #
        # The sparse store's dict is unhashable and its iteration order
        # follows insertion, so equal memories reached by different write
        # orders would freeze differently.  Sorting the items is what makes
        # the key depend on the contents alone -- and sorted items rather
        # than a frozenset because a frozenset's repr is unstable across
        # processes, which the mutation baselines compare.
        (cells, length) = self.state[0]
        return (
            tuple(sorted(cells.items())),
            length,
            *self.state[1:],
            self.io.position(),
        )

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


def run(code: str, io: IO) -> None:
    """Run an AddSubJump program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
