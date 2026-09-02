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
from esolangs.interpreters.memory import parse_int_memory as _parse

# The three store targets the wiki defines: base S*bleq, S*bl*q, Subl*q.
_STORES = ("a", "ab", "b")


#: One instant of a run: ``(mem, ip, halted)`` -- the self-modifying
#: memory, the instruction pointer, and whether a negative jump stopped the
#: run.  A value the transitions below map forward, never editing one in
#: place, with the memory as a ``tuple`` for the same reason.
#:
#: ``halted`` is carried because a jump to a negative address stops the run
#: with the pointer left where it was, so the position alone does not say.
type _State = tuple[tuple[int, ...], int, bool]


def _read(state: _State, addr: int, byte: int | None = None) -> int:
    """Read a value: a special address or a memory cell.

    ``byte`` is what the shell already took from the input port, since
    ``-2`` is the one address whose read consumes something.  An address
    past the end reads as zero; a negative one other than the two special
    cases is not an address at all.
    """
    mem, ip, _halted = state
    if addr == -1:
        return ip
    if addr == -2:
        return byte if byte is not None else 0
    if addr >= 0:
        return mem[addr] if addr < len(mem) else 0
    raise ValueError(f"invalid address {addr}")


def _write(state: _State, addr: int, value: int) -> _State:
    """Return ``state`` with ``addr`` set to ``value``.

    Writing ``-1`` moves the instruction pointer, which is what lets an
    S*bleq program compute where to go next; ``-2`` and ``-3`` are
    read-only ports and a write to either is discarded.
    """
    mem, ip, halted = state
    if addr >= 0:
        if addr >= len(mem):
            mem = (*mem, *([0] * (addr + 1 - len(mem))))
        return ((*mem[:addr], value, *mem[addr + 1 :]), ip, halted)
    if addr == -1:
        return (mem, value, halted)
    return state


def _advance(state: _State, store: str, byte: int | None = None) -> _State:
    """Return the state after executing one ``a b c`` instruction.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so the output port is the caller's business -- an instruction
    that writes one changes nothing but the pointer -- and the input port's
    byte arrives as ``byte``.

    The store variant decides where the difference lands: ``"a"`` writes
    only ``a``, while ``"ab"`` and ``"b"`` also write ``b`` when it is a
    real address.  A non-positive difference branches to ``c``, and a
    branch to a negative address halts.
    """
    mem, ip, _halted = state
    a, b, c = mem[ip], mem[ip + 1], mem[ip + 2]
    if a == -3 or b == -3:
        # The print already happened in the shell.
        return (mem, ip + 3, False)

    diff = _read(state, a, byte) - _read(state, b, byte)
    after = _write(state, a, diff)
    if store in ("ab", "b") and b >= 0:
        after = _write(after, b, diff)

    if diff > 0:
        return (after[0], after[1] + 3, False)
    target = _read(after, c)
    if target < 0:
        return (after[0], after[1], True)
    return (after[0], target, False)


@dataclass
class _Machine:
    io: IO
    mem: list[int] = field(default_factory=list)
    ip: int = 0
    store: str = "a"
    _halted: bool = field(default=False, init=False)

    @classmethod
    def of(cls, code: str, io: IO, store: str = "a") -> "_Machine":
        """Build a machine over the cells ``code`` parses to.

        The program is a list of integers, not text, so a caller cannot
        hand the source straight to the constructor.  Parsing lived in
        ``run`` and was copied into the VM adapter, which is the shape
        that lets two spellings of the same thing drift apart.
        """
        return cls(io=io, mem=_parse(code), store=store)

    def __post_init__(self) -> None:
        """Reject a store target outside the three documented variants.

        ``step`` tests ``store in ("ab", "b")``, so any other spelling --
        ``"A"``, ``""``, a typo -- silently ran the *base* language instead
        of raising.  A caller's mistake became a wrong answer rather than an
        error, so the set is checked once here, where it applies however the
        machine is constructed rather than only through :func:`run`.
        """
        if self.store not in _STORES:
            raise ValueError(f"unknown store target: {self.store!r}")

    @property
    def halted(self) -> bool:
        """Whether the instruction pointer has run off the program."""
        return self._halted or not (0 <= self.ip < len(self.mem) - 2)

    # The VM's language-shaped view: OISC cells + instruction pointer; memory is the
    # program memory.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.mem)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.mem), self.ip, self.io.position(), self._halted)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return (tuple(self.mem), self.ip, self._halted)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's constructor API, so they stay; the one
        assignment a step makes is here rather than scattered through the
        rules above.
        """
        mem, self.ip, self._halted = state
        self.mem = list(mem)

    def input_byte(self) -> int:
        # -2 returns the next byte of input; EOF reads as zero
        try:
            return ord(self.io.input_str()[0])
        except (EOFError, IndexError):
            return 0

    def output(self, value: int) -> None:
        self.io.print_char(chr(value & 0xFF))

    def step(self) -> None:
        """Execute one instruction (``a b c``), advancing or branching.

        The two ports live here rather than in the transition: this is the
        shell, so it is where an effect belongs.  ``-3`` in either operand
        slot prints the other, and ``-2`` in either is a read -- taken once
        here and handed over, since both operands consult the same byte.
        """
        if self.halted:
            return
        state = self._state
        mem = state[0]
        a, b = mem[self.ip], mem[self.ip + 1]
        if a == -3 or b == -3:
            other = b if a == -3 else a
            byte = self.input_byte() if other == -2 else None
            self.output(_read(state, other, byte))
            self._restore(_advance(state, self.store))
            return
        byte = self.input_byte() if -2 in (a, b) else None
        self._restore(_advance(state, self.store, byte))


def run(code: str, io: IO, store: str = "a") -> None:
    """Execute an S*bleq program.

    ``store`` selects the storage variant: ``"a"`` (base S*bleq), ``"ab"``
    (S*bl*q, stores in both a and b), or ``"b"`` (Subl*q, stores in b).
    """
    mach = _Machine.of(code, io, store=store)

    while not mach.halted:
        mach.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
