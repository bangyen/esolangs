"""Interpreter for Unsquare.

A stack-based language with an accumulator.  ``O``/``I`` push 0/1, ``A``
pops the stack into the accumulator, ``S`` swaps the top two, ``+``/``-``/
``x`` add 2/subtract 2/double the accumulator, ``P`` pushes it, ``o`` prints
the top of the stack (without popping) as a character -- or as a decimal
value when it is not a valid code point -- and ``i`` reads a line of input,
re-prompting on blank lines, and pushes its first character.  ``>``/``<``
are a loop bracket pair: ``>`` skips forward to the matching ``<`` when the
accumulator is 0 or 1, otherwise it records its position and ``<`` jumps
back to it.

Semantics:
- an empty-stack pop, a swap with fewer than two elements, an ``o`` on an
  empty stack, an unmatched ``<``, or a ``>`` with no matching ``<`` raise
  :class:`HaltError` (the cross-check exits with status 3);
- ``i`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3;
- ``i`` re-prompts on blank input lines.

The interpreter runs on a :class:`_Machine` (the stack, jump-return stack,
accumulator, and code cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
program.  A ``>``/``<`` loop whose body leaves the accumulator, stack, and
jump stack exactly as they were (e.g. ``><`` with the accumulator outside
``{0, 1}``) is a genuine state cycle a repeated :meth:`_Machine.snapshot`
proves; a loop that keeps pushing to the stack is unbounded growth and
needs the wall-clock backstop instead.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


class _Machine:
    """Per-run Unsquare state: the stack, jump stack, accumulator, cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the program.  The state-cycle hang detector and the
    VM expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with empty stacks, a zero accumulator, at the first token."""
        self.io = io
        self.code = code
        self.stack: list[int] = []
        self.jumps: list[int] = []
        self.acc = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: accumulator + loop stack.  ``stack``
    # above already is the view, handed back live -- the VM copies what it
    # exposes, which is why the shape protocol asks only for a Sequence.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The accumulator, the only cell this language addresses."""
        return [self.acc]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.acc,
            tuple(self.stack),
            tuple(self.jumps),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        char = self.code[self.ind]
        if char == "O":
            self.stack.append(0)
        elif char == "I":
            self.stack.append(1)
        elif char == "A":
            if not self.stack:
                raise HaltError("empty stack")
            self.acc = self.stack.pop()
        elif char == "S":
            if len(self.stack) < 2:
                raise HaltError("swap needs two elements")
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
        elif char == "+":
            self.acc += 2
        elif char == "-":
            self.acc -= 2
        elif char == "x":
            self.acc *= 2
        elif char == "P":
            self.stack.append(self.acc)
        elif char == "o":
            if not self.stack:
                raise HaltError("empty stack")
            value = self.stack[-1]
            codepoint = value & 0xFFFFFFFF
            if codepoint <= 0x10FFFF and not 0xD800 <= codepoint <= 0xDFFF:
                self.io.print_char(chr(codepoint))
            else:
                self.io.print_num(value)
        elif char == "i":
            line = self.io.input_str()
            while not line.strip():
                line = self.io.input_str()
            self.stack.append(ord(line[0]))
        elif char == ">":
            if self.acc == 0 or self.acc == 1:
                num = 1
                while num > 0:
                    self.ind += 1
                    if self.ind >= len(self.code):
                        raise HaltError("unmatched >")
                    inner = self.code[self.ind]
                    if inner == ">":
                        num += 1
                    elif inner == "<":
                        num -= 1
            else:
                self.jumps.append(self.ind - 1)
        elif char == "<":
            if not self.jumps:
                raise HaltError("unmatched <")
            self.ind = self.jumps.pop()
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run an Unsquare program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
