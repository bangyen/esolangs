"""Shared randomness hook for the interpreters that need one.

WII2D's ``?``, Painfuck's ``y``, Modulous's ``RND``, COD's junction and
LaserFuck's splitter draw at random; a bare ``secrets`` call makes the
public API non-deterministic and breaks the cycle detector's premise.
``None`` keeps the spec's real draw; a caller needing reproducibility
hands in a source.
"""

from __future__ import annotations

import random
import secrets
from typing import Protocol


class Randomness(Protocol):
    """A source of small random integers, standing in for ``secrets``."""

    def randbelow(self, upper: int) -> int:
        """Return an integer in ``range(upper)``."""


def draw(source: Randomness | None, upper: int) -> int:
    """Return a value below ``upper`` from ``source``, or from ``secrets``."""
    if source is None:
        return secrets.randbelow(upper)
    return source.randbelow(upper)


class Seeded:
    """A :class:`Randomness` backed by a seeded :class:`random.Random`.

    Reproducible *and* spread over the options ("always first" would leave
    every other branch unexercised).  ``random``, since only it can be seeded.
    """

    def __init__(self, seed: int = 0) -> None:
        """Start the generator at ``seed``, so two runs agree."""
        # bandit flags ``random`` as unfit for cryptography, which is true
        # and beside the point: reproducibility is the whole requirement
        # here, and only a seedable generator provides it.  ``secrets``
        # remains the default for a real run, above.
        self._random = random.Random(seed)  # nosec B311

    def randbelow(self, upper: int) -> int:
        """Return a value in ``range(upper)``; an empty range raises."""
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        return self._random.randrange(upper)


class FirstDraw:
    """A :class:`Randomness` whose *first* answer is chosen, the rest seeded.

    A one-off draw can decide a run (LaserFuck's initial heading), so a test
    or example pins it here rather than through a per-language argument.
    Later draws are seeded so branches stay exercised; ``rest`` pins them too.
    """

    def __init__(self, first: int, seed: int = 0, rest: int | None = None) -> None:
        """Answer the first draw with ``first``; seed or pin what follows."""
        self._first: int | None = first
        self._rest = Seeded(seed)
        self._fixed = rest

    def randbelow(self, upper: int) -> int:
        """Return the chosen value once, then the seeded or pinned draws."""
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        if self._first is not None:
            first, self._first = self._first, None
            return first % upper
        if self._fixed is not None:
            return self._fixed % upper
        return self._rest.randbelow(upper)
