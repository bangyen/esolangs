"""Interpreter for Factor.

Brainfuck re-encoded as the prime factorization of one integer (decimal
digits; other characters are comments).  Primes ascending, residue mod 11
selects the command::

    residue   1   2   3   4   5   6   7   8
    command  >   <   +   -   .   ,   [   ]

The exponent is the repeat count; other residues are ignored.  Decoding is
delegated to the brainfuck interpreter (8-bit wrap, ``<`` clamp, matched
loops; unbalanced raises :class:`ValueError`).  No digits, 0 and 1 halt
with no output; ``,`` reads a line's first byte and raises
:class:`EOFError` when input runs out.  :class:`_Machine` wraps the
decoded brainfuck machine.
"""

import math
import re
import sys

import sympy

from esolangs.factor_primes import prime_segments
from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.brainfuck import _Machine as _BFMachine

_RESIDUE = {1: ">", 2: "<", 3: "+", 4: "-", 5: ".", 6: ",", 7: "[", 8: "]"}

#: Factor has no execution state beyond the Brainfuck machine it decodes to.
type _State = _BFMachine


#: Sieve batch size for :func:`_factorint`; not a ceiling.
_SIEVE_CHUNK = 20000

#: Residue width above which a chunk is tested by one gcd, not a remainder
#: per prime.  Pays only once the number dwarfs the chunk product; the
#: committed examples sit below it.
_BATCH_BITS = 8192

# SymPy proves ``isprime`` only through this range. Above it the final BPSW
# screen is probable-prime, which cannot decide an uncapped language decode.
_EXACT_ISPRIME_LIMIT = 1 << 64


def _parse(digits: str) -> int:
    """Read the program's integer, lifting CPython's digit limit to fit it.

    The 4300-digit cap is a DoS guard, not Factor's (n=5 parity is 12565
    digits); raised for this program and put back.
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

    The number is a product of many smallish primes (1276 digits for the
    committed example), so walk primes in order and shrink as each divides.
    Never stop at a fixed prime: the residue handed to ``factorint`` is then
    a large composite that sends it to Pollard rho for minutes (a 10000
    ceiling hung the sweep on a 3243-digit program with 80 primes above it).
    Chunks widen until the residue is prime or gone. Below 2**64, exact
    ``isprime`` is asked only after a *barren* chunk and once per residue;
    above it BPSW cannot certify a language decode, so the sieve continues.
    """
    factors: dict[int, int] = {}
    checked = 0
    segments = prime_segments(_SIEVE_CHUNK)
    while number > 1:
        _start, _stop, primes = next(segments)
        divided = False
        # One gcd per chunk: ``number % prime`` costs the width of
        # ``number``, and a worst-case generated integer has
        # Theta(T log T) digits and Theta(T) primes.  A prime
        # divides ``number`` iff it divides ``gcd(number, chunk product)``,
        # which is small.  Sound mid-chunk: only other primes are divided out.
        batched = bool(primes) and number.bit_length() >= _BATCH_BITS
        common = math.gcd(number, math.prod(primes)) if batched else 0
        # A barren chunk (gcd 1) still walks its primes so the root exit in
        # the loop is still asked; only the division is saved.
        for prime in primes:
            if number == 1:
                # Finished; the root check below would read 1 as a factor.
                break
            if prime * prime > number:
                # Nothing below the root divides it: prime, no ``isprime`` needed.
                factors[number] = factors.get(number, 0) + 1
                return factors
            if batched and common % prime:
                continue
            while not number % prime:
                factors[prime] = factors.get(prime, 0) + 1
                number //= prime
                divided = True
        if number == 1:
            break
        if divided:
            # Still finding factors: widen rather than pay ``isprime``.
            continue
        # Barren: the exact small-integer screen is worth it once per value.
        # Above its proven range, keep trial-dividing to preserve totality.
        if number != checked and number < _EXACT_ISPRIME_LIMIT:
            checked = number
            if sympy.isprime(number):
                factors[number] = factors.get(number, 0) + 1
                return factors
        # Composite above the sieve: widen. ``sympy.factorint`` here would
        # send the leftover to Pollard rho for minutes.
    return factors


def decode(number: int) -> str:
    """Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(_factorint(number).items())
    return "".join(_RESIDUE[p % 11] * exp for p, exp in factors if p % 11 in _RESIDUE)


class _Machine:
    """Per-run Factor state: the decoded brainfuck machine.

    ``halted`` and the snapshot are the underlying machine's.
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

    # VM view of the decoded brainfuck machine.

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

    # Forwarded: Factor inherits brainfuck's ``_TapeMachine`` eligibility.

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
