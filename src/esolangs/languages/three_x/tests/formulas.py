"""3x key, emitted-size and workspace bounds."""

from fractions import Fraction


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
        (abs(value.numerator).bit_length() or 1)
        + (value < 0)
        + value.denominator.bit_length()
    )


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Measure guards and the widths of their admitted rational keys."""
    guards = program.count("(")
    names = 1 + n + min(guards, (1 << n) // 24)
    return {"G": guards, "K": _key(names), "S": sum(map(_key, range(1, names + 1)))}
