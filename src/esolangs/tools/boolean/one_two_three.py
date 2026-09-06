r"""Boolean-function generator for 123, under the termination convention.

123 has no usable input command for a decision tree -- its ``,`` equivalent
(``2`` at location -3) reads real stdin -- so this is a *parameterized*
generator: the template's ``{Xi}`` placeholders become ``1`` for a one and
``2`` for a zero, and the harness instantiates one program per input
combination.  Both fills are one character, so no instantiation leaks its
inputs through ``len()``.

**The answer is the halting behaviour, not printed output.**  Halt means 0
and a proven loop means 1, the convention already used here for ArrowQueue
and Point Break; the verdict comes from
:func:`esolangs.vm.run_until_halt_or_cycle`, so a loop is proved by a state
revisit rather than assumed from a fuel cap.

Why that convention and not printing
------------------------------------

Flipping a bit is XOR, so a straight-line ``1``/``2`` program is affine by
construction: the printing route reaches exactly the eight affine tables at
``n == 2`` (the constants, the two projections, their negations, XOR and
XNOR) and cannot express AND.  Termination escapes that bound because the
verdict accumulates over passes instead of reading one cell.

``docs/walls.md`` recorded the termination route as capped in turn, at the
*monotone* tables, for a verified union of nine of the sixteen.  That
ceiling belongs to the displacement-neutral ``12``/``21`` setter it fixed,
not to the language: under that setter every instantiation stays in
position lockstep, so a set bit can only add a pass and never remove one.
The ±1 setter used here is *not* neutral, the two fills displace the
pointer oppositely, and the looping set need not be upward-closed.

The construction
----------------

Every arity is *constructed*; nothing is searched at build time and no
truth-table-keyed plan is stored.  Wider tables (``n > 3``) go to the
merge-choreography pipeline in
:mod:`esolangs.tools.boolean.one_two_three_construct` unchanged.  The
small arities the suite sweeps exhaustively build here, from a cheaper
seed the wider pipeline cannot afford to assume:

1. **Seed.**  ``"2"*w0 {X0} "2"*w1 {X1} ... "33"`` -- bare fills, no
   merge.  A ``1`` fill flips the cell it stands on and steps left; a
   ``2`` fill just steps right.  After the fills the rows sit at
   popcount-spread positions of one shared parity, carrying
   row-dependent marks -- the fills *are* the embedding, at a cost of a
   few characters instead of the synchronized pipeline's walk, merge and
   scrub per input.  The closing ``33`` lands on the first offset where
   no row sits on a marked cell (a bounded first-fit scan, the same
   species as the wider pipeline's ``_close``).
2. **Separation.**  A short fixed schedule of walk/descend segments,
   each closed by ``33``: rows on a marked cell re-run the segment until
   they escape, and a segment's displacement is kept *even* so the
   cascade count cannot break the shared parity.  Each schedule is a
   frozen constant below -- discovered offline, but table-independent
   and re-executed deterministically on the exact model, never searched
   for at build time -- and ends with every row at a distinct odd
   position.
3. **Verdict.**  The wider pipeline's planned kill, generalized to the
   junky tape the descents leave: instead of shielding exactly the
   0-rows, one paint per row whose tested cell disagrees with the
   table's demand (0-rows must test a pre-mark the kill segment clears;
   1-rows must test clean so the segment's own mark loops them).  The
   collision-freedom argument is unchanged -- distinct all-odd positions
   make every paint offset unique -- and ``test(kills=...)`` still
   validates every fate on the exact model.
4. **Endgame.**  The wider pipeline's, reused as is.

Several schedules are frozen per arity, and a table takes the shortest:
each candidate is built on the exact model (a candidate whose verdict
preconditions fail simply raises and is skipped), the winner is replayed
row by row on the real interpreter, and at least one candidate covers
every table -- the suite's exhaustive ``n <= 3`` sweep is what pins that,
the same status as the schedule constants themselves.

Why constructed templates are still longer than the retired plans
-----------------------------------------------------------------

Arities up to three used to come from stored plan tables (see git
history) with mean template lengths 5.75, 11.44 and 19.97 characters --
but 102 of the 256 three-input entries were search-found witnesses with
no canonical form: no rule reaches the short shapes, because a plan
without ``3`` or a write computes a function of popcount parity alone,
and the pass counts of the ``3`` mechanism depend on the order of the
fills rather than their sum.  The constructed route trades length for
derivability -- mean 26.0, 60.5 and 163.9 characters at one, two and
three inputs (4.5x, 5.3x and 8.2x the retired plans), every byte
re-derivable from the rules plus the frozen schedule constants.

Every emitted template loops by a *proven state revisit*, never by
unbounded growth.  That is a hard requirement rather than an aesthetic
one: :func:`~esolangs.vm.run_until_halt_or_cycle` never returns on a
program whose pointer marches right forever, so a template with such a
row would hang the harness instead of reporting a 1.  The suite checks
this directly.
"""

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
    _replay,
    _table_val,
    _work,
    construct,
)

__all__ = ["one_two_three"]

#: ``{Xi}`` fills.  One character each, so instantiations are equal length.
ONE, ZERO = "1", "2"

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
#: identically at every arity.  ``test_separation_law_is_least_mean``
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

    The result is a prototype the per-table build clones, so the law is
    modelled once per process.  Everything here is deterministic replay
    of the derived constants: the only scan is the seed's
    first-clean-close offset, a bounded first-fit like the wider
    pipeline's ``_close``.  Raises if the law no longer separates --
    which the suite's exhaustive sweep turns into a test failure, so a
    corrupted constant cannot ship a template.
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

    The wider pipeline's ``_verdict`` shields exactly the 0-rows because
    its separation guarantees a clean zone above every row.  Here a
    row's tested cell may hold a leftover mark either way, so the paints
    aim at *disagreement* instead: below the kill, a 0-row's tested cell
    must end marked (the kill segment then clears it and the row skips
    out) and a 1-row's must end clear (the segment's own trailing mark
    then loops it).  Paint offsets stay collision-free for the same
    reason as there -- two rows sharing an offset would sit one cell
    apart, impossible with every position odd and distinct.  Rows at or
    above the kill height walk back and test their own cell, which must
    be clean -- a dirty survivor rejects the candidate schedule (measured
    over every table and schedule at these arities, none ever has one).
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

    One prototype, not a field of candidates: the law covers every table
    at its arity, so there is nothing to choose between.  The template
    is replayed row by row on the real interpreter before it is returned
    -- the same contract as
    :func:`~esolangs.tools.boolean.one_two_three_construct.construct`.
    """
    _work[0] = _WORK_BUDGET
    try:
        b = _separated(n).clone()
        _verdict_junky(b, truth_table)
        _endgame(b)
    except ConstructError as exc:  # pragma: no cover - the sweep proves coverage
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    template = b.template()
    _replay(template, n, truth_table)
    return template


def _in_name_order(body: str, n: int) -> str:
    """Return ``body`` once its slots are known to be in ascending order.

    The repo-wide invariant is that a template emits ``{X0}`` before
    ``{X1}``; asserting it here keeps a mis-built template from shipping.
    """
    positions = [body.index(f"{{X{i}}}") for i in range(n)]
    if positions != sorted(positions):
        raise ValueError(f"template {body!r} emits slots out of name order")
    return body


def one_two_three(truth_table: str) -> str:
    """Build a 123 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The template's ``{Xi}`` placeholders take ``1`` for a one and ``2`` for
    a zero.  The instantiated program's answer is its *halting* behaviour --
    it halts for a 0 and loops for a 1 -- so the harness decides it with
    :func:`esolangs.vm.run_until_halt_or_cycle` rather than reading output.

    Every arity is constructed: the old objection — an inert embed shifts
    the pointer phase the plan decodes — bound only the retired stored
    plans' phase-decode shape.  Small arities (``n <= 3``) build here
    from the bare-fill seed and the derived separation law; wider
    tables go to
    :func:`~esolangs.tools.boolean.one_two_three_construct.construct`
    unchanged.  Both routes replay every row on the real interpreter
    before returning, and raise :class:`ValueError` rather than emitting
    an unproven template.
    """
    n = _validate_truth_table(truth_table)
    if n > 3:
        return _in_name_order(construct(truth_table), n)
    return _in_name_order(_construct_small(truth_table, n), n)
