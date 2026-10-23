"""Quassaunt's emitted characters: definitions per level, ids by digit count."""

from __future__ import annotations

from collections.abc import Callable

from tests.proofs._diagram_bounds import (
    capped_level,
    capped_loss,
    digits,
    parent_loss,
    profile,
    worst_diagram,
)

#: Empty-name lengths of a ``_code`` push, a chain/equal node, a branch, a leaf.
_CODE, _EQUAL, _BRANCH, _LEAF = 39, 140, 211, 57


def _bound(n: int) -> int:
    """Bound on the characters, per level k of the reduced diagram.

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


def _prices(
    n: int,
) -> tuple[Callable[[int, bool], int], Callable[[int], int], Callable[[int], int]]:
    """A reference's characters: a node's id, a constant's name, the dearer."""
    top = profile(n)[3]
    return (
        lambda node, _: len(str(node)),
        lambda level: 1 + len(str(level)),
        lambda level: max(len(str(top[level])), 1 + len(str(level))),
    )


def _chars(n: int, _: str) -> int:
    """Worst characters, n = 3..12: the bound less what its last levels cannot reach.

    The bound prices every reference past the first at the dearest name.
    The 14 four-row subtables a level up are all there is, so their
    references are fixed (:func:`capped_loss`): 4 short at n = 5, 12 from 6.
    Above them the wide ids run out of pairs from n = 9 (:func:`parent_loss`).
    """
    prices = _prices(n)
    return _bound(n) - capped_loss(n, *prices) - parent_loss(n, *prices)


def witness(n: int) -> str:
    """The table reaching :func:`_chars`: every subtable, dear references first."""
    ref, const, _ = _prices(n)
    return worst_diagram(n, ref, const(capped_level(n)))


FORMULAS = {"scaling": (_chars, frozenset(range(3, 13)), tuple(range(3, 13)))}
