"""Bleh's emitted characters: functions per level, ids by digit count."""

from tests.proofs._diagram_bounds import digits, profile


def _chars(n: int, _: str) -> int:
    """Most characters over all tables, per level k of the reduced diagram.

    A branching function is ``f<id>:"0"=<ref>:"1"=<ref>;`` (11 + name), an
    equal-halved or constant one ``<name>:={io::next();<ref>};`` (16 + name).
    A reference is the child's name and ``io::next()`` (11), or ``()`` (2)
    for an equal-halved or constant child, or ``io::print"b"`` (12) at the
    leaves.  Ids of a level run up to ``top`` (profile): a function's own id
    costs at most the digits of the highest ids, each child is referenced
    once at its own cost and the other slots at the dearest.  A constant is
    ``z``/``o`` and its level, so a missing one is never cheaper.
    """
    branching, equal, constants, top = profile(n)
    name = [1 + len(str(k)) for k in range(n)]
    total = 17 + 1 + len(str(top[0])) + 11
    for k in range(n):
        nodes = branching[k] + equal[k]
        total += nodes + digits(top[k], nodes) + 11 * branching[k] + 16 * equal[k]
        total += constants[k] * (name[k] + 16)
        slots = 2 * branching[k] + equal[k] + constants[k]
        if k + 1 == n:
            total += 12 * slots
        else:
            below = branching[k + 1] + equal[k + 1]
            widest = max(1 + len(str(top[k + 1])), name[k + 1]) + 11
            total += below + digits(top[k + 1], below)
            total += 11 * branching[k + 1] + 2 * equal[k + 1]
            total += constants[k + 1] * (name[k + 1] + 2)
            total += max(0, slots - below - constants[k + 1]) * widest
    return total


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7, 8))}
