"""Independent positive-integer factorization for FRACTRAN evidence."""

from __future__ import annotations

from collections import Counter


def _factor(value: int) -> Counter[int]:
    """``value``'s prime factorisation, by trial division."""
    found: Counter[int] = Counter()
    rest, divisor = value, 2
    while divisor * divisor <= rest:
        while rest % divisor == 0:
            found[divisor] += 1
            rest //= divisor
        divisor += 1
    if rest > 1:
        found[rest] += 1
    return found
