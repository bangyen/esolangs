"""3x key, emitted-size and workspace bounds."""

from fractions import Fraction

bl = int.bit_length


def _key(i: int) -> int:
    """K(i): bits of the ith key's value (numerator, sign, denominator).

    Rank i - 1 is ``_constant(i - 1)``: 3, then 0 wrapped once per binary
    digit after the leading one, ``v/3 - 1`` or ``1 - v/3``.
    """
    if i == 1:
        return 3
    value = Fraction(0)
    for digit in bin(i - 1)[3:]:
        value = value / 3 - 1 if digit == "0" else 1 - value / 3
    return (
        (abs(value.numerator).bit_length() or 1) + (value < 0) + bl(value.denominator)
    )


def _three_x(n: int, p: str) -> int:
    """Read cursor, guard positions and residues, keys and values.

    Every guard met leaves one 3-bit item; N bounds the names: the result,
    n bits and the
    flags (one guard each, a shared block covers 24 rows).
    """
    names = 1 + n + min(str(p).count("("), 2**n // 24)
    return (
        n * bl(len(p))
        + bl(2 * n - 1)
        + 3 * p.count("(")
        + 2 * n
        + 2 * _key(names)
        + 6 * bl(names - 1)
        + 9
        + sum(_key(i) + 3 for i in range(1, names + 1))
    )
