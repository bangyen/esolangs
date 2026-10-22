"""Boolfuck's emitted characters: the unshared tree, shortened by later routes."""


def _chars(n: int, _: str) -> int:
    """C = 35T/2 + 2n^2 + 12n - 23 to n = 7; the tree's own maximum, -11, after.

    The -11 tree is parity, which the affine stream undercuts (n = 4..7: 95..127
    characters).  The next tables are 12 short, a parity with row 5 flipped.
    From n = 8 the gates take that one (n = 8: 1,968 against 4,681).
    """
    return 35 * (1 << n) // 2 + 2 * n * n + 12 * n - (23 if n <= 7 else 11)


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7))}
