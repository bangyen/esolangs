"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import parity as _parity


def _streetcode_worst(n: int) -> str:
    """Streetcode's largest shipped area and steps: the flat street's longest fill.

    From five inputs, T/2 + 1 ones (the zeros marked, T/2 - 1 of them) is the
    longest fill the flat street writes, and no tree beats it; below, parity.
    """
    if n < 5:
        return _parity(n)
    return "1" + _parity(n)[1:]


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    width = 1 << n
    # A tree's execution worst, one zero at the last entry; the shared
    # worst, parity below five and above it the flat street's longest
    # fill (:func:`_streetcode_worst`).
    return ("1" * (width - 1) + "0", _streetcode_worst(n))
