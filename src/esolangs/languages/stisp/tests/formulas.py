"""Stisp's emitted characters: equations per level, ids by digit count."""

from tests.proofs._diagram_bounds import digits, profile, worst_diagram


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


def witness(n: int) -> str:
    """The table reaching :func:`_chars` for n = 3..8.

    Every subtable of the capped level, then pairs of the highest ids: the
    extra references land on the widest names.  Past n = 8 the top ids hold
    too few pairs (59 of the 64 nodes at n = 9), so the bound is not reached.
    """
    return worst_diagram(n, lambda node, _: len(str(node)), 1, cover_const=False)


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 6, 7, 8))}
