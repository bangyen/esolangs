"""Ascenic's emitted characters: the alternating table with its first pair flipped.

The alternating table itself ignores all but the last input, so it is read and
popped; the worst table keeps every input and loses one change point."""


def _chars(n: int, _: str) -> int:
    """N = 2T^2 + (16n + 44 + 4m)T + (48n^2 + (203 + 24m)n - 98 + 39m)/2.

    m = n mod 2.
    """
    t, m = 1 << n, n % 2
    return (
        2 * t * t
        + (16 * n + 44 + 4 * m) * t
        + (48 * n * n + (203 + 24 * m) * n - 98 + 39 * m) // 2
    )


FORMULAS = {"scaling": (_chars, frozenset({2, 3, 4, 5, 6, 7}), (3, 4, 5, 6, 7))}
