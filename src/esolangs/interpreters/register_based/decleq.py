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
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

_OUT = -2
_IN = -1


def run(code: str, io: IO, limit: int = 10_000) -> None:
    """Run a Decleq program, halting after ``limit`` instructions."""
    memory = _parse(code)
    pc = 0
    steps = 0

    while steps < limit:
        if pc < 0 or pc >= len(memory):
            return
        a = memory[pc]
        b = memory[pc + 1] if pc + 1 < len(memory) else 0
        c = memory[pc + 2] if pc + 2 < len(memory) else 0

        if a == _OUT:
            value = memory[b] if 0 <= b < len(memory) else 0
            io.print_char(chr(value & 0xFF))
            pc += 3
        elif a == _IN:
            byte = io.input_char()
            if b >= len(memory):
                memory.extend([0] * (b + 1 - len(memory)))
            memory[b] = byte
            pc += 3
        else:
            if b >= len(memory):
                memory.extend([0] * (b + 1 - len(memory)))
            va = memory[a] if 0 <= a < len(memory) else 0
            memory[b] = va - 1
            pc = c if memory[b] <= 0 else pc + 3
        steps += 1

    raise HaltError(f"execution exceeded the {limit}-instruction limit")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
