"""Interpreter for BFStack.

Brainfuck-style commands on a stack: > pushes 0, < pops, + and - adjust the
top, . prints it, , pushes a byte of input, and [ ] loop while the top is
nonzero.  A pop or output on an empty stack is invalid and halts the program.

The wiki does not specify the cell width for ``+``/``-``; this interpreter
wraps at 8 bits (mod 256).  It also raises :class:`EOFError` on exhausted
input, :class:`HaltError` on an invalid empty-stack operation, and
:class:`ValueError` on an unmatched ``[``.

The interpreter runs on a :class:`_Machine` (data stack, loop stack, and
cursor), so it is step-capable: ``step()`` executes one command and
``halted`` is true once the cursor reaches the end of the code, making a
``[`` loop whose top never zeroes a finite-state cycle the state cycle
detector can prove.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


class _Machine:
    """Per-run BFStack state: the data stack, loop stack, and cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an empty data stack and loop stack."""
        self.io = io
        self.code = code
        self.stk: list[int] = []
        self.lst: list[int] = []
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.stk), tuple(self.lst), self.ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        if (char := self.code[self.ind]) == ">":
            self.stk.append(0)
        elif char == "<":
            if not self.stk:
                raise HaltError
            self.stk.pop()
        elif char == "+":
            if not self.stk:
                raise HaltError
            self.stk[-1] = (self.stk[-1] + 1) % 256
        elif char == "-":
            if not self.stk:
                raise HaltError
            self.stk[-1] = (self.stk[-1] - 1) % 256
        elif char == ".":
            if not self.stk:
                raise HaltError
            self.io.print_char(chr(self.stk[-1]))
        elif char == ",":
            self.stk.append(self.io.input_char())
        elif char == "[":
            if not self.stk:
                raise HaltError
            if self.stk[-1]:
                self.lst.append(self.ind)
            else:
                match = 1
                while match:
                    self.ind += 1
                    if self.ind == len(self.code):
                        raise ValueError("unmatched '['")
                    if (o := self.code[self.ind]) == "[":
                        match += 1
                    elif o == "]":
                        match -= 1
        elif char == "]":
            if not self.lst:
                raise HaltError
            self.ind = self.lst.pop() - 1

        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a BFStack program, halting on an invalid empty-stack operation."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
