"""BIO (Binary IO) interpreter implementation.

Register-based esoteric language with three memory blocks (x, y, z).
Uses commands in format [0|1][O|I][x|y|z] for increment/decrement, loops, and output.

The interpreter runs on a :class:`_Machine` (the three registers, the loop
stack, and the command cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
command list.  A loop whose body never changes a register grows the loop
stack and cursor without revisiting a snapshot only when a register grows
unboundedly (the ``run()`` backstop's class); a loop that revisits a
snapshot is proven by the state-cycle hang detector.

A loop ``{`` with no matching closer is a malformed program and is rejected
with :class:`ValueError`; popping an empty loop stack is an invalid operation
and halts the program with :class:`~esolangs.exceptions.HaltError`.
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


class _Machine:
    """Per-run BIO state: the registers, the loop stack, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the command list.  The VM and the state-cycle hang
    detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into commands and reset the registers."""
        self.io = io
        lang = "([01][oOiI][xXyYzZ]|})"
        self.commands = [k.lower() for k in re.findall(lang, code)]
        self.reg: list[int] = [0] * 3
        self.stk: list[int] = []
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the command list."""
        return self.ind >= len(self.commands)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.reg), tuple(self.stk), self.ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        r = "xyz".find(self.commands[self.ind][-1])
        c = self.commands[self.ind][:2]

        if c == "0o":
            self.reg[r] += 1
        elif c == "1o":
            self.reg[r] -= 1
        elif c == "1i":
            # Handle negative values by converting to unsigned 8-bit
            self.io.print_char(chr(self.reg[r] % 256))
        elif c == "}":
            if not self.stk:
                raise HaltError
            self.ind = self.stk.pop() - 1
        elif self.reg[r]:
            self.stk.append(self.ind)
        else:
            # Skip the loop block
            mat = 1
            while mat:
                self.ind += 1
                if self.ind == len(self.commands):
                    raise ValueError("unmatched '{'")
                c = self.commands[self.ind][:2]
                if c == "0i":
                    mat += 1
                elif c == "}":
                    mat -= 1
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Execute BIO code and produce output."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
