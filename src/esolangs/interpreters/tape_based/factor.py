"""Interpreter for Factor.

Factor is brainfuck re-encoded as the prime factorization of a single
integer.  The program text is decimal digits (every other character is a
comment and ignored); the integer's prime factors are sorted ascending, and
each prime's residue modulo 11 selects a brainfuck instruction:

    residue   1   2   3   4   5   6   7   8
    command  >   <   +   -   .   ,   [   ]

A prime's exponent is the number of times its instruction is carried out;
residues outside 1-8 are ignored.  Decoding is delegated to the brainfuck
interpreter, so the two agree on the 8-bit wrapping tape, the ``<`` clamp at
the left edge, and matching-bracket loops (an unbalanced program is
malformed and raises :class:`ValueError`).

Decisions for gaps in the wiki spec (documented):
- a program with no digits, and the integers 0 and 1, factor to no
  instructions and halt with no output;
- ``,`` reads a whole input line and takes its first byte, raising
  :class:`EOFError` when input runs out (the brainfuck interpreter's
  documented behavior).
"""

import re
import sys

import sympy

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.bf import run as run_bf

_RESIDUE = {1: ">", 2: "<", 3: "+", 4: "-", 5: ".", 6: ",", 7: "[", 8: "]"}


def decode(number: int) -> str:
    """Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(sympy.factorint(number).items())
    return "".join(_RESIDUE[p % 11] * exp for p, exp in factors if p % 11 in _RESIDUE)


def run(code: str, io: IO) -> None:
    """Run a Factor program, executing the brainfuck it decodes to."""
    digits = re.sub(r"[^0-9]", "", code)
    number = int(digits) if digits else 1
    run_bf(decode(number), io)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
