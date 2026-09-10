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


#: How far :func:`_factorint` extends its sieve at a time.  It keeps going
#: while the residue is still composite, so this is a batch size and not a
#: ceiling on the primes it will find.
_SIEVE_CHUNK = 20000


def _parse(digits: str) -> int:
    """Read the program's integer, lifting CPython's digit limit to fit it.

    ``int(str)`` refuses above ``sys.get_int_max_str_digits()`` (4300 by
    default) -- a CPython DoS guard against quadratic conversions, not
    anything Factor says.  A Factor program *is* one integer, so the guard
    caps the language at programs of 4300 digits: the n=5 parity table
    encodes to 12565.  The limit is raised to what this program needs and
    put back, since it is process-global and ours to borrow, not to keep.
    """
    limit = sys.get_int_max_str_digits()
    if len(digits) <= limit:
        return int(digits)
    sys.set_int_max_str_digits(len(digits) + 1)
    try:
        return int(digits)
    finally:
        sys.set_int_max_str_digits(limit)


def _factorint(number: int) -> dict[int, int]:
    """Factorize ``number``, dividing small primes out before sympy sees it.

    ``sympy.factorint`` is a general factorizer, and generality is the
    wrong tool for the shape Factor produces: the number is a product of
    many smallish primes -- one per instruction -- so the work is dividing
    them out, not searching for them.  Walking primes in order and
    shrinking ``number`` as each comes out does that directly, which
    matters because these are bignums (1276 digits for the committed
    boolean example) where every operation is priced by the length.

    The loop must not stop at a fixed prime, and that is the whole
    subtlety here.  A ceiling looks safe -- whatever is left just goes to
    sympy -- but it is not: the residue it hands over is then a *large
    composite* with every factor past the ceiling, which is the input
    ``factorint`` is worst at.  It abandons trial division for Pollard rho
    and takes minutes, where the same call on the original number takes
    milliseconds.  A 10000 ceiling did exactly that to the parity table
    whose 3243-digit program factors into 237 primes reaching 16189: 80 of
    them sat above the ceiling, and the sweep that runs it hung.

    So the sieve extends in chunks until the residue is prime or fully
    divided, and never hands a composite off to ``factorint`` because it
    gave up on it: a chunk that finds nothing widens the sieve instead.
    A genuinely hard number therefore sieves toward its own root rather
    than wedging in Pollard rho.  Such a wait can only be bounded from
    outside, by killing the subprocess: the cost is in this constructor and
    no step cap can reach it.

    Deciding that must not cost an ``isprime`` per chunk, and this is the
    subtlety that replaced the old one.  ``isprime`` runs BPSW -- a
    Miller-Rabin base-2 test and a Lucas test, each a modular
    exponentiation priced by the *full* width of its argument -- so asking
    it about a residue that is still tens of thousands of bits wide costs
    tens of seconds.  A loop that asks once per chunk pays that toll even
    though the sieve is what finds every factor: sieving to 58099 measures
    0.000s and the divisions 0.04s, against 60.02s for three ``isprime``
    calls on the n=5 parity table (12565 digits, 3000 primes reaching
    58099).  Dividing the small primes out first does not help either --
    the bit mass is in *large* primes with large exponents, so the residue
    after the first chunk is still 27412 of the original 41740 bits.

    So ``isprime`` is gated on a *barren* chunk -- a full chunk that
    divided nothing out -- and asked at most once per residue value.  That
    is exactly the signal its answer is worth paying for: every remaining
    factor is above the sieve, so the residue is either prime or hard.
    While chunks keep yielding factors the sieve is winning and is left
    alone, and a number of this shape reaches 1 without a barren chunk
    ever occurring.  Measured 60.0s -> 0.04s on n=5 parity, and the
    committed examples stay at 1.4ms.
    """
    factors: dict[int, int] = {}
    start = 2
    checked = 0
    while number > 1:
        stop = start + _SIEVE_CHUNK
        divided = False
        for prime in sympy.sieve.primerange(start, stop):
            if number == 1:
                # The chunk finished the number off; nothing is left to
                # test, and the root check below would read 1 as a factor.
                break
            if prime * prime > number:
                # Nothing below the root divides it, so the residue is
                # prime -- the one case worth taking without ``isprime``.
                factors[number] = factors.get(number, 0) + 1
                return factors
            while not number % prime:
                factors[prime] = factors.get(prime, 0) + 1
                number //= prime
                divided = True
        if number == 1:
            break
        if divided:
            # The sieve is still finding factors, so widen it rather than
            # pay ``isprime`` on a residue that is plainly composite.
            start = stop
            continue
        # A barren chunk: every remaining factor is above the sieve, so
        # the residue's primality is finally worth the BPSW test -- but
        # only once per value, since consecutive barren chunks would
        # otherwise re-ask the same question at the same full width.
        if number != checked:
            checked = number
            if sympy.isprime(number):
                factors[number] = factors.get(number, 0) + 1
                return factors
        # Composite, with every factor above the sieve.  Widening is the
        # only sound move: handing it to ``sympy.factorint`` here would
        # make the barren chunk a ceiling, and a ceiling's leftover is the
        # large composite that sends ``factorint`` to Pollard rho for
        # minutes -- the very failure the chunked sieve exists to avoid.
        start = stop
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
        number = _parse(digits) if digits else 1
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
