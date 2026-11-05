"""Parenthesys packed lookup: count full groups and the leading remainder."""


def _costs(n: int) -> tuple[int, int]:
    """The column has q full groups after one group of r digits (1 <= r <= 3)."""
    q, remainder = divmod(n - 4, 3)
    r = remainder + 1
    # A 2/3-digit group has %, its argument separators, and a concat op;
    # each appended group adds a multiply and add around a three-digit group.
    return 20 * q + r + 6 * (r > 1), 12 * q + r + 4 * (r > 1)


def _chars(n: int, _: str) -> int:
    return (1 << n) // 8 + 54 + _costs(n)[0]


def _steps(n: int, _: str) -> int:
    return 25 + _costs(n)[1]
