"""Interpreter for %^2^-1.

A single accumulator holding the magnitude ``x`` of a value ``10^x`` (the
wiki's workaround for avoiding huge numbers; the magnitude starts at 0).
``s``/``i`` subtract 2/3 (divide by 100/1000), ``m`` doubles (square), ``p``
negates (reciprocate), ``'`` zeroes it (set to 1), ``l``/``e`` print it
(decimal / as a byte), ``n`` reads one byte of input, and ``t`` rewinds to
the start of the program when the magnitude is nonzero.  The magnitude is
reset to zero whenever it exceeds 3003 (before each command).

Semantics match the C++ cross-check (``extra/c++/%^2^-1.cpp``):
- ``e`` prints the low byte, and ``l`` prints the signed magnitude;
- ``n`` raises :class:`EOFError` when input runs out, where the reference
  stores -1;
- ``t`` on a nonzero magnitude loops the program forever (the only loop).
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a %^2^-1 program."""
    acc = 0
    ind = 0
    n = len(code)

    while ind < n:
        if acc > 3003:
            acc = 0

        char = code[ind]
        if char == "s":
            acc -= 2
        elif char == "i":
            acc -= 3
        elif char == "m":
            acc *= 2
        elif char == "p":
            acc *= -1
        elif char == "l":
            io.print_num(acc)
        elif char == "e":
            io.print_char(chr(acc & 0xFF))
        elif char == "n":
            acc = io.input_char()
        elif char == "'":
            acc = 0
        elif char == "t" and acc != 0:
            ind = 0
            continue
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
