"""Interpreter for Decleq.

An OISC: ``a b c`` sets ``b = a - 1`` and jumps to ``c`` if the new ``b``
is ``<= 0``.  Memory is self-modifying: the source is whitespace-separated
integers (``#`` comments), the instruction at ``pc`` is
``memory[pc..pc+2]``, and ``x x next`` is the countdown idiom.  A read out
of range is zero; a write past the right end grows the store; a write to
a negative address indexes from the right (growing leftwards would turn a
terminating program non-terminating), so a program can write to ``-1``
and read back ``0``; a write further left than the store halts with
:class:`~esolangs.exceptions.HaltError`.  Decisions:
``a = -2`` outputs ``memory[b]`` as a byte and ``a = -1`` reads one,
both falling through; cells are unbounded; the pointer halts off the end;
exhausted input raises :class:`EOFError`.  Malformed programs raise
:class:`ValueError`.  No instruction cap: a self-decrementing cell never
revisits a state on unbounded integers, and ``esolangs.run``'s
``timeout`` is the guard.  :func:`_advance` is pure over an immutable
``_State`` whose tuple memory is part of the state because it grows.
"""

from __future__ import annotations

from esolangs._validate import check_address
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

_OUT = -2
_IN = -1

#: ``(pc, memory)``: an immutable value, rebound per step.  Memory is in
#: the state because the program rewrites and extends it, and ``halted``
#: compares against the current length.  A plain tuple: ``NamedTuple``
#: construction is Python-level.
type _State = tuple[int, tuple[int, ...]]


def _read(memory: tuple[int, ...], addr: int) -> int:
    """Return ``memory[addr]``, or zero when the address is out of range."""
    return memory[addr] if 0 <= addr < len(memory) else 0


def _written(memory: tuple[int, ...], addr: int, value: int) -> tuple[int, ...]:
    """Return ``memory`` with cell ``addr`` set to ``value``, growing if needed.

    A negative ``addr`` indexes from the right (as a subscript did before the
    store became a tuple), since growing leftwards would make a terminating
    program non-terminating.
    """
    if addr < 0:
        if addr < -len(memory):
            # Was a bare ``IndexError`` (``run("Decleq", "4 -8")`` gave a traceback).
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
    """Return the three cells of the instruction under the pointer.

    Missing operands read as zero, per :func:`_read`.
    """
    pc, memory = state
    return (memory[pc], _read(memory, pc + 1), _read(memory, pc + 2))


def _advance(state: _State, byte: int | None = None) -> _State:
    """Return the state after executing the instruction under the pointer.

    Pure; ``-1``'s byte arrives as ``byte``.  Both I/O opcodes fall through;
    only the ordinary instruction branches, on the value it just wrote.
    """
    pc, memory = state
    a, b, c = _operands(state)
    if a == _OUT:
        return (pc + 3, memory)
    if a == _IN:
        # ``byte`` is what the shell read; the write can grow the store.
        return (pc + 3, _written(memory, b, byte if byte is not None else 0))
    value = _read(memory, a) - 1
    memory = _written(memory, b, value)
    return (c if value <= 0 else pc + 3, memory)


class _Machine:
    """A Decleq run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer."""
        self.io = io
        self.state: _State = (0, tuple(_parse(code)))

    # Views on the state.

    @property
    def pc(self) -> int:
        return self.state[0]

    @pc.setter
    def pc(self, value: int) -> None:
        # Writable so a test can place the pointer on an unreachable state.
        self.state = (value, self.state[1])

    @property
    def halted(self) -> bool:
        """Whether the pointer has moved off the end of memory."""
        pc, memory = self.state
        return pc < 0 or pc >= len(memory)

    # The VM's language-shaped view: OISC cells + program counter.

    @property
    def ip(self) -> int:
        """The program counter."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        # A list, as before the memory became a tuple; the VM copies it.
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Plus the input cursor: a repeat ignoring consumed input is not a cycle.
        pc, memory = self.state
        return (memory, pc, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the pointer.

        The shell does the two memory-mapped I/O opcodes.
        """
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
    """Run a Decleq program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
