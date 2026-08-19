"""Interpreter for Minifuck.

A binary tape where [ skips the next instruction when the flipped bit is 0
and . prints the first eight cells as a binary byte (reading a byte of input
instead when the pool is zero).  < moves the pointer left.

The program is not implicitly looped: execution halts when the instruction
pointer reaches the end of the code (the wiki talk page leaves the question
open; this interpreter does not assume an implicit loop).

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run Minifuck state: the tape, pointer, and code cursor.

    ``step()`` executes one instruction; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object (the tape never rewinds, so a Minifuck program always
    halts).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell tape at the origin."""
        self.io = io
        self.code = code
        self.tape: list[int] = [0] * 8
        self.ptr = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.tape), self.ptr, self.ind, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor."""
        if self.halted:
            return
        ins = self.code[self.ind]
        if ins == "<" and self.ptr:
            self.ptr -= 1
        elif ins in ".[":
            self.ptr += 1
            if self.ptr + 1 >= len(self.tape):
                self.tape.append(0)
            self.tape[self.ptr] ^= 1

            if ins == ".":
                lst = map(str, self.tape[:8])
                if n := int("".join(lst), 2):
                    self.io.print_char(chr(n))
                else:
                    val = f"{self.io.input_char():08b}"
                    self.tape = [*map(int, val), *self.tape[8:]]
            elif not self.tape[self.ptr]:
                self.tape[self.ptr + 1] ^= 1
                self.ind += 1

        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a Minifuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
