r"""Boolean-function generator for 123, under the termination convention.

123's input command reads real stdin, so this is a *parameterized*
generator: input runs become ``1`` for a one and ``2`` for a zero (both
one character, so ``len()`` leaks nothing).  **The answer is the halting
behaviour**: halt is 0, a proven loop is 1, decided by
:func:`esolangs.vm.run_until_halt_or_cycle`.

Printing cannot work: flipping is XOR, so straight-line programs are
affine and reach only the eight affine tables at ``n == 2``.  The
limitations ledger's *monotone* cap (nine of sixteen) belonged to the
displacement-neutral ``12``/``21`` setter, not the language: the ±1
setter here displaces the fills oppositely, so the looping set need not
be upward-closed.

Construction (``n <= 3``; wider tables go unchanged to
:mod:`esolangs.tools.one_two_three.construction`):

1. **Seed** ``"2"*w0 $ "2"*w1 $ ... "33"`` -- the fills are the
   embedding; ``33`` closes at the first offset where no row sits on a
   mark (bounded first-fit, like the wider ``_close``).
2. **Separation** -- a frozen per-arity schedule of even-displacement
   walk/descend segments each closed by ``33``, ending with every row at
   a distinct odd position.  Frozen constants, replayed on the exact
   model, never searched at build time; up to four laws per arity are
   candidates, and the shortest template wins.
3. **Verdict** -- the wider pipeline's planned kill on a junky tape: one
   paint per row whose tested cell disagrees with the table's demand;
   distinct odd positions keep paint offsets collision-free.
4. **Endgame** -- the wider pipeline's, reused.

The suite's exhaustive ``n <= 3`` sweep on the real interpreter is what
pins the schedules.  Retired stored plans (see git history) averaged
5.75/11.44/19.97 characters at one/two/three inputs; the constructed
route averages 20.0/48.1/135.3 (3.5x/4.2x/6.8x) because 102 of the 256
three-input plans were search-found witnesses with no rule.  Every
template loops by a proven state revisit, never unbounded growth, or
the harness would hang instead of reporting a 1; the suite checks it.
"""

from __future__ import annotations

from functools import cache

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, runs
from esolangs.tools.one_two_three.construction import (
    _ONE,
    _RING,
    _WORK_BUDGET,
    _ZERO,
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

#: The input fills.  One character each, so instantiations are equal length;
#: the construction names them, and this re-exports its pair.
ONE, ZERO = _ONE, _ZERO
#: Each input's embed: the generator's own ``ZERO``/``ONE`` command.
PAIR = (ZERO, ONE)

#: One separation law: the walk before each fill, then the alternating test
#: displacements.
#:
#: Both parts are one *shape*, not a set of answers.  The seed walks a fixed
#: distance before each fill; separation
#: alternates ``"1"``-runs and ``"2"``-runs, one displacement each, with
#: no raw repositioning.  Every displacement is closed by its own ``33``:
#: rows whose tested cell is marked re-run the segment and escape, rows
#: whose cell is clear skip.  That split is what separates -- rows differ
#: in their *marks* after a bare fill, not their positions, so a walk
#: alone can never split them.
type _Law = tuple[tuple[int, ...], tuple[int, ...]]

#: The separation laws per small arity, each a named candidate.
#:
#: These are *derived* constants, not a frozen search log.  The first is,
#: over constant seeds and alternating displacement vectors, the law with
#: the least mean template length.  Each law puts the rows at different
#: positions, so the paints and the kill height differ by table, and the
#: rest are a greedy cover: over seeds of 0..6 per fill and up to four
#: displacements of 1..10, each is the law that most shrinks the total over
#: every table given the candidates before it (the first law and the wide
#: chain), at most four laws in all.  Both rules are re-derived in
#: ``tests/tools/test_boolean_one_two_three_laws.py``.  A failing law could
#: only raise, never mis-emit, and the exhaustive sweep re-proves each.
_LAWS: dict[int, tuple[_Law, ...]] = {
    1: (((0,), ()), ((1,), (1, 2, 2)), ((0,), (2,))),
    2: (
        ((2, 2), (3, 2, 4)),
        ((2, 0), (2,)),
        ((2, 0), (2, 4, 4)),
        ((0, 6), (3, 2, 4)),
    ),
    3: (
        ((3, 3, 3), (1, 3, 9, 4)),
        ((6, 0, 1), (4, 8, 6)),
        ((2, 6, 1), (7, 4, 2)),
        ((4, 2, 3), (6, 9, 2)),
    ),
}


@cache
def _separated(n: int, law: int = 0) -> _Builder:
    """Execute arity ``n``'s ``law``-th separation law up to full separation.

    A prototype the per-table build clones, so the law is modelled once per
    process.  Raises if the law no longer separates, which the exhaustive
    sweep turns into a test failure.
    """
    walks, disps = _LAWS[n][law]
    _work[0] = _WORK_BUDGET
    b = _Builder(n)
    for i, walk in enumerate(walks):
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
    # Pure tests, alternating ``1``-runs and ``2``-runs by position.
    for i, d in enumerate(disps):
        b.run(("1" if i % 2 == 0 else "2") * d)
        b.test()
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("the law left shared positions")
    return b


def _verdict_junky(b: _Builder, table: str) -> None:
    """Settle the verdict with the planned kill, on a junky tape.

    Paints aim at *disagreement*: below the kill a 0-row's tested cell must
    end marked (the kill clears it) and a 1-row's clear (the kill's trailing
    mark loops it).  Rows at or above the kill height test their own cell,
    which must be clean; a dirty survivor rejects the schedule (none does at
    these arities).
    """
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


def _construct_small(truth_table: str, n: int, law: int = 0) -> str:
    """Build the small-arity template arity ``n``'s ``law``-th law gives.

    No closing replay: ``test_all_small_tables`` sweeps every ``n <= 3``
    table through the real interpreter, the same contract as
    :func:`~esolangs.tools.one_two_three.construction.construct`.
    """
    _work[0] = _WORK_BUDGET
    try:
        b = _separated(n, law).clone()
        _verdict_junky(b, truth_table)
        _endgame(b)
    except ConstructError as exc:  # pragma: no cover - the sweep proves coverage
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    return b.template()


def _in_name_order(body: str, n: int) -> str:
    """Return ``body`` once it is known to carry exactly ``n`` input runs."""
    try:
        runs(body, TEMPLATE_CHAR, (PAIR,) * n)
    except ValueError as exc:
        raise ValueError(f"template {body!r} does not embed {n} inputs: {exc}") from exc
    return body


def one_two_three(truth_table: str) -> str:
    """Build a 123 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Input runs take ``1`` for a one and
    ``2`` for a zero; the program halts for 0 and loops for 1, decided by
    :func:`esolangs.vm.run_until_halt_or_cycle`.  Raises
    :class:`ValueError` when a stage invariant breaks; the execution gate
    lives in the test suite.
    """
    n = _validate_truth_table(truth_table)
    if n > 3:
        return _in_name_order(construct(truth_table), n)
    candidates = [_construct_small(truth_table, n, law) for law in range(len(_LAWS[n]))]
    return _in_name_order(min(candidates, key=len), n)
