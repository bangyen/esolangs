r"""Interpreter for S*bleq.

A Subleq derivative: each instruction ``a b c`` does ``mem[a] -= mem[b]``
and, if the result is ``<= 0``, jumps to ``mem[c]`` (indirect); otherwise
the pointer advances by three.  Address ``-1`` is the instruction
pointer, ``-2`` the next input byte (zero at EOF, per the wiki), ``-3``
outputs the other operand; none appears in ``c``.  ``store`` selects the
base (``a``), ``S*bl*q`` (``a`` and ``b``) or ``Subl*q`` (``b``)
variant; the ``S**bleq`` indirection family is not implemented.

Programs are whitespace-separated integers loaded at address zero; reads
past the end are zero.  Execution halts off the end of the program or on
a negative jump target.  Malformed programs raise :class:`ValueError`.
"""

import sys
from typing import NamedTuple

from esolangs._validate import check_address
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
class _State(NamedTuple):
    """One instant of a run."""

    mem: tuple[int, ...]
    ip: int
    halted: bool


def _read(state: _State, addr: int, byte: int | None = None) -> int:
    """Read a value: a special address or a memory cell.

    ``byte`` is what the shell took from the input port for ``-2``.
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

    ``-1`` moves the instruction pointer; ``-2``/``-3`` writes are discarded.
    """
    mem, ip, halted = state
    if addr >= 0:
        if addr >= len(mem):
            check_address(addr, "S*bleq")
            mem = (*mem, *([0] * (addr + 1 - len(mem))))
        return _State((*mem[:addr], value, *mem[addr + 1 :]), ip, halted)
    if addr == -1:
        return _State(mem, value, halted)
    return state


def _advance(state: _State, store: str, byte: int | None = None) -> _State:
    """Return the state after executing one ``a b c`` instruction.

    Pure; output is the caller's, input arrives as ``byte``.  ``"ab"`` and
    ``"b"`` also write ``b`` when it is a real address.
    """
    mem, ip, _halted = state
    a, b, c = mem[ip], mem[ip + 1], mem[ip + 2]
    if a == -3 or b == -3:
        # The print already happened in the shell.
        return _State(mem, ip + 3, halted=False)

    diff = _read(state, a, byte) - _read(state, b, byte)
    after = _write(state, a, diff)
    if store in ("ab", "b") and b >= 0:
        after = _write(after, b, diff)

    if diff > 0:
        return _State(after[0], after[1] + 3, halted=False)
    target = _read(after, c)
    if target < 0:
        return _State(after[0], after[1], halted=True)
    return _State(after[0], target, halted=False)


class _Machine:
    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  Six languages do; the other 59 raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO, store: str = "a") -> None:
        """Build a machine over the cells ``code`` parses to."""
        self.io = io
        self.mem = tuple(_parse(code))
        self.ip = 0
        self.store = store
        self._halted = False
        if store not in _STORES:
            raise ValueError(f"unknown store target: {store!r}")

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
        return (self.mem, self.ip, self.io.position(), self._halted)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return _State(self.mem, self.ip, self._halted)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        mem, self.ip, self._halted = state
        self.mem = mem

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

        ``-3`` in either slot prints the other; ``-2`` in either is one
        read, shared by both operands.
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

    ``store`` is ``"a"`` (base), ``"ab"`` (S*bl*q) or ``"b"`` (Subl*q).
    """
    mach = _Machine(code, io, store=store)

    while not mach.halted:
        mach.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
