"""Polynomial algebra for the Polynomial text generator.

A Polynomial program is a polynomial whose roots encode instructions: the
k-th instruction uses the k-th prime p, turned into a complex root
``a + p**b*i``. Conjugate pairs are included so the expanded coefficients
stay integers.
"""


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
