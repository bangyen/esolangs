"""Fish bounds: guarded packed lookup, with integer-address precision fallbacks."""

bl = int.bit_length


def _column(least: int) -> tuple[int, int]:
    """The packed row's column and its literal's length (generator._column)."""
    k = -(-least // 15)
    if k <= 15:
        return 15 * k, 3
    m = bl(least)
    return 1 << m, 1 + 2 * m


def _packed(n: int) -> tuple[int, int]:
    """Column and literal length once the literal itself may move the column."""
    bare = 4 * n + 37
    start, lit = _column(bare + 6)
    if bare + 2 * lit > start:
        start, lit = _column(bare + 2 * lit)
    return start, lit


def _execution(n: int, _: str) -> int:
    """The longer of a symmetric sum and packed prefix; plain at precision stop."""
    if n <= 2 or n > 55:
        return 9 * n + 9
    return max(6 * n + 9, 4 * n + 37 + 2 * _packed(n)[1])


def _workspace(n: int, _: str) -> int:
    """Default upper bound; exact at the registered old arities.

    Packed, ``,`` divides: the quotient is a 64-bit float. The largest
    stack is two raw indices plus6, or bit/float/column/14.
    """
    if n <= 2:
        return bl(9 * n + 8) + n + 13 + bl(n)
    prefix = 4 * n + 37 + 2 * _packed(n)[1]
    stack = max(2 * max(7, n) + 3, bl(_packed(n)[0]) + 71)
    return bl(prefix - 1) + bl(n) + 1 + stack


def _scaling(n: int, _: str) -> int:
    """F cells: plain at n=2, packed through n=55, then integer plain 2T.

    The packed row is its column, 6 powers and T/6 cells, and is never larger
    than the two-row layout from n = 3 while its coordinates are exact.
    """
    if n <= 2:
        return 2 * (9 * n + 9)
    if n > 55:
        return 2 * (1 << n)
    return _packed(n)[0] + 6 - (-(1 << n) // 6)
