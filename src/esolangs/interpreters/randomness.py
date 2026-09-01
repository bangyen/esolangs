"""Shared randomness hook for the interpreters that need one.

Several languages have a genuinely random instruction -- WII2D's ``?``,
Painfuck's ``y``, Modulous's ``RND``, COD's junction choice, LaserFuck's
beam splitter.  Left as a bare :func:`secrets.randbelow` call, each one
makes its interpreter non-deterministic through the *public* API: the same
program and input can produce different output on two runs.

That matters beyond taste.  ``esolangs.vm.run_until_halt_or_cycle`` proves a
hang from a repeated state, and its argument -- "a deterministic machine
that revisits its complete internal state has looped forever" -- is simply
false for a machine that can choose differently the second time round.  A
stepped VM is expected to be reproducible for the same reason.

Passing a source in fixes both.  ``None`` keeps the language's specified
behaviour (a real random draw); a caller that needs reproducibility hands
in something that decides.  It is not enough to say the generators avoid
the random instructions: a user can still write one.
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
    """Return a value below ``upper`` from ``source``, or from ``secrets``.

    The ``None`` default is the language's own behaviour, so an interpreter
    used without a source behaves exactly as its spec says.
    """
    if source is None:
        return secrets.randbelow(upper)
    return source.randbelow(upper)


class Seeded:
    """A :class:`Randomness` backed by a seeded :class:`random.Random`.

    A stepped VM has to make the same choices twice or nothing about it can
    be asserted, but "always pick the first option" would buy that by making
    the language degenerate: ``?`` would only ever turn one way and ``*``
    only ever split one way, so every stepped run would explore a single
    fixed path and the branches would go unexercised.  A seeded generator is
    reproducible *and* spreads over the options, so a trace is a fair sample
    of what the program does rather than one corner of it.

    ``random`` rather than ``secrets`` on purpose: nothing here is a secret,
    and only ``random`` can be seeded.
    """

    def __init__(self, seed: int = 0) -> None:
        """Start the generator at ``seed``, so two runs agree."""
        # bandit flags ``random`` as unfit for cryptography, which is true
        # and beside the point: reproducibility is the whole requirement
        # here, and only a seedable generator provides it.  ``secrets``
        # remains the default for a real run, above.
        self._random = random.Random(seed)  # nosec B311

    def randbelow(self, upper: int) -> int:
        """Return a value in ``range(upper)``, rejecting an empty range.

        The bound is checked rather than ignored: a stub that never reads
        its argument would answer an impossible request -- choosing among
        no options -- as readily as a real one, and the mistake would
        surface somewhere else.  ``secrets.randbelow`` raises on it too.
        """
        if upper <= 0:
            raise ValueError(f"upper bound must be positive, got {upper}")
        return self._random.randrange(upper)
