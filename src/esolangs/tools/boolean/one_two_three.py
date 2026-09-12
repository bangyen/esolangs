r"""Boolean-function generator for 123, under the termination."""

from __future__ import annotations

from functools import cache

from esolangs.tools.boolean.helpers import _validate_truth_table
from esolangs.tools.boolean.one_two_three_construct import (
    _RING,
    _WORK_BUDGET,
    ConstructError,
    _Builder,
    _endgame,
    _on_mark,
    _paint,
    _table_val,
    _work,
    construct,
)

__all__ = ["one_two_three"]

# : ``{Xi}`` fills.
ONE, ZERO = "1", "2"

# : One separation law: the.
#: test displacements.
# :.
# : Both parts are one *shape*,.
# : same distance before every.
# : is then a sequence of pure.
# : ``"2"``-runs, one.
# : at all.
# : tested cell is marked.
# : is clear skip, and that.
# : their *marks* after a bare.
# : alone can never split them.
# : synchronized pipeline's.
type _Law = tuple[int, tuple[int, ...]]

# : The separation law per.
# :.
# : These are *derived*.
# : seeds and alternating.
# : least mean template length,.
# : identically at every arity.
# : re-derives all three by.
# : ``n == 3`` the domain is.
# : tables and the winner leads.
# : law replaces what were ten.
# : table could only raise,.
# : ``n <= 3`` sweep re-proves.
_LAWS: dict[int, _Law] = {
    1: (0, ()),
    2: (2, (3, 2, 4)),
    3: (3, (1, 3, 9, 4)),
}


@cache
def _separated(n: int) -> _Builder:
    r"""Execute arity ``n``'s separation law up to full separation."""
    walk, disps = _LAWS[n]
    _work[0] = _WORK_BUDGET
    b = _Builder(n)
    for i in range(n):
        if walk:
            b.run("2" * walk)
        b.fill(i)
    for d in range(4 * 2**n + 9):
        probe = b.clone()
        if d:
            probe.run("2" * d)
        if any(r.pos < 0 for r in probe.live()):
            continue
        if not any(_on_mark(r) for r in probe.live()):
            if d:
                b.run("2" * d)
            b.test()
            break
    else:  # pragma: no cover - the derived seeds all close within range
        raise ConstructError("no clean close for the seed")
    # Pure tests, alternating.
    for i, d in enumerate(disps):
        b.run(("1" if i % 2 == 0 else "2") * d)
        b.test()
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("the law left shared positions")
    return b


def _verdict_junky(b: _Builder, table: str) -> None:
    r"""Settle the verdict with the planned kill, on a junky tape."""
    ones = [r for r in b.live() if _table_val(table, r.bits) == "1"]
    if not ones:
        return
    live = b.live()
    positions = [r.pos for r in live]
    if len(set(positions)) != len(positions) or any(p % 2 == 0 for p in positions):
        raise ConstructError("verdict precondition: positions not distinct odd")
    a = max(r.pos for r in ones) + 2
    if any(r.pos >= a and _on_mark(r) for r in live):  # pragma: no cover
        raise ConstructError("a survivor sits on a marked cell")
    painted = False
    for r in sorted(live, key=lambda row: row.pos):
        if r.pos >= a:
            continue
        tested = a if (a - r.pos) % 4 == 0 else a - 1
        have = bool(r.tape >> (tested + _RING) & 1)
        want = _table_val(table, r.bits) == "0"
        if have != want:
            _paint(b, tested - r.pos)
            painted = True
    if painted:
        b.test()
    b.run("1" * a + "2" + "2" * (a - 1) + "12")
    b.test(kills=frozenset(r.bits for r in ones))


def _construct_small(truth_table: str, n: int) -> str:
    r"""Build the small-arity template arity ``n``'s separation law gives."""
    _work[0] = _WORK_BUDGET
    try:
        b = _separated(n).clone()
        _verdict_junky(b, truth_table)
        _endgame(b)
    except ConstructError as exc:  # pragma: no cover - the sweep proves coverage
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    return b.template()


def _in_name_order(body: str, n: int) -> str:
    r"""Return ``body`` once its slots are known to be in ascending order."""
    positions = [body.index(f"{{X{i}}}") for i in range(n)]
    if positions != sorted(positions):
        raise ValueError(f"template {body!r} emits slots out of name order")
    return body


def one_two_three(truth_table: str) -> str:
    r"""Build a 123 template for the given truth table."""
    n = _validate_truth_table(truth_table)
    if n > 3:
        return _in_name_order(construct(truth_table), n)
    return _in_name_order(_construct_small(truth_table, n), n)
