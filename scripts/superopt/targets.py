"""The two specs v1 searches: the digits control and the full gadget.

Both ask for the eight input triples to land injectively in trit 0 of
cells 1 and 2 -- the digit gadget's contract.  The constants below are
copied from ``malbolge/generator/digits.py``; a test pins them against
the shipped ``_GADGET`` so they cannot drift.
"""

from __future__ import annotations

from .machine import ZERO, State, run
from .search import Spec

#: The gadget's fixed wipe prefix, as shipped.
PREFIX: tuple[str, ...] = ("/", "0", "/", "1", "K2", "0", "K2", "1", "/", "2")
#: The shipped injective suffix; the control must rediscover exactly it.
SHIPPED_SUFFIX: tuple[str, ...] = ("0", "1", "0", "K1", "0", "2")
#: The shipped 16-op gadget, prefix plus suffix.
SHIPPED_GADGET: tuple[str, ...] = (*PREFIX, *SHIPPED_SUFFIX)
#: The eight input triples, in read order.
INPUTS: tuple[tuple[int, int, int], ...] = tuple(
    (x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)
)


def _spec(starts: tuple[State, ...]) -> Spec:
    return Spec(
        starts=starts,
        inputs=INPUTS,
        expected=(None,) * len(INPUTS),
        distinct=True,
    )


def suffix_spec() -> Spec:
    """Rows start where the wipe prefix leaves them; find a suffix."""
    return _spec(tuple(run(PREFIX, bits) for bits in INPUTS))


def full_spec() -> Spec:
    """Rows start zeroed; find a whole gadget over the full alphabet."""
    return _spec((ZERO,) * len(INPUTS))
