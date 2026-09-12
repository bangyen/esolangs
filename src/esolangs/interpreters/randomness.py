r"""Shared randomness hook for the interpreters that need one."""

from __future__ import annotations

import random
import secrets
from typing import Protocol


class Randomness(Protocol):
    r"""A source of small random integers, standing in for ``secrets``."""

    def randbelow(self, upper: int) -> int:
        r"""Return an integer in ``range(upper)``."""


def draw(source: Randomness | None, upper: int) -> int:
    r"""Return a value below ``upper`` from ``source``, or from ``secrets``."""
    if source is None:
        return secrets.randbelow(upper)
    return source.randbelow(upper)


class Seeded:
    r"""A :class:`Randomness` backed by a seeded :class:`random.Random`."""

    def __init__(self, seed: int = 0) -> None:
        r"""Start the generator at ``seed``, so two runs agree."""
        # bandit flags ``random`` as.
        # and beside the point:.
        # here, and only a seedable.
        # remains the default for a.
        self._random = random.Random(seed)  # nosec B311

    def randbelow(self, upper: int) -> int:
        r"""Return a value in ``range(upper)``, rejecting an empty range."""
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        return self._random.randrange(upper)


class FirstDraw:
    r"""A :class:`Randomness` whose *first* answer is chosen, the rest."""

    def __init__(self, first: int, seed: int = 0, rest: int | None = None) -> None:
        r"""Answer the first draw with ``first``; seed or pin what follows."""
        self._first: int | None = first
        self._rest = Seeded(seed)
        self._fixed = rest

    def randbelow(self, upper: int) -> int:
        r"""Return the chosen value once, then the seeded or pinned draws."""
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        if self._first is not None:
            first, self._first = self._first, None
            return first % upper
        if self._fixed is not None:
            return self._fixed % upper
        return self._rest.randbelow(upper)
