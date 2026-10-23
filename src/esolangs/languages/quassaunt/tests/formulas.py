"""Quassaunt's emitted characters: definitions per level, ids by digit count."""

from tests.proofs._diagram_bounds import digits, profile

#: Empty-name lengths of a ``_code`` push, a chain/equal node, a branch, a leaf.
_CODE, _EQUAL, _BRANCH, _LEAF = 39, 140, 211, 57


def _chars(n: int, _: str) -> int:
    """Most characters over all tables, per level k of the reduced diagram.

    Each node is a fixed body plus its own name and one code per child (a
    branch has two), and a space; the start word pushes the root.  Ids of a
    level run up to ``top`` (profile): a node's own id costs at most the
    digits of the highest ids, each child level node is referenced once at
    its own digits and the other slots at its widest.  A constant chain is
    ``z``/``o`` and its depth, so its name is 1 + digits(k) and a missing
    one is never cheaper (its body outweighs the reference it saves).
    """
    branching, equal, constants, top = profile(n)
    name = [1 + len(str(k)) for k in range(n + 1)]
    total = _CODE + len(str(top[0])) + 11 + 2 * (_LEAF + name[n] + 1)
    for k in range(n):
        nodes = branching[k] + equal[k]
        total += _BRANCH * branching[k] + _EQUAL * (equal[k] + constants[k])
        total += digits(top[k], nodes) + constants[k] * name[k]
        total += nodes + constants[k]
        slots = 2 * branching[k] + equal[k] + constants[k]
        if k + 1 == n:
            total += slots * name[n]
        else:
            below = branching[k + 1] + equal[k + 1]
            widest = max(len(str(top[k + 1])), name[k + 1])
            total += digits(top[k + 1], below) + constants[k + 1] * name[k + 1]
            total += max(0, slots - below - constants[k + 1]) * widest
    return total


FORMULAS = {"scaling": (_chars, False, (3, 4, 5, 6, 7, 8))}
