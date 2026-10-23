"""Bleh's emitted characters: functions per level, ids by digit count."""

from __future__ import annotations

from collections.abc import Callable

from tests.proofs._diagram_bounds import (
    capped_level,
    capped_loss,
    digits,
    pair_loss,
    parent_loss,
    profile,
    worst_diagram,
)


def _bound(n: int) -> int:
    """Bound on the characters, per level k of the reduced diagram.

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


def _prices(
    n: int,
) -> tuple[Callable[[int, bool], int], Callable[[int], int], Callable[[int], int]]:
    """A reference's characters: name and call, a constant's, the dearest."""
    top = profile(n)[3]
    return (
        lambda node, equal: (2 if equal else 11) + 1 + len(str(node)),
        lambda level: 3 + len(str(level)),
        lambda level: max(1 + len(str(top[level])), 1 + len(str(level))) + 11,
    )


def _chars(n: int, _: str) -> int:
    """Worst characters, n = 3..19: the bound less what its last levels cannot reach.

    The bound prices every reference past the first at the dearest call.
    The 14 four-row subtables a level up are all there is, so their
    references are fixed (:func:`capped_loss`): 36 short at n = 5, 108 from 6.
    Above them the wide ids run out of pairs from n = 9, and from n = 10 the
    equal-halved ids cost to name (:func:`parent_loss`).  From n = 11 the 240 + 14
    pairs of those 16 objects are fixed too.  The parents name the 256 level
    n - 3 objects once, the rest of their slots at the dearest id (n = 12: 256
    parents, 512 slots, wide ids pair freely), so nothing more is lost until
    n = 19: its 32,768 parents out-run the 172 wide ids' 29,412 pairs, and
    :func:`pair_loss` prices the 3,356 pairs left to the narrow ids.
    """
    prices = _prices(n)
    return (
        _bound(n)
        - capped_loss(n, *prices)
        - parent_loss(n, *prices)
        - pair_loss(n, *prices)
    )


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
    """The table reaching :func:`_chars`: every subtable, dear references first."""
    ref, const, _ = _prices(n)
    if n == 10:
        return _tenth()
    return worst_diagram(n, ref, const(capped_level(n)))


FORMULAS = {"scaling": (_chars, frozenset(range(3, 20)), tuple(range(3, 20)))}
