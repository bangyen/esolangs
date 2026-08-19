"""Interpreter for NoComment.

The full wiki language (not a subset): a byte tape with a movable pointer,
plus a byte stack.  ``i``/``d`` increment/decrement the current cell, ``c``
clears it, ``l``/``r`` move the pointer (``l`` is a no-op at cell 0, ``r``
extends the tape), ``n`` pushes the current cell onto the stack, ``f`` pops
the stack into the current cell, ``s``/``b`` jump forward/backward by a
peeked stack value when the current cell is nonzero (``s`` skips X
instructions, ``b`` jumps back X-1), and ``o`` prints the current cell as a
byte.  The tape is a static 4096 bytes and the pointer wraps at both ends
(per the wiki, pointer overflow is legal and moves to the opposite end),
matching the RISC-V cross-check.

Per the wiki, any character that is not a command is an error (there are no
comments), and popping an empty stack is an error.  A malformed program
(unrecognized character) raises :class:`ValueError`; an invalid operation
(stack underflow) raises :class:`~esolangs.exceptions.HaltError`.

The interpreter runs on a :class:`_Machine` (the byte tape, the stack, and
the code cursor), so it is step-capable: ``step()`` executes one command and
``halted`` is true once the cursor reaches the end of the code.  A jump back
to a command that never changes state is a cycle the state-cycle hang
detector proves; the ``run()`` backstop stays for the unbounded-growth class.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_COMMANDS = "idclrnfsbo"

# The static tape size: the wiki says the memory space is static but does not
# give its size, so 4096 (matching the RISC-V cross-check's buffer) is used.
_TAPE = 4096


class _Machine:
    """Per-run NoComment state: the byte tape, the stack, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with a cleared tape at the origin."""
        self.io = io
        self.code = code
        self.tape: list[int] = [0] * _TAPE
        self.stack: list[int] = []
        self.ptr = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.tape),
            tuple(self.stack),
            self.ptr,
            self.ind,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]
        if c == "i":
            self.tape[self.ptr] = (self.tape[self.ptr] + 1) % 256
        elif c == "d":
            self.tape[self.ptr] = (self.tape[self.ptr] - 1) % 256
        elif c == "c":
            self.tape[self.ptr] = 0
        elif c == "l":
            self.ptr = (self.ptr - 1) % _TAPE  # pointer overflow wraps per the wiki
        elif c == "r":
            self.ptr = (self.ptr + 1) % _TAPE
        elif c == "n":
            self.stack.append(self.tape[self.ptr])
        elif c == "f":
            if not self.stack:
                raise HaltError
            self.tape[self.ptr] = self.stack.pop()
        elif c == "s":
            if self.tape[self.ptr] and self.stack:
                # skip X forward: the next command is at ind + X + 1
                target = self.ind + self.stack[-1] + 1
                if not 0 <= target < len(self.code):
                    raise HaltError
                self.ind += self.stack[-1]
        elif c == "b":
            if self.tape[self.ptr] and self.stack:
                # jump back X-1: the next command is at ind - X + 1
                target = self.ind - self.stack[-1] + 1
                if not 0 <= target < len(self.code):
                    raise HaltError
                self.ind -= self.stack[-1]
        elif c == "o":
            self.io.print_char(chr(self.tape[self.ptr]))
        else:
            raise ValueError(f"unrecognized NoComment command {c!r}")
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a NoComment program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
