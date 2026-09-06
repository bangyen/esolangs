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


#: Where :func:`_factorint` stops dividing by small primes and hands what
#: is left to sympy.  A Factor program is a product of *many small* primes
#: -- one per instruction, so the prime is bounded by the alphabet's reach
#: rather than by the program's length -- and the committed examples top
#: out at 6619 while running to 1276 digits.  Sieving to 10000 therefore
#: clears them entirely, and the general factorization behind it is what
#: keeps a number this does not suit correct rather than merely fast.
_SMALL_PRIME_LIMIT = 10000


def _factorint(number: int) -> dict[int, int]:
    """Factorize ``number``, dividing small primes out before sympy sees it.

    ``sympy.factorint`` is a general factorizer, and generality is the
    wrong tool for the shape Factor actually produces: the number is a
    product of a hundred-odd primes all under 7000, so the work is
    dividing them out, not finding them.  Walking the sieve and shrinking
    ``number`` as each comes out does that directly, and shrinks the
    operand fast, which matters because these are bignums -- 1276 digits
    for the committed boolean example -- where every ``%`` is priced by
    the number's length.  Measured 1.7x faster on both committed examples.

    Whatever is left after the sieve goes to ``sympy.factorint``: the
    residue may be a large prime, or composite with every factor past the
    limit, and neither is this loop's business.  So the answer is sympy's
    on any number this shape does not suit, and identical on the ones it
    does -- checked against ``factorint`` over 300 random integers plus
    products of large primes.
    """
    factors: dict[int, int] = {}
    for prime in sympy.sieve.primerange(2, _SMALL_PRIME_LIMIT):
        if prime * prime > number:
            break
        while not number % prime:
            factors[prime] = factors.get(prime, 0) + 1
            number //= prime
    if number > 1:
        for prime, exponent in sympy.factorint(number).items():
            factors[prime] = factors.get(prime, 0) + exponent
    return factors


def decode(number: int) -> str:
    """Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(_factorint(number).items())
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

    # The growth detector's view, forwarded like everything else here.
    # Factor has no execution semantics of its own -- it decodes a numeral
    # to brainfuck and runs that -- so it inherits brainfuck's eligibility
    # for ``esolangs.vm._TapeMachine`` exactly, rather than making a claim
    # of its own.

    @property
    def ptr(self) -> int:
        """The decoded machine's cell pointer."""
        return self.bf.ptr

    @property
    def tape(self) -> tuple[int, ...]:
        """The decoded machine's committed cells."""
        return self.bf.tape

    def input_position(self) -> int:
        """Report the decoded machine's input cursor."""
        return self.bf.input_position()

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
