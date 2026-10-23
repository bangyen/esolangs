"""Boolfuck's emitted characters: the unshared tree, shortened by later routes."""


def _chars(n: int, _: str) -> int:
    """C = 35T/2 + 2n^2 + 12n - 23 to n = 7; the tree's own maximum, -11, at n = 8.

    The -11 tree is parity, which the affine stream undercuts (n = 4..7: 95..127
    characters).  The next tables are 12 short, a parity with row 5 flipped.
    From n = 9 the gates are always built (2n^2 + 25n + 26 commands, within the
    tree's bound) and span at most 85T/8 + 2n^2 + 10n + 39 (n = 9: 5,731 against
    9,219).  n = 8 stays on the tree: 25 of 400 random tables refuse the gates.
    """
    if n >= 9:
        return 85 * (1 << n) // 8 + 2 * n * n + 10 * n + 39
    return 35 * (1 << n) // 2 + 2 * n * n + 12 * n - (23 if n <= 7 else 11)


FORMULAS = {"scaling": (_chars, frozenset(range(3, 8)), (3, 4, 5, 6, 7, 8))}
