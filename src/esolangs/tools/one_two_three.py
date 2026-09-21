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
:mod:`esolangs.tools.one_two_three_construct`):

1. **Seed** ``"2"*w0 $ "2"*w1 $ ... "33"`` -- the fills are the
   embedding; ``33`` closes at the first offset where no row sits on a
   mark (bounded first-fit, like the wider ``_close``).
2. **Separation** -- a frozen per-arity schedule of even-displacement
   walk/descend segments each closed by ``33``, ending with every row at
   a distinct odd position.  Frozen constants, replayed on the exact
   model, never searched at build time.
3. **Verdict** -- the wider pipeline's planned kill on a junky tape: one
   paint per row whose tested cell disagrees with the table's demand;
   distinct odd positions keep paint offsets collision-free.
4. **Endgame** -- the wider pipeline's, reused.

The suite's exhaustive ``n <= 3`` sweep on the real interpreter is what
pins the schedules.  Retired stored plans (see git history) averaged
5.75/11.44/19.97 characters at one/two/three inputs; the constructed
route averages 17.0/49.5/151.5 (3.0x/4.3x/7.6x) because 102 of the 256
three-input plans were search-found witnesses with no rule.  Every
template loops by a proven state revisit, never unbounded growth, or
the harness would hang instead of reporting a 1; the suite checks it.
"""

from __future__ import annotations

from functools import cache

from esolangs.tools.helpers import TEMPLATE_CHAR, _validate_truth_table, runs
from esolangs.tools.one_two_three_construct import (
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

#: One separation law: the constant pre-fill walk, then the alternating
#: test displacements.
#:
#: Both parts are one *shape*, not a set of answers.  The seed walks the
#: same distance before every fill, so it is a single number; separation
#: is then a sequence of pure tests alternating ``"1"``-runs and
#: ``"2"``-runs, one displacement each, with no raw repositioning part
#: at all.  Every displacement is closed by its own ``33``: rows whose
#: tested cell is marked re-run the segment and escape, rows whose cell
#: is clear skip, and that split is what separates -- the rows differ in
#: their *marks* after a bare fill, not in their positions, so a walk
#: alone can never split them (a halving-gap law of the retired
#: synchronized pipeline's shape fails here for exactly that reason).
type _Law = tuple[int, tuple[int, ...]]

#: The separation law per small arity.
#:
#: These are *derived* constants, not a frozen search log: over constant
#: seeds and alternating displacement vectors, each is the law with the
#: least mean template length, which is one selection rule applied
#: identically at every arity.  ``test_the_separation_law_is_the_least_mean``
#: re-derives all three by that sweep rather than trusting them.  At
#: ``n == 3`` the domain is genuinely tight -- 13 laws cover all 256
#: tables and the winner leads the runner-up by 18% -- which is why one
#: law replaces what were ten hand-swept schedules.  A law that failed a
#: table could only raise, never mis-emit, and the suite's exhaustive
#: ``n <= 3`` sweep re-proves coverage and correctness every run.
_LAWS: dict[int, _Law] = {
    1: (0, ()),
    2: (2, (3, 2, 4)),
    3: (3, (1, 3, 9, 4)),
}


@cache
def _separated(n: int) -> _Builder:
    """Execute arity ``n``'s separation law up to full separation.

    A prototype the per-table build clones, so the law is modelled once per
    process.  Raises if the law no longer separates, which the exhaustive
    sweep turns into a test failure.
    """
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


def _construct_small(truth_table: str, n: int) -> str:
    """Build the small-arity template arity ``n``'s separation law gives.

    No closing replay: ``test_all_small_tables`` sweeps every ``n <= 3``
    table through the real interpreter, the same contract as
    :func:`~esolangs.tools.one_two_three_construct.construct`.
    """
    _work[0] = _WORK_BUDGET
    try:
        b = _separated(n).clone()
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
    return _in_name_order(_construct_small(truth_table, n), n)
