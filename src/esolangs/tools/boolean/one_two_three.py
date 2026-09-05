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

Every arity is *constructed*, by the pipeline in
:mod:`esolangs.tools.boolean.one_two_three_construct`: embed each input as
a tape mark under a merge choreography that re-synchronizes every
instantiation's pointer, separate the rows to distinct odd positions by a
planned decode tree, shield each halting row and loop the rest with one
planned kill, then park the survivors so the program ends below location
0 and halts.  Nothing searches; every emission is validated stage by
stage on an exact model of all rows, and the finished template is
replayed row by row on the real interpreter before it is returned.

Arities up to three used to come from stored plan tables instead (see git
history).  Those plans were one to five literals long -- built on the
pointer-phase counter the ±1 fills drive, decoded by a short tail -- but
102 of the 256 three-input entries were search-found witnesses with no
canonical form: no rule reaches the short shapes, because a plan without
``3`` or a write computes a function of popcount parity alone, and the
pass counts of the ``3`` mechanism depend on the order of the fills
rather than their sum.  Retiring the tables for the constructed route
trades template length for derivability: constructed templates run about
forty times longer (mean 435 characters at three inputs against 12), and
every byte of them is re-derivable from the rules below plus the measured
geometry constants, with nothing frozen.

The small arities the suite sweeps exhaustively (``n <= 3``) use a
*tight* geometry, measured as the sweep minimum and verified over every
table; wider arities keep the construct module's proven-total doubling
geometry.  Two free coordinates shrink the small templates further, both
chosen per table by an exact cost argmin (see :func:`_choose_layout`):
which input's embed walks to which mark -- emission stays in name order;
only the walk target moves -- and each mark's *sense*, because the
embed's scrub can re-flip ``[0, P]`` instead of ``[0, P+1]`` at equal
cost, leaving the mark present exactly when the bit is clear.

Every emitted template loops by a *proven state revisit*, never by
unbounded growth.  That is a hard requirement rather than an aesthetic
one: :func:`~esolangs.vm.run_until_halt_or_cycle` never returns on a
program whose pointer marches right forever, so a template with such a
row would hang the harness instead of reporting a 1.  The suite checks
this directly.
"""

from __future__ import annotations

import itertools
from functools import cache

from esolangs.tools.boolean.helpers import _validate_truth_table
from esolangs.tools.boolean.one_two_three_construct import (
    _WORK_BUDGET,
    ConstructError,
    _Builder,
    _close,
    _endgame,
    _replay,
    _verdict,
    _work,
    construct,
)

__all__ = ["one_two_three"]

#: ``{Xi}`` fills.  One character each, so instantiations are equal length.
ONE, ZERO = "1", "2"

#: A layout: ``assign[i]`` is the mark index input ``i`` embeds at, and
#: ``comp[i]`` is whether its mark sense is complemented.
type _Layout = tuple[tuple[int, ...], tuple[int, ...]]

#: Tight geometry per small arity: ``(marks, escape offsets)``.
#:
#: These are measured constants, not derived ones: each is the minimum-mean
#: survivor of an exhaustive sweep of small geometries over *every* table
#: at its arity (and, at ``n == 3``, every layout of every table), with
#: each candidate build validated stage by stage and replayed row by row.
#: They follow ``marks[i] = (i + 1) * 2**n + 1`` and ``ws[i] = 2**(n - i)``
#: -- linear mark spacing, against the construct module's proven doubling
#: geometry -- but that pattern is an observation about the swept optima,
#: not a totality argument, which is why wider arities keep the proven
#: geometry.  A geometry that failed a table could only raise, never
#: mis-emit: the suite's exhaustive ``n <= 3`` sweep is what pins these.
_TIGHT: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    1: ((3,), (2,)),
    2: ((5, 9), (4, 2)),
    3: ((9, 17, 25), (8, 4, 2)),
}


def _embed(
    b: _Builder,
    marks: tuple[int, ...],
    assign: tuple[int, ...],
    comp: tuple[int, ...],
) -> None:
    """Phase A under a layout: embed input ``i`` at ``marks[assign[i]]``.

    The walk-fill-merge choreography is the construct module's
    (:func:`~esolangs.tools.boolean.one_two_three_construct._phase_a`);
    the two additions are the assignment -- fills are still emitted in
    name order, only each one's walk target moves -- and the complemented
    scrub: re-flipping ``[0, P]`` instead of ``[0, P + 1]`` costs the
    same two synchronized walks but leaves the cell ``P + 1`` mark
    present exactly when the bit is *clear*.
    """
    for i in range(len(marks)):
        m = marks[assign[i]]
        p = m - 1
        b.run("2" * p)
        b.fill(i)
        b.run("1" * (p + 1) + "212112")
        if comp[i]:
            b.run("2" * (m - 1) + "1" * m + "2")
        else:
            b.run("2" * m + "1" * (m + 1) + "2")
        if {r.pos for r in b.live()} != {0}:  # pragma: no cover - invariant
            raise ConstructError("merge failed to re-synchronize")


def _separate_fixed(b: _Builder, marks: tuple[int, ...], ws: tuple[int, ...]) -> None:
    """Separate with a fixed even escape offset per level.

    The construct module's schedule escapes by half the walk distance,
    which halves the minimum inter-group gap per level and is what its
    doubling mark base pays for.  With the tight marks the offsets are
    pinned instead: level ``i``'s escapes move a row ``ws[i]`` to the
    right per re-run -- *per re-run*, because the marks are equally
    spaced and an escape can land on the next level's mark and cascade.
    The exact model tracks every fate either way; distinct positions are
    asserted here and the verdict re-checks distinct *odd* before it
    commits to a kill.
    """
    for mk, w in zip(marks, ws, strict=True):
        for _visit in range(2**b.n + 1):
            pending = [p for p in {r.pos for r in b.live()} if p < mk]
            if not pending:
                break
            d = mk - max(pending)
            # Strictly greater, not >=: over every layout of every table
            # at these arities, no visit ever walks exactly the escape
            # offset (0 of 49416), so a d == w visit -- whose first run
            # would be empty -- can only mean the geometry changed.
            if d <= w:  # pragma: no cover - excluded by the swept geometry
                raise ConstructError(f"mark {mk}: walk {d} not above escape {w}")
            b.run("2" * (d - w))
            b.test()
            b.run("2" * w)
            b.test()
        else:  # pragma: no cover - 2**n groups is the exact worst case
            raise ConstructError(f"mark {mk} did not converge")
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("separation left shared positions")


@cache
def _positions(n: int) -> dict[frozenset[int], int]:
    """Map each mark set to its position after separation.

    Separation never consults the table, and a row's trajectory depends
    only on ``(pos, tape)`` -- that is, on which mark cells it carries --
    so one reference run of the exact model fixes where every mark set
    ends up, for every layout at once: a layout only changes *which row*
    carries which mark set, never where a mark set lands.  This is what
    makes :func:`_choose_layout`'s cost exact rather than estimated.
    """
    marks, ws = _TIGHT[n]
    _work[0] = _WORK_BUDGET
    b = _Builder(n)
    _embed(b, marks, tuple(range(n)), (0,) * n)
    _close(b)
    _separate_fixed(b, marks, ws)
    return {frozenset(marks[i] for i in range(n) if r.bits[i]): r.pos for r in b.live()}


def _layout_positions(n: int, layout: _Layout) -> list[int]:
    """Each row's position after separation under ``layout``, by row index."""
    marks, _ = _TIGHT[n]
    posmap = _positions(n)
    assign, comp = layout
    out = []
    for r in range(2**n):
        bits = tuple((r >> (n - 1 - i)) & 1 for i in range(n))
        out.append(
            posmap[frozenset(marks[assign[i]] for i in range(n) if bits[i] ^ comp[i])]
        )
    return out


def _verdict_cost(n: int, table: str, layout: _Layout) -> int:
    """Exact verdict emission length for ``table`` under ``layout``.

    Mirrors what ``_verdict`` emits -- one shield paint per 0-row below
    the kill, the paints' closing ``33``, and the kill with its ``33`` --
    priced on the exact positions from :func:`_positions`.
    """
    pos = _layout_positions(n, layout)
    ones = [pos[r] for r in range(2**n) if table[r] == "1"]
    if not ones:
        return 0
    a = max(ones) + 2
    cost = 2 * a + 4
    painted = False
    for r in sorted(range(2**n), key=lambda r: pos[r]):
        if pos[r] >= a or table[r] == "1":
            continue
        tested = a if (a - pos[r]) % 4 == 0 else a - 1
        k = tested - pos[r]
        cost += 2 * k + (2 * (k - 1) if k > 1 else 0)
        painted = True
    return cost + (2 if painted else 0)


def _choose_layout(n: int, table: str) -> _Layout:
    """Pick the layout whose verdict is cheapest to emit, ties lexicographic.

    The assignment and the complements are free coordinates -- every
    layout embeds, separates and verdicts correctly (at ``n == 3`` every
    one of the 48 layouts of every table was built and replayed during
    prototyping; a bad one could in any case only raise, never mis-emit)
    -- so the choice is pure size optimization.  The verdict is the only
    stage whose length the layout moves much: it decides where the 1-rows
    sit, hence the kill depth and how many shield paints the 0-rows need.
    Measured against building all 48 layouts and keeping the shortest,
    this argmin gives up under one character of mean template length.
    """
    return min(
        (
            (assign, comp)
            for assign in itertools.permutations(range(n))
            for comp in itertools.product((0, 1), repeat=n)
        ),
        key=lambda lay: (_verdict_cost(n, table, lay), lay),
    )


def _construct_small(truth_table: str, n: int) -> str:
    """Build a small-arity template with the tight geometry.

    The same pipeline and contract as
    :func:`~esolangs.tools.boolean.one_two_three_construct.construct`:
    every stage validates on the exact model, and the finished template
    is replayed row by row on the real interpreter before it is
    returned.  Raises :class:`ValueError` rather than emitting anything
    unproven.
    """
    marks, ws = _TIGHT[n]
    assign, comp = _choose_layout(n, truth_table)
    _work[0] = _WORK_BUDGET
    try:
        b = _Builder(n)
        _embed(b, marks, assign, comp)
        _close(b)
        _separate_fixed(b, marks, ws)
        _verdict(b, truth_table)
        _endgame(b)
        template = b.template()
        _replay(template, n, truth_table)
    except ConstructError as exc:  # pragma: no cover - the contract
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
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
    plans' phase-decode shape, because the construction re-synchronizes
    every instantiation's pointer after each embed and leaves the bit as
    a tape mark instead.  Small arities (``n <= 3``) build here with the
    tight measured geometry; wider tables go to
    :func:`~esolangs.tools.boolean.one_two_three_construct.construct`
    unchanged.  Both routes replay every row on the real interpreter
    before returning, and raise :class:`ValueError` rather than emitting
    an unproven template.
    """
    n = _validate_truth_table(truth_table)
    if n > 3:
        return _in_name_order(construct(truth_table), n)
    return _in_name_order(_construct_small(truth_table, n), n)
