"""Interpreter for Decleq.

An OISC: ``a b c`` sets ``b = a - 1`` and jumps to ``c`` if the new ``b``
is ``<= 0``.  The source is whitespace-separated integers (``#``
comments) forming self-modifying memory; ``x x next`` is the countdown
idiom.  Unbounded cells; no instruction cap (a decrementing cell never
repeats a state), so ``esolangs.run``'s ``timeout`` is the guard.

``a = -2`` prints ``memory[b]`` as a byte, ``a = -1`` reads one Unicode
character code; both ignore ``c`` and fall through.

Errors:
    ProgramError: A source token that is not an integer.
    InputExhaustedError: ``a = -1`` at EOF.
    HaltError: A write past the left end of the store.
    InterpreterLimitError: A write that would grow the store past 2**24 cells.

Decisions:
    * The page is ten lines and names no halt: its optional I/O ("Memory-mapped
      I/O: It is optional / -2 b c Outputs b / -1 b c Set b to user input") is
      implemented, falling through where SUBBIG, whose assembly the example
      uses, jumps to ``c``.  Generated I/O sets ``c`` to the next
      instruction, so both readings run it (a clean room taking SUBBIG's
      looped on every row, 2026-10-30).
    * The pointer halts off the end of the store as it has grown (not of the
      source).  A read out of range is zero; a write past the end grows the
      store; a negative write indexes from the right (an error is the other
      reading).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.decleq.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime._validate import check_address
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer
from esolangs.runtime.memory import parse_int_memory as _parse

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
            raise HaltError(
                f"address {format_integer(addr)} is "
                f"{format_integer(-addr - len(memory))} cells past the "
                f"left end of a {len(memory)}-cell store",
                hint="keep the address inside the allocated store",
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


# :func:`_advance` is pure over an immutable ``_State``.
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


_WORKSPACE_MODEL = WorkspaceModel(
    "decleq-v1", ("memory", "instruction", "input_cursor")
)


class _Machine:
    """A Decleq run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str | tuple[int, ...], io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer."""
        self.io = io
        self.state: _State = (0, tuple(_parse(code)) if isinstance(code, str) else code)

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
        # A list; the VM copies it.
        return list(self.state[1])

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            memory=self.state[1],
            instruction=self.state[0],
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Plus the input cursor: a repeat ignoring consumed input is not a cycle.
        pc, memory = self.state
        return (memory, pc, self.io.progress())

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


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain an immutable parsed image; each invocation owns its run state."""
    if not isinstance(source, str):
        raise TypeError("decleq machines require text source")
    if options:
        raise TypeError("decleq machines accept no runtime options")

    image = tuple(_parse(source))

    def build(io: IO) -> _Machine:
        return _Machine(image, io)

    def execute(io: IO) -> CompletionReport:
        return drive(build(io), policy=CAPABILITIES.completion)

    return RuntimePlan(build, execute)


def _execute(code: str, io: IO) -> CompletionReport:
    """Run a Decleq program to completion."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Decleq program to completion."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
