"""Inject's emitted characters: the halving route over every essential input."""


def _chars(n: int, _: str) -> int:
    """C = 3T + 71n + 27, two more a label past 49: 3n labels, 49 one-letter.

    The tree route below n = 5 peaks at 82, 151, 220, 343 (exhaustive).
    """
    return 3 * (1 << n) + 71 * n + 27 + 2 * max(0, 3 * n - 49)


# n = 17 is the first two-letter label; parity reaches C at n = 5..23.
FORMULAS = {"scaling": (_chars, True, (5, 6, 17))}
