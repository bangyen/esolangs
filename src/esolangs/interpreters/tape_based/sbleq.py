r"""Interpreter for S*bleq."""

import sys

from esolangs._validate import check_address
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

# The three store targets the.
_STORES = ("a", "ab", "b")


# : One instant of a run:.
# : memory, the instruction.
# : run.
# : place, with the memory as a.
# :.
# : ``halted`` is carried.
# : with the pointer left where.
type _State = tuple[tuple[int, ...], int, bool]


def _read(state: _State, addr: int, byte: int | None = None) -> int:
    r"""Read a value: a special address or a memory cell."""
    mem, ip, _halted = state
    if addr == -1:
        return ip
    if addr == -2:
        return byte if byte is not None else 0
    if addr >= 0:
        return mem[addr] if addr < len(mem) else 0
    raise ValueError(f"invalid address {addr}")


def _write(state: _State, addr: int, value: int) -> _State:
    r"""Return ``state`` with ``addr`` set to ``value``."""
    mem, ip, halted = state
    if addr >= 0:
        if addr >= len(mem):
            check_address(addr, "S*bleq")
            mem = (*mem, *([0] * (addr + 1 - len(mem))))
        return ((*mem[:addr], value, *mem[addr + 1 :]), ip, halted)
    if addr == -1:
        return (mem, value, halted)
    return state


def _advance(state: _State, store: str, byte: int | None = None) -> _State:
    r"""Return the state after executing one ``a b c`` instruction."""
    mem, ip, _halted = state
    a, b, c = mem[ip], mem[ip + 1], mem[ip + 2]
    if a == -3 or b == -3:
        # The print already happened in.
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


class _Machine:
    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO, store: str = "a") -> None:
        r"""Build a machine over the cells ``code`` parses to."""
        self.io = io
        self.mem = tuple(_parse(code))
        self.ip = 0
        self.store = store
        self._halted = False
        if store not in _STORES:
            raise ValueError(f"unknown store target: {store!r}")

    @property
    def halted(self) -> bool:
        r"""Whether the instruction pointer has run off the program."""
        return self._halted or not (0 <= self.ip < len(self.mem) - 2)

    # The VM's language-shaped.
    # program memory.

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.mem)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (self.mem, self.ip, self.io.position(), self._halted)

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transitions work on."""
        return (self.mem, self.ip, self._halted)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        mem, self.ip, self._halted = state
        self.mem = mem

    def input_byte(self) -> int:
        # -2 returns the next byte of.
        try:
            return ord(self.io.input_str()[0])
        except (EOFError, IndexError):
            return 0

    def output(self, value: int) -> None:
        self.io.print_char(chr(value & 0xFF))

    def step(self) -> None:
        r"""Execute one instruction (``a b c``), advancing or branching."""
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
    r"""Execute an S*bleq program."""
    mach = _Machine(code, io, store=store)

    while not mach.halted:
        mach.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
