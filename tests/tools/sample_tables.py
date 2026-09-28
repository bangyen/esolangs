"""The seeded five-input sample a gain that grows with the table is judged on.

``docs/CONTRIBUTING.md`` lets such a gain clear the 5% bar on 200 random
five-input tables instead of the 256 three-input ones; this draws the same
tables ``scripts/screens/sharing.py`` screens, so a pinned total and the
screen's figure are over one sample.
"""

import random


def five_input_sample(count: int = 200, seed: int = 0) -> list[str]:
    """Return ``count`` distinct five-input tables from ``random.Random(seed)``."""
    rng = random.Random(seed)
    found: set[str] = set()
    while len(found) < count:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)
