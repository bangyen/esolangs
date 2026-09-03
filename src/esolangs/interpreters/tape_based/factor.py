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

The interpreter runs on a :class:`_Machine` wrapping the decoded brainfuck
machine, so it is step-capable: ``step()`` executes one decoded command and
``halted`` is the underlying brainfuck machine's.  The state-cycle hang
detector and the VM expose this object.
"""

import re
import sys

import sympy

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainfuck import _Machine as _BFMachine

_RESIDUE = {1: ">", 2: "<", 3: "+", 4: "-", 5: ".", 6: ",", 7: "[", 8: "]"}

#: Factor has no execution state beyond the Brainfuck machine it decodes to.
type _State = _BFMachine


def decode(number: int) -> str:
    """Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(sympy.factorint(number).items())
    return "".join(_RESIDUE[p % 11] * exp for p, exp in factors if p % 11 in _RESIDUE)


class _Machine:
    """Per-run Factor state: the decoded brainfuck machine.

    ``step()`` executes one decoded command; ``halted`` is the underlying
    brainfuck machine's.  The VM and the state-cycle hang detector expose
    this object (the decoded program is fixed, so the brainfuck machine's
    snapshot is the complete state).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Decode ``code`` and reset the underlying brainfuck machine."""
        self.io = io
        digits = re.sub(r"[^0-9]", "", code)
        number = int(digits) if digits else 1
        self.state: _State = _BFMachine(decode(number), io)

    @property
    def bf(self) -> _State:
        """The delegated Brainfuck state."""
        return self.state

    @property
    def halted(self) -> bool:
        return self.bf.halted

    # The VM's language-shaped view: Decoded brainfuck machine; ip the cursor, memory
    # the tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.bf.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.bf.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def step(self) -> None:
        self.bf.step()

    def snapshot(self) -> tuple[object, ...]:
        return self.bf.snapshot()


def run(code: str, io: IO) -> None:
    """Run a Factor program, executing the brainfuck it decodes to."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
