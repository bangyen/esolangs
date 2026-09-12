r"""Interpreter for Decleq."""

from __future__ import annotations

from esolangs._validate import check_address
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

_OUT = -2
_IN = -1

# : One instant of a run:.
# : self-modifying store.
# : returns a new one rather.
# : ``tuple`` for the same.
# :.
# : The memory is in the state.
# : rewrites it as it runs.
# : the store, and ``halted``.
# : length.
# : that agree on every cell.
#: different states.
# :.
# : A plain tuple rather than a.
# : unpacking in the functions.
# : ``NamedTuple.__new__`` is.
#: C-level.
type _State = tuple[int, tuple[int, ...]]


def _read(memory: tuple[int, ...], addr: int) -> int:
    r"""Return ``memory[addr]``, or zero when the address is out of range."""
    return memory[addr] if 0 <= addr < len(memory) else 0


def _written(memory: tuple[int, ...], addr: int, value: int) -> tuple[int, ...]:
    r"""Return ``memory`` with cell ``addr`` set to ``value``, growing if."""
    if addr < 0:
        if addr < -len(memory):
            # This used to be a bare.
            # package's one promise:.
            # caller as a raw traceback.
            raise HaltError(
                f"address {addr} is {-addr - len(memory)} cells past the "
                f"left end of a {len(memory)}-cell store"
            )
        addr += len(memory)
    elif addr >= len(memory):
        check_address(addr, "Decleq")
        memory = (*memory, *([0] * (addr + 1 - len(memory))))
    return (*memory[:addr], value, *memory[addr + 1 :])


def _operands(state: _State) -> tuple[int, int, int]:
    r"""Return the three cells of the instruction under the pointer."""
    pc, memory = state
    return (memory[pc], _read(memory, pc + 1), _read(memory, pc + 2))


def _advance(state: _State, byte: int | None = None) -> _State:
    r"""Return the state after executing the instruction under the pointer."""
    pc, memory = state
    a, b, c = _operands(state)
    if a == _OUT:
        return (pc + 3, memory)
    if a == _IN:
        # ``byte`` is what the shell.
        return (pc + 3, _written(memory, b, byte if byte is not None else 0))
    value = _read(memory, a) - 1
    memory = _written(memory, b, value)
    return (c if value <= 0 else pc + 3, memory)


class _Machine:
    r"""A Decleq run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` into memory and reset the pointer."""
        self.io = io
        self.state: _State = (0, tuple(_parse(code)))

    # The language's own names.
    # than fields of their own, so.

    @property
    def pc(self) -> int:
        return self.state[0]

    @pc.setter
    def pc(self, value: int) -> None:
        # Writable so a caller can.
        # that running the program.
        # tail below cell 6 is only.
        # become the input opcode.
        self.state = (value, self.state[1])

    @property
    def halted(self) -> bool:
        r"""Whether the pointer has moved off the end of memory."""
        pc, memory = self.state
        return pc < 0 or pc >= len(memory)

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The program counter."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        # A list, because that is what.
        # a tuple, and the VM copies.
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The memory is already a.
        # input cursor joins it because.
        # is not a real cycle.
        pc, memory = self.state
        return (memory, pc, self.io.position())

    def step(self) -> None:
        r"""Execute one instruction, advancing the pointer."""
        if self.halted:
            return
        a, b, _c = _operands(self.state)
        byte = None
        if a == _OUT:
            self.io.print_char(chr(_read(self.state[1], b) & 0xFF))
        elif a == _IN:
            byte = self.io.input_char()
        self.state = _advance(self.state, byte)


def run(code: str, io: IO) -> None:
    r"""Run a Decleq program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
