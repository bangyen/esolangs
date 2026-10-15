"""The two Polynomial peels: prime-power real roots and instruction quadratics.

Each divides out exactly what an instruction can encode and keeps the
remainder for the general search.
"""

from collections.abc import Callable, Iterable

from esolangs.languages.polynomial.interpreter.primality import (
    _first_primes,
    _require_sympy,
)

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

#: Modulus of the single-word trial division that screens a quadratic
#: candidate before the exact one (2**61 - 1, prime).  An exact divisor
#: divides mod anything, so the screen never rejects a true factor; a
#: spurious candidate dies here in one cheap pass instead of an exact
#: division over multi-thousand-digit coefficients.
_TRIAL_MODULUS = (1 << 61) - 1


def _peel_prime_count(degree: int) -> int:
    """How many primes the peels enumerate for a polynomial of ``degree``."""
    return max(1, degree * _PEEL_PRIME_SLACK)


def _divide_out_quadratics(
    coefficients: list[int], candidates: Iterable[tuple[int, int]]
) -> tuple[list[tuple[int, int]], list[int]]:
    """Divide the candidate quadratics out of the polynomial, exactly.

    A pair joins only because ``(x - a)**2 + q`` divides exactly, re-tried
    for multiplicity; the single-word screen runs first.
    """
    found: list[tuple[int, int]] = []
    remainder = coefficients
    remainder_mod = [k % _TRIAL_MODULUS for k in coefficients]
    ordered = sorted(candidates) if isinstance(candidates, set) else candidates
    for real, square in ordered:
        while len(remainder) >= 3:
            quotient_mod = _divide_quadratic(
                remainder_mod, real, square, _TRIAL_MODULUS
            )
            if quotient_mod is None:
                break
            quotient = _divide_quadratic(remainder, real, square)
            if quotient is None:
                break
            found.append((real, square))
            remainder = quotient
            remainder_mod = quotient_mod
        if len(remainder) <= 1:
            break
    return found, remainder


def _divide_quadratic(
    coefficients: list[int], real: int, square: int, modulus: int | None = None
) -> list[int] | None:
    """Divide by ``(x - real)**2 + square`` exactly, or report that it does not.

    Long division on the integer coefficient list; a ``Poly`` division at
    this degree costs orders of magnitude more.  ``None`` on a remainder.
    With a ``modulus`` it is the screen over that field: ``None`` there
    means the exact division cannot succeed either.
    """
    b1 = -2 * real
    b0 = real * real + square
    if modulus is not None:
        b1 %= modulus
        b0 %= modulus
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
        quotient.append(value if modulus is None else value % modulus)
    # Both remainder positions have to vanish for this to be a factor.
    # ``size >= 3`` from the guard above, so that much always applies.
    linear = coefficients[size - 2] - b1 * quotient[size - 3]
    if size >= 4:
        linear -= b0 * quotient[size - 4]
    constant = coefficients[size - 1] - b0 * quotient[size - 3]
    if modulus is not None:
        linear %= modulus
        constant %= modulus
    if linear or constant:
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
    roots = _roots_in_peel_field(coefficients)
    if not roots:
        return [], coefficients
    prime_count = _peel_prime_count(len(coefficients) - 1)
    return _divide_out_quadratics(
        coefficients, _quadratic_candidates_mod(roots, prime_count)
    )


def _roots_in_peel_field(coefficients: list[int]) -> set[int]:
    """Return the roots of the polynomial in GF(:data:`_PEEL_MODULUS`).

    Empty when the field factorization fails: it is the whole search, and the
    caller's remainder search still sees everything.
    """
    sp = _require_sympy()
    modulus = _PEEL_MODULUS
    try:
        field_poly = sp.Poly(coefficients, sp.Symbol("x"), domain=sp.GF(modulus))
        _content, field_factors = field_poly.factor_list()
    except (sp.PolynomialError, NotImplementedError, ValueError):
        return set()
    roots: set[int] = set()
    for factor, _multiplicity in field_factors:
        if factor.degree() != 1:
            continue
        lead, constant = (int(k) % modulus for k in factor.all_coeffs())
        roots.add((-constant * pow(lead, -1, modulus)) % modulus)
    return roots


def _quadratic_candidates_mod(
    roots: set[int], prime_count: int
) -> set[tuple[int, int]]:
    """Propose ``(a, p**(2*b))`` from roots mod :data:`_PEEL_MODULUS`.

    A pair of roots ``a ± sqrt(-q)`` marks each candidate ``q``.
    """
    sp = _require_sympy()
    modulus = _PEEL_MODULUS
    candidates: set[tuple[int, int]] = set()
    for base in _first_primes(prime_count):
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
    return candidates


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
    found: list[int] = []
    for base in _first_primes(_peel_prime_count(len(coefficients) - 1)):
        if len(coefficients) <= 1:
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
