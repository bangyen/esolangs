"""Stisp's emitted characters: equations per level, ids by digit count."""

from tests.proofs._diagram_bounds import digits, profile


def _chars(n: int, _: str) -> int:
    """Most characters over all tables, per level k of the reduced diagram.

    A branching node writes two equations (16 + its id twice + its halves'
    ids), an equal-halved one writes one (8 + both ids once).  The ids of a
    level run up to ``top`` (profile), so a node's own id costs at most the
    digits of the highest ids; each child is referenced once at its own
    digits, and the other slots at the child level's widest id.  Constants
    are not written and cost one digit, so a missing one is never cheaper.
    """
    branching, equal, _, top = profile(n)
    total = 10 + len(str(top[0])) + 6 * n
    for k in range(n):
        total += 16 * branching[k] + 8 * equal[k]
        total += 2 * digits(top[k], branching[k])
        total += digits(top[k] - branching[k], equal[k])
        slots = 2 * branching[k] + equal[k]
        if k + 1 == n:
            total += slots
        else:
            below = branching[k + 1] + equal[k + 1]
            total += digits(top[k + 1], below)
            total += max(0, slots - below) * len(str(top[k + 1]))
    return total


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7, 8))}
