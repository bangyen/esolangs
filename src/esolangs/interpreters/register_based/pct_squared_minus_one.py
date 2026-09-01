"""Interpreter for %^2^-1.

A single accumulator holding the magnitude ``x`` of a value ``10^x`` (the
wiki's workaround for avoiding huge numbers; the magnitude starts at 0).
``s``/``i`` subtract 2/3 (divide by 100/1000), ``m`` doubles (square), ``p``
negates (reciprocate), ``'`` zeroes it (set to 1), ``l``/``e`` print it
(decimal / as a byte), ``n`` reads one byte of input, and ``t`` rewinds to
the start of the program when the magnitude is nonzero.  The magnitude is
reset to zero whenever it exceeds 3003 (before each command).

Semantics:
- ``e`` prints the low byte, and ``l`` prints the signed magnitude;
- ``n`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3;
- ``t`` on a nonzero magnitude loops the program forever (the only loop).

The interpreter runs on a :class:`_Machine` (the code and the accumulator),
so it is step-capable: ``step()`` executes one command, applying the
over-3003 reset before the command as the original loop does, and ``halted``
is true once the cursor reaches the end of the program.
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run %^2^-1 state: the code, the accumulator, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the accumulator at zero."""
        self.io = io
        self.code = code
        self.acc = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: Accumulator + cursor; ip the cursor, memory the
    # accumulator.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.acc)

    def step(self) -> None:
        """Execute one command, resetting the accumulator first if too large."""
        if self.halted:
            return
        if self.acc > 3003:
            self.acc = 0

        char = self.code[self.ind]
        if char == "s":
            self.acc -= 2
        elif char == "i":
            self.acc -= 3
        elif char == "m":
            self.acc *= 2
        elif char == "p":
            self.acc *= -1
        elif char == "l":
            self.io.print_num(self.acc)
        elif char == "e":
            self.io.print_char(chr(self.acc & 0xFF))
        elif char == "n":
            self.acc = self.io.input_char()
        elif char == "'":
            self.acc = 0
        elif char == "t" and self.acc != 0:
            self.ind = 0
            return
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a %^2^-1 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
