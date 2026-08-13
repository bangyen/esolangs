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

Semantics match the Rust and Ruby cross-checks (``extra/rust/unsquare.rs``
and ``extra/ruby/unsquare.rb``):
- an empty-stack pop, a swap with fewer than two elements, an ``o`` on an
  empty stack, an unmatched ``<``, or a ``>`` with no matching ``<`` raise
  :class:`HaltError` (the references exit with status 3);
- ``i`` raises :class:`EOFError` when input runs out, where the references
  exit with status 3;
- ``i`` re-prompts on blank input lines.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run an Unsquare program."""
    stack: list[int] = []
    jumps: list[int] = []
    acc = 0
    ind = 0
    n = len(code)

    while ind < n:
        char = code[ind]
        if char == "O":
            stack.append(0)
        elif char == "I":
            stack.append(1)
        elif char == "A":
            if not stack:
                raise HaltError("empty stack")
            acc = stack.pop()
        elif char == "S":
            if len(stack) < 2:
                raise HaltError("swap needs two elements")
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif char == "+":
            acc += 2
        elif char == "-":
            acc -= 2
        elif char == "x":
            acc *= 2
        elif char == "P":
            stack.append(acc)
        elif char == "o":
            if not stack:
                raise HaltError("empty stack")
            value = stack[-1]
            codepoint = value & 0xFFFFFFFF
            if codepoint <= 0x10FFFF and not 0xD800 <= codepoint <= 0xDFFF:
                io.print_char(chr(codepoint))
            else:
                io.print_num(value)
        elif char == "i":
            line = io.input_str("Input: ")
            while not line.strip():
                line = io.input_str("Input: ")
            stack.append(ord(line[0]))
        elif char == ">":
            if acc == 0 or acc == 1:
                num = 1
                while num > 0:
                    ind += 1
                    if ind >= n:
                        raise HaltError("unmatched >")
                    inner = code[ind]
                    if inner == ">":
                        num += 1
                    elif inner == "<":
                        num -= 1
            else:
                jumps.append(ind - 1)
        elif char == "<":
            if not jumps:
                raise HaltError("unmatched <")
            ind = jumps.pop()
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
