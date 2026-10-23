"""Inject's emitted characters: the halving route over every essential input."""

#: Index of the first two-, three- and four-letter label (49 one-letter names
#: past o, t, z, then 52^2, 52^3 more).
_LONGER = (49, 49 + 52**2, 49 + 52**2 + 52**3)


def _extra(labels: int) -> int:
    """Characters the first ``labels`` names spend past one letter each."""
    return sum(max(0, labels - first) for first in _LONGER)


def _chars(n: int, _: str) -> int:
    """C = 3T + 71n + 27 + 5E(n) + 2(E(3n) - E(n)): n input names (five uses
    each) then 2n halving labels (two each), named in order, E the characters
    past one letter a name.

    The tree route below n = 5 peaks at 82, 151, 220, 343 (exhaustive).
    """
    return 3 * (1 << n) + 71 * n + 27 + 5 * _extra(n) + 2 * (_extra(3 * n) - _extra(n))


# n = 17 is the first two-letter label, n = 50 the first two-letter input
# (not buildable: 2^50 rows; the layout is checked with stand-in halves);
# parity reaches C at n = 5..21.
FORMULAS = {"scaling": (_chars, True, (5, 6, 17))}
