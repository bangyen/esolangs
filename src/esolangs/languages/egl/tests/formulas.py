"""The original EGL row remains a ceiling for the folded layout."""


def _chars(n: int, _: str) -> int:
    """3T + 25n + d + 8, d the digits of T.

    Header, painted row, n guards of 25 + weight.
    """
    return 3 * (1 << n) + 25 * n + len(str(1 << n)) + 8


FORMULAS = {"scaling": (_chars, False, (3, 4, 5))}
