"""Fargo's emitted characters: the inline Davio expression."""


def _chars(n: int, _: str) -> int:
    """F = 7 + M_{n-1}, M_1 = 23, M_t = 2 M_{t-1} + 8 + bl(t): the worst ANF, inline."""
    if n == 1:
        return 14
    m = 23
    for t in range(2, n):
        m = 2 * m + 8 + t.bit_length()
    return 7 + m


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7))}
