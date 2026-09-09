"""Polynomial algebra for the Polynomial text generator.

A Polynomial program is a polynomial whose roots encode instructions: the
k-th instruction uses the k-th prime p, turned into a complex root
``a + p**b*i``. Conjugate pairs are included so the expanded coefficients
stay integers.
"""

import contextlib
import sys
from collections.abc import Iterator


@contextlib.contextmanager
def _digit_limit_for(digits: int) -> Iterator[None]:
    """Raise CPython's ``int``/``str`` digit cap to fit ``digits``, then restore.

    ``sys.get_int_max_str_digits()`` defaults to 4300 and is a DoS guard
    against quadratic conversions, not anything Polynomial says.  A
    program's coefficients grow with its instruction count -- a 541
    instruction table needs more than that -- so at some arity the guard
    stops the generator from rendering a program the interpreter could run.
    It is process-global and ours to borrow, so it is raised to what this
    render needs and handed straight back, exactly as Factor's ``_parse``
    and boolean ``factor`` already do for the same reason.
    """
    limit = sys.get_int_max_str_digits()
    if digits <= limit:
        yield
        return
    sys.set_int_max_str_digits(digits + 1)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


def primes(count: int) -> list[int]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if all(candidate % p for p in primes):
            primes.append(candidate)
        candidate += 1
    return primes


def multiply(a: list[int], b: list[int]) -> list[int]:
    result: list[int] = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            result[i + j] += ai * bj
    return result


def format_coeffs(coeffs: list[int]) -> str:
    """Render the coefficient list as the program's ``f(x) = ...`` text.

    The widest coefficient sets how far CPython's digit cap has to be lifted
    for the ``str`` calls below; it is estimated from the bit length
    (``log10(2) ~= 0.30103``) so sizing it does not pay for the very
    conversion it is about to allow.
    """
    widest = max((abs(coeff) for coeff in coeffs), default=0)
    digits = int(widest.bit_length() * 0.30103) + 2
    with _digit_limit_for(digits):
        return _format_coeffs(coeffs)


def _format_coeffs(coeffs: list[int]) -> str:
    terms: list[str] = []
    degree = len(coeffs) - 1
    for i, coeff in enumerate(coeffs):
        d = degree - i
        if coeff == 0:
            continue
        prefix = (
            ""
            if coeff == 1 and d > 0
            else ("-" if coeff == -1 and d > 0 else str(coeff))
        )
        power = f"x^{d}" if d > 1 else ("x" if d == 1 else "")
        terms.append(f"{prefix}{power}")
    return "f(x) = " + " + ".join(terms).replace("+ -", "- ")
