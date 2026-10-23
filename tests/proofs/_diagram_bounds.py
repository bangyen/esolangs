"""Most nodes a reduced decision diagram holds, level by level, for size bounds."""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations


def profile(n: int) -> tuple[list[int], list[int], list[int], list[int]]:
    """Return per-level ``(branching, equal-halved, constants, top id)`` maxima.

    A level k node sits at one of 2^k positions and is one of the 2^2^(n-k)
    subtables: ``branching`` has distinct halves, ``equal-halved`` is a
    nonconstant with equal halves, at most 2 constants take what is left.
    ``top`` bounds the ids of :func:`subtree_ids`, fresh bottom-up.
    """
    rows = [1 << (n - k) for k in range(n)]
    branching = [min(1 << k, (1 << rows[k]) - (1 << rows[k] // 2)) for k in range(n)]
    equal = [min((1 << k) - branching[k], (1 << rows[k] // 2) - 2) for k in range(n)]
    constants = [min(2, (1 << k) - branching[k] - equal[k]) for k in range(n)]
    nodes = [min(1 << k, (1 << rows[k]) - 2) for k in range(n)]
    top = [1 + sum(nodes[k:]) for k in range(n)]
    return branching, equal, constants, top


def digits(top: int, count: int) -> int:
    """Return the most decimal digits ``count`` distinct ids up to ``top`` hold."""
    return sum(len(str(i)) for i in range(top - count + 1, top + 1))


def capped_level(n: int) -> int:
    """Return the first level whose positions hold every nonconstant subtable."""
    return next(k for k in range(n) if 1 << k >= (1 << (1 << (n - k))) - 2)


def best_cover(
    cost: dict[str, int], pairs: int, need: set[str]
) -> list[tuple[str, str]]:
    """Return the dearest `pairs` distinct ordered pairs of unequal elements.

    Every element of `need` must appear; `cost` prices an element.
    """
    ordered = [(x, y) for x in cost for y in cost if x != y]
    return list(
        max(
            (
                c
                for c in combinations(ordered, pairs)
                if {e for p in c for e in p} >= need
            ),
            key=lambda c: sum(cost[x] + cost[y] for x, y in c),
        )
    )


def worst_diagram(
    n: int, ref: Callable[[int, bool], int], const: int, *, cover_const: bool = True
) -> str:
    """Return the table with the dearest reduced diagram, for n >= 3.

    The capped level k holds every nonconstant subtable, equal-halved ones
    first (so the branching ones take the highest ids).  The level above
    pairs them off, then fills its remaining nodes with the pairs whose
    references cost most: `ref(id, equal)` prices a node, `const` a
    constant, which `cover_const` also writes once.  A level with two
    subtables is covered by an exhaustive choice of pairs instead.
    """
    k = capped_level(n)
    m = 1 << (n - k)
    half = m // 2
    kinds = [format(v, f"0{m}b") for v in range(1, (1 << m) - 1)]
    equal = [t for t in kinds if t[:half] == t[half:]]
    order = equal + [t for t in kinds if t[:half] != t[half:]]
    first = profile(n)[3][k] - len(order) + 1
    cost = {t: ref(first + i, t in equal) for i, t in enumerate(order)}
    zero, one = "0" * m, "1" * m
    cost[zero] = cost[one] = const
    nodes = 1 << (k - 1)
    if len(order) == 2:
        pairs = best_cover(cost, nodes, set(cost) if cover_const else set(order))
    else:
        pairs = [(order[i], order[i + 1]) for i in range(0, len(order), 2)]
        pairs += [(zero, one)] * cover_const
        by_cost = sorted(
            ((x, y) for x in cost for y in cost if x != y),
            key=lambda p: -(cost[p[0]] + cost[p[1]]),
        )
        pairs += [p for p in by_cost if p not in pairs][: nodes - len(pairs)]
    return "".join(a + b for a, b in pairs)


def capped_loss(
    n: int,
    ref: Callable[[int, bool], int],
    const: Callable[[int], int],
    widest: Callable[[int], int],
) -> int:
    """Return what a per-level bound over-counts at the last two levels.

    The bound prices each child once and every other reference at the
    dearest.  With two subtables at level n - 1 and a capped level above
    (n - 1: a few distinct pairs; n - 2: all 14 four-row subtables, whose
    references to the two are fixed, 14 to nodes and 14 to constants), the
    references cannot all be dear.
    """
    k = capped_level(n)
    top = profile(n)[3][n - 1]
    children = [ref(top - 1, False), ref(top, False)]  # noqa: FBT003
    dear, constant = widest(n - 1), const(n - 1)
    if k == n - 1:
        nodes = 1 << (k - 1)
        cost = {"a": children[0], "b": children[1], "0": constant, "1": constant}
        assumed = sum(children) + 2 * constant + (2 * nodes - 4) * dear
        best = best_cover(cost, nodes, set(cost))
        return assumed - sum(cost[x] + cost[y] for x, y in best)
    if k == n - 2:
        return 24 * dear - 6 * sum(children) - 12 * constant
    return 0
