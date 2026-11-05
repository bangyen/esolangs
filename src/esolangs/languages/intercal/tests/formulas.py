"""A linear unshared-select ceiling, independent of the naming policy."""

from math import isqrt

_VARIABLE_MAX = 65535


def _digits_sum(limit: int) -> int:
    """Count decimal digits in 1..limit without enumerating them."""
    total, start = 0, 1
    for digits in range(1, len(str(max(limit, 1))) + 1):
        total += digits * max(0, min(limit, 10**digits - 1) - start + 1)
        start *= 10
    return total


def _chars(n: int, _: str) -> int:
    """Bound scalar text by U+3; spilling grows each reference by at most eight.

    Canonical introductions lower ideal scalar cost: graph readers bound
    actual uses below, and global PLEASE/newline rounding differs by at most
    three. A spilled target's indices j*i do not exceed its scalar ordinal,
    so their digit sum adds at most eight characters; each reference already
    has at least two. DIMENSION statements are charged separately.
    """
    t = 1 << n
    expression = 2 * t + sum(
        (1 << level) * (20 + 2 * (1 + len(str(n - level)))) for level in range(n)
    )
    statements = n + 3
    unshared = expression + 7 * n + _digits_sum(n) + 22 + 2 * len(str(n + 1))
    unshared += 4 * statements - 1 + 4 * ((statements + 4) // 5)
    # At most T-1 ordinary nodes, n inputs/result and fewer than n negations.
    spilled = max(0, t + 2 * n - _VARIABLE_MAX)
    if not spilled:
        return unshared + 3
    width = isqrt(spilled - 1) + 1
    arrays = -(-spilled // width)
    dimensions = arrays * (14 + len(str(width))) + _digits_sum(arrays)
    return 5 * (unshared + 3) + dimensions
