"""Stisp's emitted characters: equations per level, ids by digit count."""

from tests.proofs._diagram_bounds import (
    capped_level,
    digits,
    profile,
    worst_diagram,
)


def _chars(n: int, _: str) -> int:
    """Most characters over all tables, per level k of the reduced diagram.

    A branching node writes two equations (16 + its id twice + its halves'
    ids), an equal-halved one writes one (8 + both ids once).  The ids of a
    level run up to ``top`` (profile), so a node's own id costs at most the
    digits of the highest ids; each child is referenced once at its own
    digits, and the other slots at the child level's widest id.  Constants
    are not written and cost one digit, so a missing one is never cheaper.

    Above the capped level the references are priced by pair: the h widest
    ids make h(h-1) unequal pairs, and ids ascend by first occurrence, so the
    first L // 2 pairs hold only the L narrow ids (a pair has two slots, the
    ids introduced by pair j number at most 2j).  The rest are one wide and
    one narrow slot; an equal pair loses 8 + 2 characters for a slot.
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
            if n >= 9 and k + 1 == capped_level(n) and equal[k] == 0:
                total += _pair_refs(top[k + 1], below, branching[k])
                continue
            total += digits(top[k + 1], below)
            total += max(0, slots - below) * len(str(top[k + 1]))
    return total


def _pair_refs(top: int, nodes: int, pairs: int) -> int:
    """Digits the `pairs` unequal parents write for `nodes` ids ending at `top`."""
    wide = len(str(top))
    high = min(nodes, top - 10 ** (wide - 1) + 1)
    low = nodes - high
    narrow = len(str(top - high)) if low else wide
    forced = min(low // 2, pairs)
    wide_pairs = min(high * (high - 1), pairs - forced)
    mixed = pairs - forced - wide_pairs
    return 2 * narrow * forced + 2 * wide * wide_pairs + (narrow + wide) * mixed


def witness(n: int) -> str:
    """The table reaching :func:`_chars` for n = 3..10.

    Every subtable of the capped level, then pairs of the highest ids: the
    extra references land on the widest names.  Past n = 8 the top ids hold
    too few pairs (59 of the 64 nodes at n = 9); the rest pair a wide id with
    a narrow one, which :func:`_chars` prices.
    """
    return worst_diagram(n, lambda node, _: len(str(node)), 1, cover_const=False)


FORMULAS = {"scaling": (_chars, frozenset(range(3, 11)), tuple(range(3, 11)))}
