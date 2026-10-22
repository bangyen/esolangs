"""EGL's emitted characters: a painted row and n weighted guards."""


def _chars(n: int, _: str) -> int:
    """3T + 52n + d + 6, d the digits of T.

    Header, painted row, n guards of 52 + weight.
    """
    return 3 * (1 << n) + 52 * n + len(str(1 << n)) + 6


FORMULAS = {"scaling": (_chars, True, (3, 4, 5))}
