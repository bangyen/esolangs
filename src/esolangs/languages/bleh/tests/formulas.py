"""Exact alias-priced diagram sizes and scoped workspace attainers."""

from __future__ import annotations

from collections.abc import Callable

from tests.proofs._diagram_bounds import (
    capped_level,
    capped_loss,
    pair_loss,
    parent_loss,
    profile,
    worst_diagram,
)


def _width(i: int) -> int:
    """Letters in id ``i``'s name: bijective base 52, id 2 is ``b``."""
    size = 1
    while i > 52 * (52**size - 1) // 51:
        size += 1
    return size


def _widths(top: int, count: int) -> int:
    """Return the most letters ``count`` distinct ids up to ``top`` hold."""
    return sum(_width(i) for i in range(top - count + 1, top + 1))


def _bound(n: int) -> int:
    """Per-level node/reference ceiling at the actual short-call prices.

    Branching definitions cost name+11; equal/constant definitions name+9.
    Branch references add4, equal references2, and leaf prints11. A level's
    first child references cover its IDs; remaining slots use the dearest.
    """
    branching, equal, constants, top = profile(n)
    name = [1 + len(str(k)) for k in range(n)]
    total = 52 + _width(top[0]) + 4
    for k in range(n):
        nodes = branching[k] + equal[k]
        total += _widths(top[k], nodes) + 11 * branching[k] + 9 * equal[k]
        total += constants[k] * (name[k] + 9)
        slots = 2 * branching[k] + equal[k] + constants[k]
        if k + 1 == n:
            total += 11 * slots
        else:
            below = branching[k + 1] + equal[k + 1]
            widest = _width(top[k + 1]) + 4
            total += _widths(top[k + 1], below)
            total += 4 * branching[k + 1] + 2 * equal[k + 1]
            total += constants[k + 1] * (name[k + 1] + 2)
            total += max(0, slots - below - constants[k + 1]) * widest
    return total


def _prices(
    n: int,
) -> tuple[Callable[[int, bool], int], Callable[[int], int], Callable[[int], int]]:
    """A reference's characters: name and call, a constant's, the dearest."""
    top = profile(n)[3]
    return (
        lambda node, equal: (2 if equal else 4) + _width(node),
        lambda level: 3 + len(str(level)),
        lambda level: _width(top[level]) + 4,
    )


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the dearest aliases and the three independent read losses."""
    prices = _prices(n)
    return {
        "B": _bound(n),
        "A": capped_loss(n, *prices),
        "P": parent_loss(n, *prices),
        "R": pair_loss(n, *prices),
    }


def _tenth() -> str:
    """The n = 10 table: 128 parents over 14 four-row subtables and 2 constants.

    Ranks 0-3 are the cheap-id branching ones (mids), 4 and 5 the equal-halved
    (cheap), 6-13 the dear ids.  The first parents name only ranks below 6,
    except that rank 5 may pair with the first dear id; then every pair of
    dear ids, each dear id with each mid both ways, a constant on two dear
    ids, and two more mid pairs fill the 128.
    """
    rows = [format(v, "04b") for v in range(1, 15)]
    equal = ["0101", "1010"]
    branching = [r for r in rows if r not in equal]
    node = [*branching[:4], *equal, *branching[4:]]
    mid, dear = range(4), range(6, 14)
    pairs = [(0, 1), (2, 3), (0, 4), (5, 6)]
    pairs += [(a, b) for a in dear for b in dear if a != b]
    pairs += [p for a in dear for m in mid for p in ((a, m), (m, a))]
    pairs += [(7, "0000"), (8, "1111"), (1, 0), (3, 2)]
    return "".join(
        "".join(x if isinstance(x, str) else node[x] for x in p) for p in pairs
    )


def witness(n: int) -> str:
    """Attain the alias-priced diagram maximum: all subtables, dear refs first."""
    ref, const, _ = _prices(n)
    if n == 10:
        return _tenth()
    return worst_diagram(n, ref, const(capped_level(n)))


def workspace_witness(n: int) -> str:
    """A full forced-thunk path, then a literal print and its argument frame."""
    return "1" * ((1 << n) - 2) + "01"
