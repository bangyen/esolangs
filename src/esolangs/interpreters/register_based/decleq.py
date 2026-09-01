"""Interpreter for Decleq.

An OISC whose instruction ``a b c`` means ``b = a - 1`` and jumps to ``c``
if the new ``b`` is less than or equal to zero.  The program is a
self-modifying memory: the source file is a list of integers (whitespace-
separated, ``#`` comments allowed), the instruction pointer starts at 0, and
the instruction at address ``pc`` is the three cells
``memory[pc]..memory[pc+2]``, so the common countdown idiom is ``x x next``
(decrement ``x``, jump to ``next`` when it reaches zero).

Documented decisions for gaps in the wiki stub:
- ``a b c`` stores ``memory[a] - 1`` into ``memory[b]`` (the literal reading
  of "b = a - 1"; with ``a == b`` it is a plain decrement), then jumps to
  ``c`` when ``memory[b] <= 0`` and otherwise falls through three cells;
- the optional memory-mapped I/O is implemented: ``a = -2`` outputs
  ``memory[b]`` as a byte, ``a = -1`` reads a byte of input into
  ``memory[b]``, and both fall through rather than jump;
- cells are unbounded integers, the pointer halts when it moves off the end
  of memory, exhausted input raises :class:`EOFError` (repo-wide
  convention), and a program that has not halted after ``limit``
  instructions is rejected with :class:`HaltError`.

Malformed programs raise :class:`ValueError`.

The interpreter runs on a :class:`_Machine` (the self-modifying memory and
the instruction pointer), so it is step-capable: ``step()`` executes one
instruction and ``halted`` is true once the pointer moves off the end of
memory (every instruction decrements a cell, so a loop never revisits a
snapshot and the ``limit`` stays as the run() backstop for that class).
"""

from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse
from esolangs.interpreters.oisc_cli import main_with_limit, run_with_limit

_OUT = -2
_IN = -1


class _Machine:
    """Per-run Decleq state: the self-modifying memory and the pointer.

    ``step()`` executes one instruction; ``halted`` is true once the pointer
    moves off the end of memory.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer."""
        self.io = io
        self.memory: list[int] = _parse(code)
        self.pc = 0

    @property
    def halted(self) -> bool:
        """Whether the pointer has moved off the end of memory."""
        return self.pc < 0 or self.pc >= len(self.memory)

    # The VM's language-shaped view: OISC cells + program counter.
    # ``memory`` above already is the store, handed back live -- the VM
    # copies it on the way out.

    @property
    def ip(self) -> int:
        """The program counter."""
        return self.pc

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.memory), self.pc, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the pointer."""
        if self.halted:
            return
        a = self.memory[self.pc]
        b = self.memory[self.pc + 1] if self.pc + 1 < len(self.memory) else 0
        c = self.memory[self.pc + 2] if self.pc + 2 < len(self.memory) else 0

        if a == _OUT:
            value = self.memory[b] if 0 <= b < len(self.memory) else 0
            self.io.print_char(chr(value & 0xFF))
            self.pc += 3
        elif a == _IN:
            byte = self.io.input_char()
            if b >= len(self.memory):
                self.memory.extend([0] * (b + 1 - len(self.memory)))
            self.memory[b] = byte
            self.pc += 3
        else:
            if b >= len(self.memory):
                self.memory.extend([0] * (b + 1 - len(self.memory)))
            va = self.memory[a] if 0 <= a < len(self.memory) else 0
            self.memory[b] = va - 1
            self.pc = c if self.memory[b] <= 0 else self.pc + 3


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run a Decleq program, halting after ``limit`` instructions."""
    run_with_limit(_Machine(code, io), limit)


if __name__ == "__main__":
    main_with_limit(run)
