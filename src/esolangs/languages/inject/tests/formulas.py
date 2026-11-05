"""Inject's emitted characters: the halving route over every essential input."""

from esolangs.languages.inject.proof_formulas import _regex_chars

#: Index of the first two-, three- and four-letter label (49 one-letter names
#: past o, t, z, then 52^2, 52^3 more).
_LONGER = (49, 49 + 52**2, 49 + 52**2 + 52**3)


def _extra(labels: int) -> int:
    """Characters the first ``labels`` names spend past one letter each."""
    return sum(max(0, labels - first) for first in _LONGER)


def _chars(n: int, _: str) -> int:
    """C = T + 71n + 29 + 2R(n) + 5E(n) + 2(E(3n)-E(n)).

    R sums the n regex widths; E counts extra letters past single-character
    labels. Input and guard label occurrences are unchanged by regex spelling.
    The tree route below n = 5 peaks at 82, 151, 220, 343 (exhaustive).
    """
    return (
        (1 << n)
        + 71 * n
        + 29
        + 2 * _regex_chars(n)
        + 5 * _extra(n)
        + 2 * (_extra(3 * n) - _extra(n))
    )


# n = 17 is the first two-letter label, n = 50 the first two-letter input
# (not buildable: 2^50 rows; the layout is checked with stand-in halves);
# parity reaches C at n = 5..21.
