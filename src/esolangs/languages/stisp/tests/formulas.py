"""Stisp's emitted characters: equations per level, ids by digit count."""

from __future__ import annotations

from collections.abc import Callable

from tests.proofs._diagram_bounds import (
    capped_level,
    capped_loss,
    digits,
    profile,
    worst_diagram,
)


def _bound(n: int) -> int:
    """Bound on the characters, per level k of the reduced diagram.

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


def _prices(
    n: int,
) -> tuple[Callable[[int, bool], int], Callable[[int], int], Callable[[int], int]]:
    """A reference's digits, a constant's cost, a level's widest id's digits."""
    top = profile(n)[3]
    return (
        lambda node, _equal: len(str(node)),
        lambda _level: 1,
        lambda level: len(str(top[level])),
    )


def _late_equal(n: int) -> int:
    """1 when the capped level sits at n - 3, else 0.

    The bound prices the 14 four-row subtables below the capped level with
    the equal-halved pair at the level's lowest ids, as they are named when
    that level is itself capped (n <= 10): by the pairing, equal ones
    first.  One level down they are named by the capped subtables' halves
    in ascending order — the equal capped subtables come first and name
    every child — so the pair takes ids 8 and 13, not 4 and 5, and the
    level's own-id digits total one less than the bound prices.
    """
    return 1 if capped_level(n) == n - 3 else 0


def _chars(n: int, _: str) -> int:
    """Worst characters, n = 3..19: the bound less what its capped level cannot reach.

    The bound prices the capped level's references to the level below at
    the widest id, but from n = 11 that level holds every eight-row
    subtable, so its references are forced: each of the 14 nodes named 31
    times and 60 slots on the constants (:func:`capped_loss`).  The 14
    nodes' own ids are likewise named in ascending order, one character
    less than priced (:func:`_late_equal`).
    At n = 20 the capped level drops to n - 4 and its parents price three
    digit widths; the bound is not exact there.
    """
    return _bound(n) - capped_loss(n, *_prices(n)) - _late_equal(n)


def witness(n: int) -> str:
    """The table reaching :func:`_chars` for n = 3..19.

    Every subtable of the capped level, then pairs of the highest ids: the
    extra references land on the widest names.  Past n = 8 the top ids hold
    too few pairs (59 of the 64 nodes at n = 9); the rest pair a wide id with
    a narrow one, which :func:`_chars` prices.
    """
    return worst_diagram(n, lambda node, _: len(str(node)), 1, cover_const=False)


FORMULAS = {"scaling": (_chars, frozenset(range(3, 20)), tuple(range(3, 20)))}
