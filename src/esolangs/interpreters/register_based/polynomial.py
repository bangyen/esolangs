"""Polynomial interpreter implementation.

Polynomial programs are polynomial functions ``f(x) = ...``; real zeroes
are control flow and complex zeroes register operations on a single
integer register, in ascending-prime order.  The wiki's cat notes output
ignores negatives; this clamps to zero (a NUL), and EOF stores -1 as
specified -- as does reading a NUL byte, which keeps the register
distinguishable from an unset one.
Malformed programs raise :class:`ValueError`.  No instruction cap: a
growing register never repeats, and ``esolangs.run``'s ``timeout`` is
the guard.

Root recovery is exact: ``[a, b]`` is ``(x-a)^2 + p**(2*b)`` and ``[v]``
is ``x - p**v``, so the Gaussian integer roots are recovered exactly and
the values read off (a real root ``p**v`` passes 2**53 at ``p**8`` for
``p >= 100``, where ``complex`` would round).  Past
:data:`_NTT_MIN_DEGREE` candidates come from roots modulo two small
prime fields found by NTT (:func:`_roots_mod`); acceptance is exact
division either way.  Whatever the peels leave, and every sparse source,
goes through ``p``-adic lifting and a 2-D lattice
(:func:`_dense_gaussian_roots`) behind the gap lemma
(:func:`_gap_chunks`), so a cold parse is polynomial in the source length
for every source.  :func:`_advance` is pure over ``(register,
cursor)``; the instructions are factored once when the machine is built.
"""

import functools
import math
import re
import sys
from collections.abc import Callable, Iterator, Sequence
from typing import Any, NamedTuple

try:
    import sympy as sp
except ModuleNotFoundError:  # optional ``math`` extra
    sp = None

from esolangs.exceptions import MissingDependencyError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.factor import _isprime64


def _require_sympy() -> Any:
    """Return SymPy or name the extra that installs it."""
    if sp is None:
        raise MissingDependencyError(
            "Polynomial requires optional mathematics support; "
            "install it with `pip install 'esolangs[math]'`"
        )
    return sp


class _Root(NamedTuple):
    """A recovered root, exact: ``real + imag*i`` with integer parts.

    Mirrors ``complex``'s attributes but never rounds.
    """

    real: int
    imag: int


def prime(number: int) -> bool:
    """Check if a number is prime."""
    if number < 2:
        return False
    return all(number % val for val in range(2, math.isqrt(number) + 1))


def _bracket_pairs(string: list[list[int]]) -> dict[int, int]:
    """Pair every control-flow bracket with its partner, in one pass.

    Codes 2 and 6 close, other single-element instructions open.  An
    unmatched bracket is left out: :func:`brackets` raises when it is
    *reached*, and rejecting at load would be a different language.
    """
    pairs: dict[int, int] = {}
    open_at: list[int] = []
    for i, instruction in enumerate(string):
        if len(instruction) != 1:
            continue
        if instruction[0] in (2, 6):
            if open_at:
                beg = open_at.pop()
                pairs[beg] = i
                pairs[i] = beg
        else:
            open_at.append(i)
    return pairs


def brackets(string: list[list[int]], pointer: int) -> int:
    """Find matching bracket for control flow statements.

    Raises :class:`ValueError` on an unmatched bracket.
    """
    length = len(string[pointer]) == 1
    end = string[pointer][0] in [2, 6]
    direct = (1, -1)[length and end]
    count = direct
    while count:
        pointer += direct
        if pointer < 0 or pointer >= len(string):
            raise ValueError("unmatched control-flow bracket")
        if len(string[pointer]) == 1:
            if string[pointer][0] in [2, 6]:
                count -= 1
            else:
                count += 1
    return pointer


def convert(pre: Sequence[complex | _Root]) -> list[list[int]]:
    """Convert polynomial roots to instruction codes using prime encoding.

    Compares plain integers, so an exact :class:`_Root` matches however wide.
    A real root ``p**v`` (``1 <= v <= 8``) is ``[v]``; a root ``a + p**b i``
    (``1 <= b <= 6``) is ``[a, b]``; anything else is dropped.  The codes
    come out grouped by ascending ``p`` and, within one prime, in
    ``(imag, real)`` order -- what scanning every integer up to the largest
    root did, but with each root recognised by its integer ``v``-th roots and
    a proven primality test, so the cost is polynomial in the roots' bits
    rather than in their values.
    """
    keyed: list[tuple[int, int, int, list[int]]] = []
    for root in pre:
        real, imag = round(root.real), round(root.imag)
        if imag:
            match = _prime_power(imag, _PEEL_MAX_IMAGINARY_EXPONENT)
            if match is not None:
                keyed.append((match[0], imag, real, [real, match[1]]))
        else:
            match = _prime_power(real, _PEEL_MAX_EXPONENT)
            if match is not None:
                keyed.append((match[0], 0, real, [match[1]]))
    keyed.sort(key=lambda entry: entry[:3])
    return [entry[3] for entry in keyed]


def _integer_root(number: int, degree: int) -> int:
    """Return ``floor(number ** (1 / degree))`` for ``number >= 0``, exactly.

    Integer Newton from above: ``O(log number)`` steps of ``degree``-th
    powers, so polynomial in the bit length however wide ``number`` is.
    """
    if number < 2 or degree == 1:
        return number
    guess = 1 << -(-number.bit_length() // degree)
    while True:
        better = ((degree - 1) * guess + number // guess ** (degree - 1)) // degree
        if better >= guess:
            return guess
        guess = better


def _prime_power(number: int, max_exponent: int) -> tuple[int, int] | None:
    """Return ``(p, v)`` with ``number == p**v``, ``p`` prime, ``v <= max_exponent``.

    ``None`` otherwise.  The representation is unique, so the first ``v``
    whose integer root is an exact prime is the answer.
    """
    if number < 2:
        return None
    for exponent in range(1, max_exponent + 1):
        base = _integer_root(number, exponent)
        if base < 2:
            break
        if base**exponent == number and _is_proven_prime(base):
            return base, exponent
    return None


#: Below this, Factor's :func:`_isprime64` is a proof: Miller--Rabin with Sinclair's
#: seven bases is deterministic through ``2**64``.  Above it SymPy's
#: ``isprime`` is BPSW -- a compositeness verdict is still a witness, but
#: "prime" is not a proof -- so a probable prime there is certified by
#: :func:`_aks` before it is believed.
_EXACT_ISPRIME_LIMIT = 1 << 64


def _is_proven_prime(number: int) -> bool:
    """Return whether ``number`` is prime, with a proof in every range.

    Deterministic Miller--Rabin below :data:`_EXACT_ISPRIME_LIMIT`; above
    it BPSW screens composites (its "composite" is a witness) and AKS
    certifies the rest, so the answer is never probabilistic.
    """
    if number < _EXACT_ISPRIME_LIMIT:
        return _isprime64(number)
    if not _require_sympy().isprime(number):
        return False
    return _aks(number)


def _totient(number: int) -> int:
    """Euler's phi by trial division; only ever called on AKS's small ``r``."""
    result, rest, factor = number, number, 2
    while factor * factor <= rest:
        if rest % factor == 0:
            while rest % factor == 0:
                rest //= factor
            result -= result // factor
        factor += 1
    if rest > 1:
        result -= result // rest
    return result


def _cyclic_mul(left: list[int], right: list[int], modulus: int) -> list[int]:
    """Multiply in ``Z_modulus[x] / (x**r - 1)`` by Kronecker substitution.

    Both operands are ``r`` reduced residues; one big-integer product
    replaces the ``r**2`` coefficient products.
    """
    size = len(left)
    width = (2 * modulus.bit_length() + size.bit_length() + 8) // 8
    packed_left = int.from_bytes(
        b"".join(k.to_bytes(width, "little") for k in left), "little"
    )
    packed_right = int.from_bytes(
        b"".join(k.to_bytes(width, "little") for k in right), "little"
    )
    raw = (packed_left * packed_right).to_bytes(width * 2 * size, "little")
    out = [0] * size
    for index in range(2 * size - 1):
        value = int.from_bytes(raw[index * width : (index + 1) * width], "little")
        if value:
            out[index % size] += value
    return [k % modulus for k in out]


def _aks(number: int) -> bool:
    """Agrawal--Kayal--Saxena: a deterministic polynomial-time primality proof.

    ``L = number.bit_length() >= log2 number`` stands in for the logarithm,
    which only strengthens both conditions: ``r`` has ``ord_r(number) > L**2``
    and the congruence is checked for ``a <= isqrt(phi(r) * L**2)``, which is
    at least ``sqrt(phi(r)) log2 number`` and still below ``r``.  Slow in
    practice past ``2**64`` -- it is the certificate the proof needs, reached
    only by a BPSW probable prime that large.
    """
    if number < 2:
        return False
    bits = number.bit_length()
    for exponent in range(2, bits + 1):
        if _integer_root(number, exponent) ** exponent == number:
            return False
    square = bits * bits
    modulus = 2
    while True:
        if math.gcd(modulus, number) == 1:
            value, order = number % modulus, 1
            while order <= square and value != 1:
                value = value * number % modulus
                order += 1
            if order > square:
                break
        modulus += 1
    for base in range(2, min(modulus, number - 1) + 1):
        if 1 < math.gcd(base, number) < number:
            return False
    if number <= modulus:
        return True
    limit = math.isqrt(_totient(modulus) * square)
    shift = number % modulus
    for base in range(1, limit + 1):
        # (x + base)**number modulo (x**modulus - 1, number), square-and-multiply.
        power = [0] * modulus
        power[0] = 1
        factor = [0] * modulus
        factor[0] = base % number
        factor[1 % modulus] += 1
        exponent = number
        while exponent:
            if exponent & 1:
                power = _cyclic_mul(power, factor, number)
            exponent >>= 1
            if exponent:
                factor = _cyclic_mul(factor, factor, number)
        expected = [0] * modulus
        expected[shift] = 1
        expected[0] = (expected[0] + base) % number
        if power != expected:
            return False
    return True


def sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list.

    CPython's 4300-digit cap is raised to the widest number here and put
    back, as the generator's ``format_coeffs`` does.
    """
    return _with_digit_limit(_sanitize, code)


def sanitize_terms(code: str) -> dict[int, int]:
    """Parse polynomial string into its sparse ``{degree: coefficient}`` map.

    Exactly the terms :func:`sanitize` densifies (an empty map is its
    ``[0]``), without the ``max_degree + 1`` list: ``x^1000000000000 - 1``
    is two entries here and a terabyte there.
    """
    return _with_digit_limit(_sanitize_terms, code)


def _with_digit_limit[T](parse: Callable[[str], T], code: str) -> T:
    """Run ``parse`` with CPython's digit cap lifted past ``code``'s widest number."""
    longest = max((len(run) for run in re.findall(r"\d+", code)), default=0)
    limit = sys.get_int_max_str_digits()
    if longest <= limit:
        return parse(code)
    sys.set_int_max_str_digits(longest + 1)
    try:
        return parse(code)
    finally:
        sys.set_int_max_str_digits(limit)


def _sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list."""
    terms = _sanitize_terms(code)
    # If no terms found, return [0]
    if not terms:
        return [0]

    # Build coefficient list from highest to lowest degree
    max_degree = max(terms.keys())
    return [terms.get(degree, 0) for degree in range(max_degree, -1, -1)]


def _sanitize_terms(code: str) -> dict[int, int]:
    """Parse polynomial string into ``{degree: coefficient}``, sparse.

    The last term written for a degree wins, and the last bare number is
    the constant even over an explicit ``x^0``.  Zero coefficients are
    kept: ``0x^5`` still sets the dense list's length.
    """
    # Remove "f(x) = " prefix (with or without surrounding spaces)
    match = re.match(r"f\(x\)\s*=\s*(.*)", code)
    if not match:
        return {}

    code = match.group(1).strip()

    # Handle simple cases
    if not code or code == "0":
        return {}

    # Normalize the polynomial string
    code = code.replace(" ", "")

    # Add explicit coefficients and degrees for x terms
    code = re.sub(r"(?<!\d)x(?!\^)", "1x^1", code)  # x -> 1x^1
    code = re.sub(r"x([+-])", r"x^1\1", code)  # x+ -> x^1+

    # Find all terms with their degrees and coefficients
    terms: dict[int, int] = {}

    # Find x^n terms first
    for match in re.finditer(r"(-?\d*)x\^(\d+)", code):
        coeff_str = match.group(1)
        if not coeff_str:
            coeff = 1
        elif coeff_str == "-":
            coeff = -1
        else:
            coeff = int(coeff_str)
        degree = int(match.group(2))
        terms[degree] = coeff

    # Remove x terms from code to find constants
    code_without_x = re.sub(r"-?\d*x\^\d+", "", code)

    # Find constant terms (remaining numbers)
    for match in re.finditer(r"-?\d+", code_without_x):
        coeff = int(match.group(0))
        terms[0] = coeff

    return terms


#: Largest exponent a real instruction's root can carry, from the
#: ``range(1, 9)`` :func:`convert` reads them back with.  The peel below
#: enumerates ``p**v`` up to this, so the two agree by construction.
_PEEL_MAX_EXPONENT = 8

#: How many primes the peel enumerates, as a multiple of the polynomial's
#: degree.  A program assigns its k-th instruction the k-th prime and each
#: instruction costs at least one degree, so the degree bounds the primes
#: that can appear; the slack covers a program written by hand rather than
#: generated.  Candidates are cheap -- one Horner pass each -- and a miss
#: costs only that the root stays in the tail.
_PEEL_PRIME_SLACK = 2

#: Largest exponent a complex instruction's imaginary part can carry, from
#: the ``range(1, 7)`` :func:`convert` reads it back with.
_PEEL_MAX_IMAGINARY_EXPONENT = 6

#: Bound on the ``a`` a quadratic peel will lift out of its residue.  ``a``
#: is a data operand -- a table index, an offset, a codepoint delta -- so it
#: has no encoding bound the way an exponent does, and a residue that lifts
#: to something enormous is a pairing that happened to line up rather than a
#: real factor.  Generously past the ``-3 .. 50`` a dense n=6 table uses;
#: anything past it falls through to ``factor_list`` like any other miss.
_PEEL_MAX_REAL_PART = 1 << 20

#: Prime the quadratic peel finds roots modulo.  It must be ``1 (mod 4)``,
#: and that is not a detail: a factor's ``q`` is ``p**(2*b)``, a perfect
#: square, so ``-q`` is a quadratic residue exactly when ``-1`` is -- which
#: holds iff the modulus is ``1 (mod 4)``.  Under such a prime *every*
#: encodable ``q`` admits the square root the pairing needs; under a ``3
#: (mod 4)`` prime *none* does, and the peel silently finds nothing.
#: Measured: ``nextprime(2**64)`` recovers 51 of 51 sampled ``q`` values,
#: while ``nextprime(2**32)`` and ``nextprime(2**128)`` -- both ``3 (mod
#: 4)`` -- recover none.  Wide enough that distinct small ``a`` stay
#: distinct mod it.
_PEEL_MODULUS = 18446744073709551629

#: Degree above which the candidate search runs through NTT root sets
#: instead of enumerating (real roots) and factoring over
#: :data:`_PEEL_MODULUS` (quadratics).  The NTT path pays a fixed ~0.45s
#: to evaluate the polynomial over both fields, so it loses below the
#: crossover and wins above it superlinearly.  Measured on generated
#: programs, enumerated against screened: degree 74 is 298ms against
#: 457ms, degree 118 is 687ms against 479ms -- the crossover -- and then
#: degree 314 is 5.3s against 0.7s, degree 912 is 78s against 2.6s, and
#: degree 2260 (dense n=10) extrapolates to ~15 minutes against 44s.
_NTT_MIN_DEGREE = 100

#: The two prime fields the large-degree path finds roots in, as ``(m, c,
#: k, g)`` with ``m = c * 2**k + 1`` prime and ``g`` a primitive root.
#: Both are ``1 (mod 4)`` so ``sqrt(-1)`` exists (the same constraint
#: :data:`_PEEL_MODULUS` carries, for the same pairing).  The first field
#: is where quadratic candidates are *paired* -- its size bounds the
#: recoverable real part at ``m // 2`` and sets the spurious-pair rate --
#: and the second only cross-checks, killing all but ~0.2% of the spurious
#: pairs before the trial division.  ``test_ntt_field_constants``
#: re-derives all four numbers of each.
_NTT_FIELDS = ((163841, 5, 15, 3), (65537, 1, 16, 3))

#: Modulus of the single-word trial division that screens a quadratic
#: candidate before the exact one (2**61 - 1, prime).  An exact divisor
#: divides mod anything, so the screen never rejects a true factor; a
#: spurious candidate dies here in one cheap pass instead of an exact
#: division over multi-thousand-digit coefficients.
_TRIAL_MODULUS = (1 << 61) - 1

#: Nonzero bytes in a packed root mask; see :func:`_iter_bits`.
_NONZERO_BYTE = re.compile(rb"[^\x00]")


def _ntt_radix2(vec: list[int], modulus: int, root: int) -> list[int]:
    """Transform ``vec`` in place: ``out[t] = sum_j vec[j] * root**(j*t)``.

    Iterative radix-2; ``len(vec)`` a power of two, ``root`` of that order.
    """
    size = len(vec)
    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            vec[i], vec[j] = vec[j], vec[i]
    span = 2
    while span <= size:
        step = pow(root, size // span, modulus)
        half = span >> 1
        powers = [1] * half
        for i in range(1, half):
            powers[i] = powers[i - 1] * step % modulus
        for start in range(0, size, span):
            for i in range(half):
                low = vec[start + i]
                high = vec[start + i + half] * powers[i] % modulus
                vec[start + i] = (low + high) % modulus
                vec[start + i + half] = (low - high) % modulus
        span <<= 1
    return vec


def _roots_mod(coefficients: list[int], field: tuple[int, int, int, int]) -> set[int]:
    """Return every root of the polynomial in the prime field, exactly.

    Evaluates at all field points: the group has order ``c * 2**k``, so
    ``f(g**t)`` over ``t`` is a DFT computed as ``c`` NTTs and a combining
    pass.  Repeated roots and irreducible factors need no special machinery.
    """
    modulus, cofactor, log_size, generator = field
    group = modulus - 1
    size = 1 << log_size
    degree = len(coefficients) - 1
    folded = [0] * group
    for i, coefficient in enumerate(coefficients):
        j = (degree - i) % group
        folded[j] = (folded[j] + coefficient) % modulus
    sub_root = pow(generator, cofactor, modulus)
    parts = []
    for r in range(cofactor):
        part = folded[r::cofactor]
        part += [0] * (size - len(part))
        parts.append(_ntt_radix2(part, modulus, sub_root))
    if cofactor == 1:
        values = parts[0]
    else:
        values = [0] * group
        mask = size - 1
        for r, part in enumerate(parts):
            if r == 0:
                for t in range(group):
                    values[t] = part[t & mask]
            else:
                twiddle = pow(generator, r, modulus)
                w = 1
                for t in range(group):
                    values[t] = (values[t] + w * part[t & mask]) % modulus
                    w = w * twiddle % modulus
    roots = {pow(generator, t, modulus) for t, v in enumerate(values) if v == 0}
    if coefficients[-1] % modulus == 0:
        roots.add(0)
    return roots


def _iter_bits(mask: int, size: int) -> Iterator[int]:
    """Yield the set bit positions of ``mask``, a ``size``-bit integer.

    ``mask & -mask`` copies the whole integer per bit; a compiled byte scan
    finds nonzero bytes at C speed.
    """
    raw = mask.to_bytes((size + 7) >> 3, "little")
    for match in _NONZERO_BYTE.finditer(raw):
        index = match.start()
        byte = raw[index]
        base = index << 3
        while byte:
            low = byte & -byte
            yield base + low.bit_length() - 1
            byte ^= low


def _quadratic_candidates_ntt(
    prime_count: int,
    root_sets: tuple[set[int], set[int]],
    real_bound: int,
) -> set[tuple[int, int]]:
    """Propose ``(a, p**(2*b))`` pairs from the two fields' root sets.

    Roots pairing at distance ``2*i*p**b`` in the first field propose every
    lift of ``a`` through ``real_bound``; the second field checks each lift.
    Spurious pairs survive at the product of the densities (~0.2% on dense
    n=10) and die in trial division.
    """
    sp = _require_sympy()
    field_data = []
    for (modulus, _, _, generator), roots in zip(_NTT_FIELDS, root_sets, strict=True):
        mask = 0
        for root in roots:
            mask |= 1 << root
        field_data.append(
            (modulus, pow(generator, (modulus - 1) // 4, modulus), roots, mask)
        )
    candidates: set[tuple[int, int]] = set()
    for index, base in enumerate(  # pragma: no branch - ends on the break
        sp.primerange(2, prime_count * prime_count + 3)
    ):
        if index >= prime_count:
            break
        # If the instruction prime equals one field, its conjugate roots
        # coincide there.  Pair in the other field and use the collision as
        # the cross-check; every generated prime is therefore recoverable.
        primary = 1 if base == field_data[0][0] else 0
        m0, i0, _roots0, mask0 = field_data[primary]
        m1, i1, roots1, _mask1 = field_data[1 - primary]
        full = (1 << m0) - 1
        power0 = base % m0
        power1 = base % m1
        square = base * base
        for _exponent in range(_PEEL_MAX_IMAGINARY_EXPONENT):
            delta = 2 * i0 * power0 % m0
            rotated = ((mask0 << delta) | (mask0 >> (m0 - delta))) & full
            hits = mask0 & rotated
            if hits:
                offset0 = i0 * power0 % m0
                offset1 = i1 * power1 % m1
                for r in _iter_bits(hits, m0):
                    residue = (r - offset0) % m0
                    first = residue + ((-real_bound - residue + m0 - 1) // m0) * m0
                    for real in range(first, real_bound + 1, m0):
                        if (real + offset1) % m1 in roots1 and (
                            real - offset1
                        ) % m1 in roots1:
                            candidates.add((real, square))
            power0 = power0 * base % m0
            power1 = power1 * base % m1
            square *= base * base
    return candidates


def _ntt_real_bound(degree: int) -> int:
    """Return the real-part lift window for a polynomial of ``degree``.

    A generated DAG operand is a label plus a span or byte delta: labels total
    at most the instruction count, spans at most 48 times it, and the tree and
    parking cases add at most 51.  Thus ``|a| < 50 * degree`` once the NTT path
    starts above degree 100, where ``degree**2`` covers it.  The quadratic
    envelope also admits generous hand-written slack; exact division remains
    the acceptance test.
    """
    return max(_NTT_FIELDS[0][0] // 2, degree * degree)


def _divide_quadratic_mod(
    coefficients: list[int], real: int, square: int
) -> list[int] | None:
    """:func:`_divide_quadratic` over GF(:data:`_TRIAL_MODULUS`).

    The screen: ``None`` means the exact division cannot succeed either.
    """
    modulus = _TRIAL_MODULUS
    b1 = -2 * real % modulus
    b0 = (real * real + square) % modulus
    size = len(coefficients)
    if size < 3:
        return None
    quotient: list[int] = []
    for index in range(size - 2):
        value = coefficients[index]
        if index >= 1:
            value -= b1 * quotient[index - 1]
        if index >= 2:
            value -= b0 * quotient[index - 2]
        quotient.append(value % modulus)
    linear = (coefficients[size - 2] - b1 * quotient[size - 3]) % modulus
    if size >= 4:
        linear = (linear - b0 * quotient[size - 4]) % modulus
    if linear:
        return None
    constant = (coefficients[size - 1] - b0 * quotient[size - 3]) % modulus
    if constant:
        return None
    return quotient


def _divide_out_quadratics(
    coefficients: list[int], candidates: set[tuple[int, int]]
) -> tuple[list[tuple[int, int]], list[int]]:
    """Divide the candidate quadratics out of the polynomial, exactly.

    A pair joins only because ``(x - a)**2 + q`` divides exactly, re-tried
    for multiplicity; the single-word screen runs first.
    """
    found: list[tuple[int, int]] = []
    remainder = coefficients
    remainder_mod = [k % _TRIAL_MODULUS for k in coefficients]
    for real, square in sorted(candidates):
        while len(remainder) >= 3:
            quotient_mod = _divide_quadratic_mod(remainder_mod, real, square)
            if quotient_mod is None:
                break
            quotient = _divide_quadratic(remainder, real, square)
            if quotient is None:
                break
            found.append((real, square))
            remainder = quotient
            remainder_mod = quotient_mod
    return found, remainder


def _divide_quadratic(
    coefficients: list[int], real: int, square: int
) -> list[int] | None:
    """Divide by ``(x - real)**2 + square`` exactly, or report that it does not.

    Long division on the integer coefficient list; a ``Poly`` division at
    this degree costs orders of magnitude more.  ``None`` on a remainder.
    """
    b1 = -2 * real
    b0 = real * real + square
    size = len(coefficients)
    if size < 3:
        return None
    quotient: list[int] = []
    for index in range(size - 2):
        value = coefficients[index]
        if index >= 1:
            value -= b1 * quotient[index - 1]
        if index >= 2:
            value -= b0 * quotient[index - 2]
        quotient.append(value)
    # Both remainder positions have to vanish for this to be a factor.
    # ``size >= 3`` from the guard above, so that much always applies.
    linear = coefficients[size - 2] - b1 * quotient[size - 3]
    if size >= 4:
        linear -= b0 * quotient[size - 4]
    if linear:
        return None
    constant = coefficients[size - 1] - b0 * quotient[size - 3]
    if constant:
        return None
    return quotient


def _peel_instruction_quadratics(
    coefficients: list[int],
) -> tuple[list[tuple[int, int]], list[int]]:
    """Divide out the complex instructions' quadratics, exactly.

    ``b`` is small but ``a`` is unbounded (dense n=6 would need ~158000
    trial divisions), so ``a`` is solved for: modulo :data:`_PEEL_MODULUS`
    the roots are ``a ± sqrt(-q)``, one root-finding pass proposes ``a``
    per candidate ``q``, confirmed by the partner root.  Accepted only on
    exact division; everything else stays for ``factor_list``.  Dense n=6
    remainder degree-206: 3.16s roots, 0.26s candidates (103 for 103
    quadratics), 0.02s verify, against 35.55s for ``factor_list``.
    """
    if len(coefficients) < 3:
        return [], coefficients

    sp = _require_sympy()
    modulus = _PEEL_MODULUS
    x = sp.Symbol("x")
    try:
        field_poly = sp.Poly(coefficients, x, domain=sp.GF(modulus))
        _content, field_factors = field_poly.factor_list()
    except (sp.PolynomialError, NotImplementedError, ValueError):
        # The field factorization is the whole search; without it there is
        # nothing to peel and the caller's factor_list still sees everything.
        return [], coefficients

    roots: set[int] = set()
    for factor, _multiplicity in field_factors:
        if factor.degree() != 1:
            continue
        lead, constant = (int(k) % modulus for k in factor.all_coeffs())
        roots.add((-constant * pow(lead, -1, modulus)) % modulus)
    if not roots:
        return [], coefficients

    # One instruction is at least two degrees, so the degree bounds the
    # primes a program of this size can have reached.
    prime_count = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    candidates: set[tuple[int, int]] = set()
    # `primerange(2, n*n + 3)` always holds more than `n` primes, so the loop
    # leaves on the `break` and never by running out.
    for index, base in enumerate(  # pragma: no branch
        sp.primerange(2, prime_count * prime_count + 3)
    ):
        if index >= prime_count:
            break
        for exponent in range(1, _PEEL_MAX_IMAGINARY_EXPONENT + 1):
            square = base ** (2 * exponent)
            root_of_negative = sp.sqrt_mod((-square) % modulus, modulus)
            if root_of_negative is None:
                # _PEEL_MODULUS is prime and 1 mod 4, so -1 is a quadratic
                # residue; `square` is a square, so -square is one too.  Only
                # a retuned modulus can land here, and skipping would silently
                # drop candidates.
                raise AssertionError(f"-{square} has no square root mod {modulus}")
            offset = int(root_of_negative)
            for root in roots:
                real_mod = (root - offset) % modulus
                # A genuine factor puts *both* of its roots in the set.
                # ``real_mod + offset`` is ``root`` itself, so only the
                # other one is worth asking about.
                if (real_mod - offset) % modulus not in roots:
                    continue
                real = real_mod if real_mod < modulus // 2 else real_mod - modulus
                if abs(real) > _PEEL_MAX_REAL_PART:
                    continue
                candidates.add((real, square))

    return _divide_out_quadratics(coefficients, candidates)


def _peel_prime_power_roots(
    coefficients: list[int],
    screen: Callable[[int], bool] | None = None,
) -> tuple[list[int], list[int]]:
    """Divide out the real roots that are prime powers, exactly.

    Horner at each candidate proves the factor, synthetic division deflates;
    anything missed stays in the remainder, so incomplete but never wrong.
    Dense n=6 (degree 264): 58 roots in 0.66s, 82.65s factoring -> 35.27s.
    At large degree the ``screen`` (root of the original mod the NTT fields)
    gates the Horner: 14.6K probes -> ~170 on dense n=8, 48.7s -> under 1s.
    """
    sp = _require_sympy()
    found: list[int] = []
    limit = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
    # As above: the range always outlasts `limit`, so this ends on the `break`.
    for prime_index, base in enumerate(  # pragma: no branch
        sp.primerange(2, limit * limit + 3)
    ):
        if prime_index >= limit or len(coefficients) <= 1:
            break
        candidate = base
        for _exponent in range(_PEEL_MAX_EXPONENT):
            if screen is not None and not screen(candidate):
                candidate *= base
                continue
            while len(coefficients) > 1:
                # Horner: the polynomial's value at ``candidate``.
                value = 0
                for coefficient in coefficients:
                    value = value * candidate + coefficient
                if value:
                    break
                found.append(candidate)
                # Synthetic division by an exact root, so it stays exact.
                deflated = [coefficients[0]]
                for coefficient in coefficients[1:-1]:
                    deflated.append(coefficient + deflated[-1] * candidate)
                coefficients = deflated
            candidate *= base
    return found, coefficients


#: A Gaussian integer ``re + im*i`` as an exact pair.
type _Gaussian = tuple[int, int]

#: Sparse polynomial: ``(exponent, coefficient)`` pairs, exponents ascending,
#: coefficients nonzero.
type _Terms = list[tuple[int, int]]


def _gaussian_pow(base: _Gaussian, exponent: int) -> _Gaussian:
    """Return ``base**exponent`` in ``Z[i]`` by square-and-multiply."""
    result_re, result_im = 1, 0
    base_re, base_im = base
    while exponent:
        if exponent & 1:
            result_re, result_im = (
                result_re * base_re - result_im * base_im,
                result_re * base_im + result_im * base_re,
            )
        exponent >>= 1
        if exponent:
            base_re, base_im = (
                base_re * base_re - base_im * base_im,
                2 * base_re * base_im,
            )
    return result_re, result_im


def _sparse_value(chunk: _Terms, point: _Gaussian) -> _Gaussian:
    """Evaluate ``sum c * x**(e - e_0)`` at ``point``: sparse Horner in ``Z[i]``."""
    value_re, value_im = chunk[-1][1], 0
    for index in range(len(chunk) - 2, -1, -1):
        step_re, step_im = _gaussian_pow(point, chunk[index + 1][0] - chunk[index][0])
        value_re, value_im = (
            value_re * step_re - value_im * step_im + chunk[index][1],
            value_re * step_im + value_im * step_re,
        )
    return value_re, value_im


def _gap_chunks(terms: _Terms) -> list[_Terms]:
    """Cut a sparse polynomial at every gap no root of norm >= 4 can bridge.

    With ``S`` the absolute coefficient sum of the chunk so far and ``g``
    the next gap, ``2**g > S`` (equivalently ``g >= S.bit_length()``) forces
    every Gaussian integer root ``alpha`` with ``|alpha| >= 2`` of what is
    left to be a root of both sides: if the upper part were nonzero at
    ``alpha`` it would be a nonzero Gaussian integer, so ``|alpha|**g`` could
    not exceed ``S``.  Inside a chunk every gap is below
    ``log2(t * H) + 1``, which bounds the chunk's degree.
    """
    chunks: list[_Terms] = []
    current: _Terms = [terms[0]]
    mass = abs(terms[0][1])
    for exponent, coefficient in terms[1:]:
        if exponent - current[-1][0] >= mass.bit_length():
            chunks.append(current)
            current, mass = [], 0
        current.append((exponent, coefficient))
        mass += abs(coefficient)
    chunks.append(current)
    return chunks


def _vanishes_at(terms: _Terms, point: _Gaussian) -> bool:
    """Whether the sparse polynomial is zero at ``point`` (``|point| >= 2``).

    Exact: by :func:`_gap_chunks` the polynomial vanishes there iff every
    chunk does, and each chunk has polynomially bounded degree however
    large the exponents.
    """
    return bool(terms) and all(
        _sparse_value(chunk, point) == (0, 0) for chunk in _gap_chunks(terms)
    )


def _sparse_multiplicity(terms: _Terms, point: _Gaussian) -> int:
    """Return the multiplicity of the root ``point`` (``|point| >= 2``).

    For ``alpha != 0`` the multiplicity is the least ``j`` with
    ``(x d/dx)**j f (alpha) != 0``: ``(x d/dx)**j`` is ``x**j d**j/dx**j``
    plus lower derivatives, a unitriangular change.  The operator keeps the
    support and multiplies each coefficient by its exponent, so every
    iterate is sparse too; Hajos' lemma stops the loop within ``t - 1``.
    """
    multiplicity = 0
    while _vanishes_at(terms, point):
        multiplicity += 1
        terms = [(e, c * e) for e, c in terms if e]
    return multiplicity


def _mod_rem(dividend: list[int], divisor: list[int], prime: int) -> list[int]:
    """Remainder of ``dividend / divisor`` over GF(``prime``), descending lists."""
    rest = [k % prime for k in dividend]
    inverse = pow(divisor[0], -1, prime)
    size = len(divisor)
    while len(rest) >= size:
        factor = rest[0] * inverse % prime
        if factor:
            for index in range(1, size):
                rest[index] = (rest[index] - factor * divisor[index]) % prime
        rest.pop(0)
    while rest and not rest[0]:
        rest.pop(0)
    return rest


def _squarefree_mod(coefficients: list[int], prime: int) -> bool:
    """Whether reduction mod ``prime`` keeps the degree and stays squarefree."""
    reduced = [k % prime for k in coefficients]
    if not reduced[0]:
        return False
    degree = len(reduced) - 1
    left = reduced
    right = [k * (degree - i) % prime for i, k in enumerate(reduced[:-1])]
    while right and not right[0]:
        right.pop(0)
    if not right:
        # The derivative vanishes mod p: a p-th power, never squarefree.
        return degree == 0
    while right:
        left, right = right, _mod_rem(left, right, prime)
    return len(left) == 1


def _value_mod(coefficients: list[int], point: int, modulus: int) -> int:
    """Horner mod ``modulus``."""
    value = 0
    for coefficient in coefficients:
        value = (value * point + coefficient) % modulus
    return value


def _hensel_lift(
    coefficients: list[int], roots: list[int], prime: int, target: int
) -> list[int]:
    """Lift simple roots mod ``prime`` to roots mod ``target`` (a power of it).

    Newton's iteration doubles the precision each step because the
    derivative is a unit at a simple root.  The coefficients are reduced
    once per precision, not once per root.
    """
    degree = len(coefficients) - 1
    derivative = [k * (degree - i) for i, k in enumerate(coefficients[:-1])]
    modulus = prime
    while modulus < target:
        modulus = min(modulus * modulus, target)
        reduced = [k % modulus for k in coefficients]
        slope_poly = [k % modulus for k in derivative]
        roots = [
            (
                root
                - _value_mod(reduced, root, modulus)
                * pow(_value_mod(slope_poly, root, modulus), -1, modulus)
            )
            % modulus
            for root in roots
        ]
    return roots


def _round_div(numerator: int, denominator: int) -> int:
    """Nearest integer to ``numerator / denominator`` (``denominator > 0``)."""
    return (2 * numerator + denominator) // (2 * denominator)


def _dot(left: tuple[int, int], right: tuple[int, int]) -> int:
    """Euclidean inner product in ``Z**2``."""
    return left[0] * right[0] + left[1] * right[1]


def _gauss_reduce(
    first: tuple[int, int], second: tuple[int, int]
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Lagrange--Gauss reduction: ``|b1| <= |b2|`` and ``|<b1, b2>| <= |b1|**2/2``."""
    if _dot(first, first) > _dot(second, second):
        first, second = second, first
    while True:
        mu = _round_div(_dot(first, second), _dot(first, first))
        second = (second[0] - mu * first[0], second[1] - mu * first[1])
        if _dot(second, second) >= _dot(first, first):
            return first, second
        first, second = second, first


def _nearest_plane(
    basis: tuple[tuple[int, int], tuple[int, int]], target: tuple[int, int]
) -> tuple[int, int]:
    """Return ``target`` minus Babai's nearest-plane lattice vector, exactly.

    On a Lagrange--Gauss-reduced basis of a lattice whose minimum exceeds
    ``sqrt(16/3) B``, a coset vector of norm at most ``B`` is the one
    returned: both roundings are forced (see the proof in
    ``docs/proofs/polynomial.md``).
    """
    first, second = basis
    gram11, gram12 = _dot(first, first), _dot(first, second)
    determinant = gram11 * _dot(second, second) - gram12 * gram12
    along_second = _round_div(
        _dot(target, second) * gram11 - gram12 * _dot(target, first), determinant
    )
    rest = (target[0] - along_second * second[0], target[1] - along_second * second[1])
    along_first = _round_div(_dot(rest, first), gram11)
    return rest[0] - along_first * first[0], rest[1] - along_first * first[1]


def _root_prime(coefficients: list[int]) -> int:
    """Return the least prime ``p = 1 (mod 4)`` keeping ``coefficients`` squarefree.

    ``p`` must not divide the leading coefficient or the discriminant, and
    only ``O(d (d + log H))`` primes do, so ``p`` is polynomial in the input.
    ``1 (mod 4)`` gives ``sqrt(-1)`` in the ``p``-adic integers.
    """
    candidate = 5
    while not (prime(candidate) and _squarefree_mod(coefficients, candidate)):
        candidate += 4
    return candidate


def _dense_gaussian_roots(coefficients: list[int]) -> set[_Gaussian]:
    """Return every nonzero Gaussian integer root of a dense integer polynomial.

    Deterministic and polynomial time, no factorization over ``Z``: take the
    squarefree part; pick the least prime ``p = 1 (mod 4)`` that keeps it
    squarefree of full degree; find its roots mod ``p`` by exhausting GF(p)
    (``p`` is polynomially bounded); Hensel-lift each to ``P = p**k > 16
    B**2`` with ``B`` Cauchy's root bound; a root ``a + c i`` maps to
    ``a + c*iota`` for a fixed ``iota = sqrt(-1) mod P``, so ``(a, c)`` is the
    short vector of a coset of ``{(u, v): u + v*iota = 0 (mod P)}`` --
    determinant ``P``, minimum at least ``sqrt(P)`` -- and nearest-plane
    rounding on a reduced basis returns it.  Every candidate is checked by
    exact evaluation, so the set is exactly the roots.
    """
    sp = _require_sympy()
    start = 0
    while start < len(coefficients) and not coefficients[start]:
        start += 1
    stop = len(coefficients)
    while stop > start and not coefficients[stop - 1]:
        stop -= 1
    poly = coefficients[start:stop]
    if len(poly) < 2:
        return set()
    squarefree = [int(k) for k in sp.Poly(poly, sp.Symbol("x")).sqf_part().all_coeffs()]
    if len(squarefree) < 2:
        return set()
    lead = abs(poly[0])
    bound = 1 + -(-max(abs(k) for k in poly[1:]) // lead)
    base = _root_prime(squarefree)
    residues = [r for r in range(base) if not _value_mod(squarefree, r, base)]
    if not residues:
        return set()
    modulus = base
    while modulus <= 16 * bound * bound:
        modulus *= base
    iota = next(r for r in range(2, base) if (r * r + 1) % base == 0)
    (iota,) = _hensel_lift([1, 0, 1], [iota], base, modulus)
    basis = _gauss_reduce((modulus, 0), ((-iota) % modulus, 1))
    terms = [(len(poly) - 1 - i, k) for i, k in enumerate(poly) if k][::-1]
    found: set[_Gaussian] = set()
    for lifted in _hensel_lift(squarefree, residues, base, modulus):
        candidate = _nearest_plane(basis, (lifted, 0))
        if candidate != (0, 0) and _sparse_value(terms, candidate) == (0, 0):
            found.add(candidate)
    return found


def _sparse_roots(terms: dict[int, int]) -> list[_Root]:
    """Return the Gaussian integer roots of norm >= 4 of a sparse polynomial.

    With multiplicity, in the shape :func:`_factor_roots` reports them (a
    real root repeated, a pair ``(a, c), (a, -c)`` repeated), and in time
    polynomial in the source length however large the exponents: cut at
    the unbridgeable gaps (:func:`_gap_chunks`), find the roots of one chunk
    (:func:`_dense_gaussian_roots`) -- every root of the whole is one of
    them -- and keep those at which every chunk of every needed
    ``(x d/dx)**j f`` vanishes (:func:`_sparse_multiplicity`).  Every
    instruction root has norm at least 4, so nothing :func:`convert` reads
    is lost; the unit-sized roots, whose powers do not shrink the gap
    argument, are left out.  An identically zero map has no roots here; the
    caller owns that case.
    """
    items = sorted((e, c) for e, c in terms.items() if c)
    if len(items) < 2:
        return []
    chunks = _gap_chunks(items)
    if any(len(chunk) < 2 for chunk in chunks):
        # A lone monomial chunk is nonzero at every alpha != 0.
        return []
    seed = min(chunks, key=lambda chunk: chunk[-1][0] - chunk[0][0])
    low = seed[0][0]
    dense = [0] * (seed[-1][0] - low + 1)
    for exponent, coefficient in seed:
        dense[len(dense) - 1 - (exponent - low)] = coefficient
    roots: list[_Root] = []
    for real, imag in sorted(
        _dense_gaussian_roots(dense), key=lambda r: (abs(r[1]), r)
    ):
        if imag < 0 or real * real + imag * imag < 4:
            continue
        multiplicity = _sparse_multiplicity(items, (real, imag))
        if imag:
            roots.extend([_Root(real, imag), _Root(real, -imag)] * multiplicity)
        else:
            roots.extend([_Root(real, 0)] * multiplicity)
    return roots


def _remainder_roots(coefficients: list[int]) -> list[_Root]:
    """Every integer and Gaussian root of what the peels left, with multiplicity.

    Replaces the ``factor_list`` fallback (Zassenhaus, exponential in the
    worst case) by :func:`_dense_gaussian_roots` and exact division, and
    reports what it did: each integer root repeated, each non-real pair
    ``(a, c), (a, -c)`` with ``c > 0`` repeated, integers first.
    """
    start = 0
    while start < len(coefficients) and not coefficients[start]:
        start += 1
    rest = coefficients[start:]
    if len(rest) <= 1:
        return []
    zeros = 0
    while not rest[-1]:
        rest = rest[:-1]
        zeros += 1
    reals: list[_Root] = [_Root(0, 0)] * zeros
    pairs: list[_Root] = []
    for real, imag in sorted(_dense_gaussian_roots(rest)):
        if imag < 0:
            continue
        if imag:
            while (quotient := _divide_quadratic(rest, real, imag * imag)) is not None:
                pairs.extend([_Root(real, imag), _Root(real, -imag)])
                rest = quotient
            continue
        while len(rest) > 1:
            deflated = [rest[0]]
            for coefficient in rest[1:]:
                deflated.append(coefficient + deflated[-1] * real)
            if deflated.pop():
                break
            reals.append(_Root(real, 0))
            rest = deflated
    return reals + pairs


@functools.lru_cache(maxsize=256)
def _factor_roots(coefficients: tuple[int, ...]) -> tuple[_Root, ...]:
    """Recover every integer and Gaussian integer root, with multiplicity.

    Both peels run first (exact divisions, remainders kept), so the general
    search sees only what neither recognised -- on a generated program
    usually nothing.  Past :data:`_NTT_MIN_DEGREE` the candidates are
    screened through the fields' root sets; same acceptance.  What is left
    goes to :func:`_remainder_roots`, deterministic polynomial time; it
    replaced a ``factor_list`` whose Zassenhaus recombination is
    exponential in the worst case.
    """
    _require_sympy()
    if len(coefficients) - 1 > _NTT_MIN_DEGREE:
        from esolangs.polynomial_resources import estimate_cold_parse

        estimate = estimate_cold_parse(list(coefficients))
        root_sets = tuple(_roots_mod(list(coefficients), f) for f in _NTT_FIELDS)

        def in_every_field(candidate: int) -> bool:
            return all(
                candidate % field[0] in roots
                for field, roots in zip(_NTT_FIELDS, root_sets, strict=True)
            )

        peeled, remainder = _peel_prime_power_roots(list(coefficients), in_every_field)
        roots = [_Root(root, 0) for root in peeled]
        if len(remainder) > 1:
            prime_count = max(1, (len(coefficients) - 1) * _PEEL_PRIME_SLACK)
            candidates = _quadratic_candidates_ntt(
                prime_count,
                (root_sets[0], root_sets[1]),
                estimate.real_lift_bound,
            )
            quadratics, remainder = _divide_out_quadratics(remainder, candidates)
        else:
            quadratics = []
    else:
        peeled, remainder = _peel_prime_power_roots(list(coefficients))
        roots = [_Root(root, 0) for root in peeled]
        if len(remainder) > 1:
            quadratics, remainder = _peel_instruction_quadratics(remainder)
        else:
            quadratics = []

    for real, square in quadratics:
        imaginary = math.isqrt(square)
        roots.extend([_Root(real, imaginary), _Root(real, -imaginary)])
    if len(remainder) <= 1:
        return tuple(roots)

    roots.extend(_remainder_roots(remainder))
    return tuple(roots)


def _find_roots(coefficients: list[int]) -> list[_Root]:
    """Find the roots of an exact-integer polynomial."""
    return list(_factor_roots(tuple(coefficients)))


#: A source whose degree is at most this many times its length is parsed
#: densely, through :func:`_find_roots` and its peels; the dense list is then
#: linear in the source.  Anything sparser -- ``x^1000000000000 - 1`` --
#: goes to :func:`_sparse_roots`, whose cost does not see the degree.
_DENSE_DEGREE_PER_CHAR = 2


@functools.lru_cache(maxsize=4)
def _parse_program(code: str) -> tuple[tuple[int, ...], ...]:
    """Recover the instruction list from a program's source, once.

    Keyed on the source: re-parsing a tens-of-megabytes program cost 0.9s
    per row on dense n=8.  Polynomial time in the source length for every
    source (``docs/proofs/polynomial.md``, "Cold parsing of arbitrary
    programs"): a dense source takes the peels, a sparse one never builds
    its coefficient list.
    """
    cleaned_code = re.sub(r"[^\df(x)=+-^]", "", code)
    if cleaned_code[:5] != "f(x)=":
        raise ValueError("Polynomial program must start with 'f(x) = '")
    _require_sympy()
    terms = sanitize_terms(cleaned_code)
    degree = max(terms, default=0)
    if degree <= _DENSE_DEGREE_PER_CHAR * len(cleaned_code):
        dense = [terms.get(power, 0) for power in range(degree, -1, -1)]
        roots = _find_roots(dense)
    elif not any(terms.values()):
        # The dense list would be ``degree + 1`` zeros, and the real peel
        # divides ``x - 2`` out of zero ``degree`` times: ``degree`` copies
        # of code ``[1]``, an output as long as the degree itself.
        return ((1,),) * degree
    else:
        roots = _sparse_roots(terms)
    return tuple(tuple(instr) for instr in convert([k for k in roots if k.imag >= 0]))


#: The arithmetic instructions, in the order their codes select them.
#: Each is a function of the register and the instruction's operand, so
#: none of them reaches the machine the way the old bound lambdas did.
_ARITH: tuple[Callable[[int, int], int], ...] = (
    lambda r, a: r + a,  # +=
    lambda r, a: r - a,  # -=
    lambda r, a: r * a,  # *=
    lambda r, a: r // a,  # /=
    lambda r, a: r % a,  # %=
    lambda r, a: r**a,  # ^
)

#: The branch conditions, keyed by ``(code - 1) % 4`` the way the
#: instruction codes reach them.  The old table held these in the same list
#: as the arithmetic above, with an integer ``0`` wedged into the endif slot
#: to keep the indices lining up; splitting them means neither table has a
#: hole and every entry has one signature.
#:
#: Key 1 -- the endif slot -- is deliberately absent, because nothing
#: reaches it.  ``convert`` emits single-element codes 1..8 only, so the
#: final arm would need ``one == 10`` and cannot get it, and the bracket arm
#: would need a closer whose *partner* is also a 6, which ``brackets``
#: rejects as unmatched before any condition is consulted.  Enumerating
#: every 2- and 3-instruction table over 1..8 from every cursor and all
#: three register signs -- 4992 combinations -- reaches it zero times, and
#: calling the old slot directly does raise, so the sweep's probe fires.
_COND: dict[int, Callable[[int], bool]] = {
    0: lambda reg: reg > 0,
    2: lambda reg: reg < 0,
    3: lambda reg: not reg,
}

#: One instant of a run: ``(reg, ind)`` -- the single integer register and
#: the instruction cursor.  A value, not a record: :func:`_advance` returns a
#: new pair rather than editing one in place.
type _State = tuple[int, int]


def _partner(
    instructions: list[list[int]], ind: int, pairs: dict[int, int] | None
) -> int:
    """Return ``ind``'s matching bracket, from the table where there is one.

    Falls back to the scan, which raises on an unmatched bracket as before.
    """
    if pairs is not None and ind in pairs:
        return pairs[ind]
    return brackets(instructions, ind)


def _advance(
    state: _State,
    instructions: list[list[int]],
    byte: int | None = None,
    pairs: dict[int, int] | None = None,
) -> tuple[_State, str | None]:
    """Return the state after one instruction, and anything it prints.

    Pure.  The cursor always advances by one, including after a taken jump
    lands on the bracket, so the body runs rather than the bracket re-testing.
    """
    reg, ind = state
    instruction = instructions[ind]
    one = instruction[0]
    rest = instruction[1:] if len(instruction) > 1 else []
    output: str | None = None

    if two := ([*rest, 0])[0]:
        if one:
            reg = _ARITH[two - 1](reg, one)
        elif two - 1:
            reg = byte if byte else -1
        else:
            # Negative registers print as NUL: the wiki says output ignores
            # them, and clamping is this interpreter's documented reading.
            output = chr(max(0, reg))
    elif one in [2, 6]:
        # One lookup, not two: the partner was being found twice over to
        # read its code and then to jump to it.
        partner = _partner(instructions, ind, pairs)
        beg = instructions[partner][0]
        if beg > 4 and _COND[(beg - 1) % 4](reg):
            ind = partner
    elif not _COND[(one - 1) % 4](reg):
        ind = _partner(instructions, ind, pairs)

    return (reg, ind + 1), output


class _Machine:
    """Per-run Polynomial state: the instructions, the register, and the cursor.

    ``halted`` once the cursor reaches the end; register and cursor are the
    complete state.
    """

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        """Recover ``code``'s instructions and start with a zero register."""
        self.io = io
        self.instructions = [list(instr) for instr in _parse_program(code)]
        # Bracket partners, paired once instead of scanned for per jump.
        self._pairs = _bracket_pairs(self.instructions)
        self.ind = 0
        self.reg = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the instructions."""
        return self.ind >= len(self.instructions)

    # The VM's language-shaped view: Single register + cursor; ip the cursor, memory
    # the register.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.reg]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.reg, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor.

        The shell: the byte is read before the transition, the character printed after.
        """
        if self.halted:
            return
        instruction = self.instructions[self.ind]
        one = instruction[0]
        two = ([*instruction[1:], 0])[0]

        byte = None
        if two and not one and two - 1:
            # An empty line reads as -1, which is what the trailing NUL in
            # the original's ``input_str() + chr(0)`` produced: ``ord`` of
            # that NUL is 0, and ``0 or -1`` is -1.
            try:
                val = self.io.input_str() + chr(0)
            except EOFError:
                val = chr(0)
            byte = ord(val[0])

        (self.reg, self.ind), output = _advance(
            (self.reg, self.ind), self.instructions, byte, self._pairs
        )
        if output is not None:
            self.io.print_char(output)


def run(code: str, io: IO) -> None:
    """Execute a Polynomial program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
