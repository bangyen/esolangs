"""Pointless's emitted characters: every function declared once."""

from tests.proofs._diagram_bounds import digits, profile


def _chars(n: int, _: str) -> int:
    """A bound: the program declaring every function, levels of the reduced diagram.

    Inlining only shrinks it: callees are decided first, so a function's
    callers are still declared and its uses are the static count; pasting
    it in changes the length by uses * size - (declaration + uses * call),
    and the rule does so only when that is at most 0.  A branch
    is 27 + its id + two names, an equal-halved function 11 + id + name; a
    constant is ``c<bit>d<depth>``.  Ids of a level run up to ``top``
    (profile): each child is named once at its own digits, the other slots
    at the widest.
    """
    branching, equal, constants, top = profile(n)
    name = [3 + len(str(k)) for k in range(n + 1)]
    total = 305 + 6 * n + len(str(top[0])) + 2
    total += 2 * (name[n] + 4) + 8 * n + 8  # the two leaves
    for k in range(n):
        nodes = branching[k] + equal[k]
        total += 4 * nodes + digits(top[k], nodes)
        total += 23 * branching[k] + 7 * equal[k]
        total += constants[k] * (name[k] + 11)
        slots = 2 * branching[k] + equal[k] + constants[k]
        if k + 1 == n:
            total += slots * name[n]
            continue
        below = branching[k + 1] + equal[k + 1]
        widest = max(len(str(top[k + 1])), name[k + 1])
        total += digits(top[k + 1], below) + constants[k + 1] * name[k + 1]
        total += max(0, slots - below - constants[k + 1]) * widest
    return total


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7, 8))}
