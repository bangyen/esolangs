"""Ascenic's emitted characters: the alternating table, a change point every row."""


def _chars(n: int, _: str) -> int:
    """N = 2T^2 + (16n + 44 + 4m)T + (48n^2 + (235 + 24m)n - 34 + 55m)/2.

    m = n mod 2.
    """
    t, m = 1 << n, n % 2
    return (
        2 * t * t
        + (16 * n + 44 + 4 * m) * t
        + (48 * n * n + (235 + 24 * m) * n - 34 + 55 * m) // 2
    )


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7))}
