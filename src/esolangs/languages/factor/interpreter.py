"""Interpreter for Factor.

Brainfuck re-encoded as the prime factorization of one integer (decimal
digits; other characters are comments).  Primes ascending, residue mod 11
selects the command (``> < + - . , [ ]`` for residues 1-8); the exponent
is the repeat count, other residues are ignored.  Decoding delegates to
the brainfuck interpreter.  No digits, 0 and 1 halt with no output.
"""

import math
import re

from esolangs.factor_primes import isprime64 as _isprime64
from esolangs.factor_primes import prime_segments
from esolangs.languages.brainfuck.interpreter import _Machine as _BFMachine
from esolangs.runtime._digits import digit_limit_for
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

#: A prime's residue mod ``_MODULUS`` selects the instruction it stands for.
_MODULUS = 11
_RESIDUE = {1: ">", 2: "<", 3: "+", 4: "-", 5: ".", 6: ",", 7: "[", 8: "]"}


#: Sieve batch size for :func:`_factorint`; not a ceiling.
_SIEVE_CHUNK = 20000

#: Gcd filtering pays once the residue dwarfs the chunk product;
#: committed examples sit below this width.
_BATCH_BITS = 8192

# ``isprime64`` is a proof only below this; above, trial division stays exact.
_EXACT_ISPRIME_LIMIT = 1 << 64


def _parse(digits: str) -> int:
    """Read the program's integer, lifting CPython's digit limit to fit it.

    The 4300-digit cap is a DoS guard, not Factor's (n=6 parity is 5934
    digits); raised for this program and put back.
    """
    with digit_limit_for(len(digits)):
        return int(digits)


def _factorint(number: int) -> dict[int, int]:
    """Factorize ``number`` by widening segmented trial division.

    The number is a product of many smallish primes, so walk primes in
    order and shrink as each divides.  Never stop at a fixed prime: the
    residue is then a large composite that sends the tail to Pollard rho
    for minutes.  Chunks widen until the residue is prime or gone.
    """
    factors: dict[int, int] = {}
    checked = 0
    segments = prime_segments(_SIEVE_CHUNK)
    while number > 1:
        _start, _stop, primes = next(segments)
        divided = False
        # A gcd filters the chunk: ``number % prime`` costs the width of
        # ``number``, but a prime divides ``number`` iff it divides
        # ``gcd(number, chunk product)``, which is small.
        batched = bool(primes) and number.bit_length() >= _BATCH_BITS
        if batched:
            common = math.gcd(number, math.prod(primes))
            active = primes
            # Each gcd is square-free. Strip one copy per present prime
            # together: the 917061-digit block proof decoded in 55.0s versus
            # 99.6s with a whole-program division per prime occurrence.
            while common > 1:
                number //= common
                active = [prime for prime in active if not common % prime]
                for prime in active:
                    factors[prime] = factors.get(prime, 0) + 1
                divided = True
                # Exact quotient batches avoid a gcd while every active prime
                # survives: the native block control fell from 57.1s to 48.1s.
                # Once a prime drops out, gcd(remainder, common) finds survivors.
                quotient, remainder = divmod(number, common)
                while not remainder:
                    number = quotient
                    for prime in active:
                        factors[prime] += 1
                    quotient, remainder = divmod(number, common)
                common = math.gcd(remainder, common)
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
            if batched:
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
            if _isprime64(number):
                factors[number] = factors.get(number, 0) + 1
                return factors
        # Composite above the sieve: widen. ``sympy.factorint`` here would
        # send the leftover to Pollard rho for minutes.
    return factors


def decode(number: int) -> str:
    """Decode a Factor integer into its brainfuck instruction string."""
    factors = sorted(_factorint(number).items())
    return "".join(
        _RESIDUE[p % _MODULUS] * exp for p, exp in factors if p % _MODULUS in _RESIDUE
    )


class _Machine(_BFMachine):
    """Decode Factor, then run it as Brainfuck.

    Inheriting brainfuck's ``_Machine`` keeps Factor's ``_TapeMachine``
    eligibility: the VM view is the decoded machine's.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Decode ``code`` and reset the underlying brainfuck machine."""
        digits = re.sub(r"[^0-9]", "", code)
        number = _parse(digits) if digits else 1
        super().__init__(decode(number), io)


def run(code: str, io: IO) -> None:
    """Run a Factor program, executing the brainfuck it decodes to."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
