"""Build Minifuck Boolean templates by input substitution.

Each input is embedded once at equal width. The staged and sculpted routes
derive candidates, verify every instantiated row with the joint simulator, and
raise rather than emit an unverified program. The simulator laws are pinned
differentially against the interpreter.
"""

import re
from bisect import bisect_left
from collections.abc import Callable, Iterator
from functools import cache

from esolangs.tools.boolean.helpers import (
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

# The machine the construction.
# are re-exported rather than.
# suite imports them from here.
# reads as part of the.
from esolangs.tools.boolean.minifuck_sim import _clamp, _Joint, _runs, _Sim, _walk_to

__all__ = ["minifuck"]

# What an acceptance callback.
# and returning None means.

# Where the embedded bits start.
# begins past it with a little.
_BASE = 16

# What separates one embedded.
# the prefix-XORs too.
# the ``<`` steps back over a.
# .
# The separator decides the.
# and the first two here were.
# than a detail: between them.
# :func:`_staging_index`.
# complement pairs, inside the.
# figure here read 92, which no.
# frame named, since a bare.
# And 112 of the 120 tables the.
# tape entirely rather than.
# over the same alphabet fixed.
# those 120, and the searches.
# Only the first two are used.
# degenerate path and the.
# staging enumeration, so.
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]

# The separators the scanning.
# search's cost; the plan.
_SCAN_SEPS = _SEPS[:2]

# How far the bits and their.
_SPAN = 6

# The pool spells ASCII '0'.
# are fixed and cell 7 carries.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# How wide the pool is.
# byte and not a tunable: it is.
# .
# **Several numbers in this.
# spelling them as literals hid.
# ``docs/generators/minifuck_gen.
# .
# * the accumulator floor --.
# because the accumulator has.
# * the sculpting rewind guard,.
# is what keeps a round's.
# * :data:`_PROBE_WALK_OUT` and.
# ``_POOL_WIDTH + 1``;.
# * the sculpting accumulator.
# .
# The last pair is essential.
# guard is exactly what makes.
# worst rewind is ``lo -.
# guard can never fire.
# and the identity looks like a.
# .
# The staging path takes the.
# :data:`_PROBE_WALK_OUT`, and.
# are the length of that loop.
# .
# What is *not* this constant.
# width: collapsing it into.
# hold.
# :func:`_mux_start`'s offset.
# the shortest position whose.
# two are coupled, just not.
_POOL_WIDTH = len(_POOL) + 1

# The two reads.
# leaves it at ``(acc-1) + NOT.
# neighbour unconditionally.
# every reachable pool.
# pool -- is what makes a table.
_READS = ("[<", "[x<[<")


# What complements the bit a.
# cell the setter used and.
# own cell -- so the bit.
# where the setter left it.
# .
# The trailing character is not.
# skip flag, and a gadget that.
# template, shifting every.
# feeds the skip instead.
# ``<[`` passes a probe that.
# on it printed 0 of 12 on the.
# state, and a probe that omits.
_FLIP = "<[x"


def _embed(
    n: int,
    settle: int = 0,
    sep: str = _SEP,
    flips: int = 0,
) -> _Joint:
    """Emit the embed: each ``{Xi}`` once, separated by :data:`_SEP`.

    The separator is not arbitrary.  A plain run of ``[x`` leaves the bits'
    prefix-XORs too correlated for the one-sided tests the endgame can make,
    and the XOR family becomes unreachable; ``[x<[x`` steps back over one
    cell so the parities stay distinguishable.  ``settle`` re-crosses the
    region that many times, which advances the affine state and offers the
    searches a different set of columns.

    ``flips`` is a mask of the inputs whose bit is complemented as it lands,
    and it defaults to what this always did.  It is a *derivation coordinate*
    rather than post-processing: the gadget writes the live tape and leaves
    interpreter state behind, so a joint that did not emit it would be
    simulating a different program than the one that ships.  The pass that
    varied it has been removed (see below); the parameter stays because the
    coordinate is real and cheap to keep open.

    The setters are emitted in ascending name order whatever the mask says --
    the gadget goes *after* the setter it complements, never in place of a
    different one -- so a flipped embed satisfies the slot-order invariant
    ``tests/tools/test_boolean_parameterized.py`` holds every generator to.
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        if (flips >> i) & 1:
            j.emit(_FLIP)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


# Pool codes move a mark right,.
# The five shipped plans are.
# joint-state check used for.
# seemingly similar strings can.
def _step(carry: int = 1, backs: int = 1, *, odd: bool = True) -> str:
    """One step of a pool code: carry a mark right, then walk the pointer back.

    This is the ``ceil(k / 2)`` law inverted.  A run of ``k`` brackets carries
    a mark right by ``ceil(k / 2)`` and leaves a pending skip when ``k`` is
    odd, so asking for a carry of ``c`` fixes the run at ``2 * c - 1`` when
    the skip is wanted and ``2 * c`` when it is not.  The trailing ``<`` runs
    set how far behind the mark the pointer ends up, which is the second free
    variable: the carry is clean only from just left of the mark.
    """
    return "[" * (2 * carry - odd) + "<" * backs


# Each plan is ``(steps, core,.
# which one is the core, and.
# step carries the mark one.
# core carries two.
# construction indexed by where.
# .
# An override is ``(backs,.
# variables stay visible side.
# .
# **Why these values, and not a.
# compress further, which was.
# derivable from the finished.
# ``core > 0`` ends at ``mark =.
# the core's index -- verified.
# outcome cannot pick it.
# properties split the way they.
# strands tables at every.
# third, 18 for the fourth, 6.
# is exactly what dropping.
# strands nothing at any.
# instead: slot order goes from.
# cost the ablation records for.
# .
# Only the first plan's core.
# core.
# the ablation finds strands.
# the arity being measured.
# functions, leaving marks at.
_PLANS: tuple[tuple[int, int, dict[int, tuple[int, bool]]], ...] = (
    (2, 0, {1: (4, True)}),
    (4, 1, {}),
    (5, 2, {}),
    (5, 3, {0: (2, True)}),
    (5, 3, {2: (2, True), 4: (3, False)}),
)


def _render(steps: int, core: int, overrides: dict[int, tuple[int, bool]]) -> str:
    """Spell one plan out as a pool code."""
    codes = []
    for i in range(steps):
        backs, odd = overrides.get(i, (1, True))
        codes.append(_step(carry=2 if i == core else 1, backs=backs, odd=odd))
    return "".join(codes)


_POOL_CODES = tuple(_render(*plan) for plan in _PLANS)


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out.

    The pool must read ``0011000`` plus ``cell7`` at print time, and the walk
    out to the accumulator crosses it -- so what matters is the pool *after*
    that walk, not at the moment the code ends.
    """
    target = (*_POOL, cell7)
    probe = [m.copy() for m in j.ms]
    for char in code:
        for m in probe:
            m.exec(char)
    if any(m.dead or m.skip for m in probe):
        return False
    if len({m.ptr for m in probe}) != 1:
        return False
    steps = walk_out - probe[0].ptr
    if steps < 0:
        return False
    for _ in range(steps):
        for char in "[x":
            for m in probe:
                m.exec(char)
    for cell in range(_POOL_WIDTH):
        col = {m.cell(cell) for m in probe}
        if len(col) != 1 or probe[0].cell(cell) != target[cell]:
            return False
    return True


# What the pool derivation.
# out (measured over 9..39, no.
# derivation needs *a* value.
# the key omit it.
# rejects anything under 8 and.
# or further left.
_PROBE_WALK_OUT = _POOL_WIDTH + 1

# : The window a pool verdict.
_POOL_MASK = (1 << _POOL_WIDTH) - 1


# : How far right a row can sit.
# :.
# : The bound is not "where.
# : -- but **where the window.
# : further right, and this is.
# :.
# : * At pointer 3 the codes.
# : determines the verdict: 3.
# : the cells above them were.
# : 2400, over eight redraws of.
# : * From pointer 4 the.
# : :func:`_find_pool` deletes:.
# : 39, none of them below.
# :.
# : So the table is derived.
# : and a row beyond it is.
# : every site a build reaches.
# : three inputs -- so the.
# : and refusing is what keeps.
# : that cells outside the key.
_POOL_PTR_MAX = 2


def _pool_code_for_row(
    codes: tuple[str, ...], low: int, ptr: int, cell7: int, *, skip: bool
) -> tuple[int, int] | None:
    """Return the pool code this row admits and where it leaves it, or None.

    The pointer comes back with the code because a pool is only a pool if
    every row reads it from *one* place: the code that answers each row
    separately still fails the joint when it leaves the rows on different
    cells.  That is a cross-row condition, so a per-row verdict alone cannot
    express it -- see :func:`_find_pool`, which compares the pointers the rows
    come back with.

    The verdict depends on **cells 0..7 of the row, where the pointer sits, and
    whether a skip is pending** -- and on nothing else.  A code is a fixed
    string, so its effect on that state is a fixed function; the walk out that
    follows is :meth:`_Sim.run_walk`, whose closed form is the prefix-XOR carry
    law that method documents.  Composing the two *computes* the answer, so
    this asks each code what it does rather than trying it against the target,
    which is why the pool is no longer a search.

    Sufficiency of the window is measured, not assumed: over 400 random values
    of cells 0..7, each run with cells 8..40 randomised six ways, no verdict
    changed.  Nothing above the window is read, so a row is summarised by one
    byte plus its pointer and skip.

    **At the origin at most one code answers a row**: over the 512 keys a
    build can reach, the accepting sets are singletons (36) or empty (476).
    That is the fact that makes the pool a lookup rather than a trial -- at
    every state the generator actually asks about, a key *names* its code.

    Away from the origin the property is not free: of the 3072 keys in the
    derived domain, 104 admit exactly one code and 4 admit two, the latter all
    with the pointer moved on or a skip pending.  Those four are settled by the
    ordering -- the first index wins, which is the answer the scan gave, so the
    two agree by construction rather than by luck.  Recording the number
    matters: "one code per key" is true where it is used and false in general,
    and a rule that claimed the strong form would be wrong at the edges the
    generator does not visit.

    ``cell7`` is not a second dimension.  At the origin ``(low, cell7)`` is
    admitted exactly when ``(low ^ 0x80, 1 - cell7)`` is, by the same code,
    with no exception over the 512: the orientation is a mirror of bit 7 of
    the window.
    """
    for index, code in enumerate(codes):
        probe = _Sim(_POOL_WIDTH + _PROBE_WALK_OUT + _POOL_PTR_MAX + 4)
        probe.tape = low
        probe.ptr = ptr
        probe.skip = skip
        probe.apply(_runs(code))
        # Neither guard the scan.
        # over its 7680 (key, code).
        # mid-skip, and none ends right.
        # refusals when a *candidate*.
        # so a code that broke either.
        # than a state to skip past,.
        # would quietly drop the code.
        if probe.dead or probe.skip:  # pragma: no cover - see the note above
            raise AssertionError(f"pool code {code!r} left a row unrunnable")
        steps = _PROBE_WALK_OUT - probe.ptr
        if steps < 0:  # pragma: no cover - see the note above
            raise AssertionError(f"pool code {code!r} ended past the walk out")
        landed = probe.ptr
        probe.run_walk(steps)
        target = (*_POOL, cell7)
        if all(probe.cell(cell) == target[cell] for cell in range(_POOL_WIDTH)):
            return index, landed
    return None


@cache
def _pool_slice(
    codes: tuple[str, ...], ptr: int, *, skip: bool
) -> dict[tuple[int, int], tuple[int, int]]:
    """Derive the verdict for every window byte at one ``(pointer, skip)``.

    The slice is **exhaustive in the coordinates the caller does not fix**:
    every one of the 256 window bytes at both orientations.  So this is still
    the predicate over its slice rather than a memo of the states a build
    reached -- ask it once and it answers for windows that never occur as
    readily as for the one that did.

    Deriving a slice at a time is what keeps a caller from paying for the
    whole domain.  Builds only ever ask at the origin with no skip -- all 1956
    sites at two and three inputs -- so a build derives one slice of six and
    the rest come into being only if something asks, which in practice is the
    test that sweeps them.  Whole-domain derivation cost 57ms on first touch
    against a 0.2ms one-input build; the slice is a sixth of that, and the
    exhaustiveness argument the whole-domain form was carrying now lives where
    it belongs, in the test that checks every key against the scan.

    Keyed on the code list because the codes are ablated -- dropped one at a
    time to measure what each is worth -- and a table derived against a list
    no longer in force would report that a dropped code stranded nothing.
    """
    return {
        (low, cell7): answer
        for low in range(1 << _POOL_WIDTH)
        for cell7 in (0, 1)
        if (answer := _pool_code_for_row(codes, low, ptr, cell7, skip=skip)) is not None
    }


def _find_pool(j: _Joint, cell7: int, walk_out: int) -> str | None:
    """Return the pool code for this orientation, or None if none fits.

    Every row names the one code it admits, through :data:`_POOL_CODE_OF`, and
    the joint answers that code when the rows agree.  **The joint's verdict is
    the AND over its rows** -- measured over 40000 checks (4000 random joints x
    1, 2, 4 and 8 rows x both orientations x all five codes) with no
    disagreement against the simulated :func:`_pool_reaches`.

    That is why this is a lookup per row rather than a trial per code.  The
    breadth-first search here originally, and the five-code trial that replaced
    it, both asked "does this candidate match?"; the row's window byte answers
    "which code does this state admit?" directly, so nothing is tried.

    Row uniformity is *not* required and must not be assumed.  It holds at
    every site a build reaches -- 2024 call sites at two and three inputs, all
    with the pointer at 0, no pending skip, no dead row -- but a joint whose
    rows differ inside the window can still be admitted, because the code's
    carry cascade can merge differing cells: a constructed two-row state
    differing at cells 5 and 6 is accepted by the same code both rows name.
    The AND handles that; a "rows must agree in the window" guard would
    wrongly refuse it.

    ``walk_out`` decides whether a code is *asked*, not whether it fits: the
    verdict is invariant in it.  Measured over walk_outs 9 to 39, no
    ``(site, code)`` pair changes answer -- 0 of 1000 at four and eight rows,
    0 of 300 at sixteen.  That follows from the affine picture, since cells
    0..7 after the walk depend only on what was crossed before them, and it
    is why arity reaches the pool codes only through the joint's rows and
    window state rather than through how far right the accumulator sits.  It
    stays in the signature because callers reason in terms of their own
    accumulator, and dropping it would push the invariance argument out to
    every call site.
    """
    del walk_out

    codes = tuple(_POOL_CODES)

    def answer_for(row: _Sim) -> tuple[int, int] | None:
        """Which code this row names, and where that code leaves it."""
        if row.dead or row.ptr > _POOL_PTR_MAX:
            # A dead row prints nothing,.
            # window's reach.
            return None
        rows = _pool_slice(codes, row.ptr, skip=row.skip)
        return rows.get((row.tape & _POOL_MASK, cell7))

    chosen = answer_for(j.ms[0])
    if chosen is None:
        return None
    for row in j.ms[1:]:
        # Equality covers both.
        # code *and* be left on the.
        if answer_for(row) != chosen:
            return None
    return codes[chosen[0]]


def _endgame(j: _Joint, acc: int, read: str, cell7: int) -> None:
    """Set the pool, relay ``acc`` into the pointer, and print one digit.

    The walk back to the pool is measured from the read's *entry*: a
    constant-1 column diverges every row alike, so the pointer's minimum sits
    one cell further right than for a column with a zero row, and measuring
    from there would short the walk by one.
    """
    if acc < _POOL_WIDTH:
        raise ValueError("accumulator must sit past the pool")
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        raise ValueError("no pool pattern for this orientation")
    j.emit(code)
    _walk_to(j, acc - 1)
    j.emit(read)
    j.emit("<" * (acc - (_POOL_WIDTH - 1)))
    # ``_find_pool`` accepts a code.
    # walk out, which is the state.
    # restated on what was actually.
    # It is an AssertionError.
    # disagreeing is a bug in the.
    # ValueError, which would turn.
    for cell in range(_POOL_WIDTH):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)


# Derived columns, keyed by.
# dict rather than.
# ``_Joint`` rather than being.
# answer here -- the sentinel.
# .
# ``_derived_plans.cache_clear``.
# a cold derivation means a.
# from a build and assert they.
# seventeen.
_PRINTED_COLUMNS: dict[tuple[str, int, int], tuple[int, ...] | None] = {}
_MISSING = object()


def _printed_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return what the ``'[x<[<'`` read prints here, without printing it.

    The endgame is not a search: what it prints is fixed by the tape once the
    pool is set and the walk has run.  Emitting the pool code and walking to
    ``acc - 1`` leaves the pointer one cell short of the answer, and the read
    then reports the cell at ``ptr + 1`` -- directly for ``'[x<[<'`` and
    complemented for ``'[<'``, which is the only difference between the two.
    So one walk yields both reads' columns, and neither has to be run.

    This is the same value :func:`_endgame` would print, derived rather than
    observed.  Checked against it over every ``(separator, settle, bracket
    run, accumulator, orientation)`` at two, three and four inputs: 15600
    columns, no disagreement.  :func:`_confirm` re-checks each one that is
    actually used, so a divergence would surface as a miss rather than as a
    wrong program.

    Returns None when this orientation has no pool pattern or the walk cannot
    reach, which are the two conditions :func:`_endgame` raises on.

    Memoised on the staging's own template, because what this derives does not
    depend on which tables are wanted: the whole-arity spelling computes each
    column once and matches it against every table, while the table-major one
    would recompute the identical column for every build.  Measured at three
    inputs, the enumeration visits 12612 distinct ``(staging, accumulator,
    orientation)`` triples however many tables are asked for -- 8 builds make
    46790 calls and 40 make 206488, both over that same 12612 -- so the cache
    is what lets asking per table cost what asking for the arity does.
    """
    key = (j.template(), acc, cell7)
    hit = _PRINTED_COLUMNS.get(key, _MISSING)
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    column = _derive_column(j, acc, cell7)
    _PRINTED_COLUMNS[key] = column
    return column


def _derive_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return the column :func:`_printed_column` memoises, derived fresh.

    Split out because two callers want opposite cache behaviour: the staged
    oracle asks about the same few stagings again and again, so the memo
    above pays for itself, while :func:`_try_print` is handed a fresh
    template on every sculpted build -- a memo keyed on those would grow one
    entry per build and never hit.
    """
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        return None
    probe = j.fork()
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed; as _printed_column
        # Never seen to fire, but *not*.
        # this says "not observed".
        # argument -- that `_find_pool`.
        # `acc - 1`, so the walk must.
        # is deleted rather than.
        # in it.
        # right the accumulator can.
        # .
        # What is measured: 1740 real.
        # and three inputs, walked over.
        # cache cleared each time -- no.
        # unreachable target raises, as.
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1))


def _column_sweep(j: _Joint, cell7: int) -> dict[int, tuple[int, ...]]:
    """Return every accumulator's printed column, from **one** walk.

    :func:`_printed_column` answers one accumulator, and answering all of them
    that way re-walks the same ground once per accumulator: the walk to
    ``acc - 1`` is a prefix of the walk to ``acc``.  This runs the walk once
    and reads a column off as the pointer passes each accumulator in turn.

    What makes that sound is that the pool code does not depend on the
    accumulator.  :func:`_find_pool` is asked for a ``walk_out``, so it *could*
    answer differently per accumulator and the fused walk would be wrong --
    but measured over every ``(separator, settle, suffix, orientation)`` at
    two, three and four inputs it never does: one code serves the whole
    accumulator range or none does.  So the code is chosen once, from the
    shortest walk, and the walk is then extended.

    Checked against :func:`_printed_column` rather than argued: 30160 columns
    over the *entire* enumeration at two and three inputs, and 18720 more at
    four across both suffix families, with no disagreement.  Accumulators the
    walk cannot reach are absent from the mapping, which is the ``None`` that
    function returns.
    """
    code = _find_pool(j, cell7, 8)
    if code is None:
        return {}
    probe = j.fork()
    probe.emit(code)
    ptrs = set(probe.ptrs())
    if len(ptrs) != 1:
        # Setting the pool is what.
        # leaves exactly one pointer:.
        # three inputs, 27620 sweeps,.
        # check stays because that.
        # codes rather than something.
        return {}  # pragma: no cover - the pool converges the rows
    cur = ptrs.pop()
    columns: dict[int, tuple[int, ...]] = {}
    for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
        if acc - 1 < cur:
            # The walk only ever runs.
            # the pool leaves `cur` at 4 or.
            # sweeps) and the loop starts.
            # always behind.
            continue  # pragma: no cover - the pool lands below the range
        probe.emit("[x" * (acc - 1 - cur))
        cur = acc - 1
        columns[acc] = tuple(probe.col(probe.ms[0].ptr + 1))
    return columns


def _confirm(
    j: _Joint, acc: int, read: str, cell7: int, column: tuple[int, ...]
) -> bool:
    """Whether the endgame really prints ``column`` here.

    The derivation above settles which accumulator answers a table; this runs
    the endgame that was chosen and checks it, so nothing is recorded on the
    strength of the algebra alone.  It is the same standard the enumeration
    has always applied -- a staging is accepted on the evidence of its own
    output -- narrowed to the accumulators that are about to be used.

    :func:`_endgame` also asserts the pool is input-independent, a side
    condition the derivation does not model; a failure there is a bug in the
    pair rather than a miss, so it is left to propagate.
    """
    probe = j.fork()
    try:
        _endgame(probe, acc, read, cell7)
    except ValueError:  # pragma: no cover - not observed; as _printed_column
        # The derivation only offers.
        # read off a walk, so the.
        # Traced over every table at.
        # none of them raising.
        # point of this function is.
        # of the algebra alone -- an.
        # the disagreement it exists to.
        return False
    printed = probe.printed()
    if any(len(digit) != 1 for digit in printed):
        return False
    return tuple(int(digit) for digit in printed) == column


def _try_print(j: _Joint, truth_table: str, acc: int) -> _Joint | None:
    """Emit the endgame that prints the table at ``acc``, or None.

    The choice of read and orientation is **computed, not tried**.  This
    used to fork the joint four ways, run all four endgames, and keep
    whichever printed -- the last candidate search on the build path.  What
    each pair prints was never in doubt, though: the column is fixed by the
    tape once the pool is set and the walk has run (:func:`_derive_column`),
    and the two reads differ only in polarity -- ``'[x<[<'`` reports the
    column directly and ``'[<'`` complemented, the same mapping the staging
    index's ``claim`` uses.  So one derivation per orientation names the
    pair, in the order the trial loop used, and one endgame is emitted.

    Nothing is returned on the strength of the algebra alone: the emitted
    endgame's own output is still compared against the table, which is the
    module-wide standard, and :func:`_endgame` still asserts the pool is
    input-independent.  Both guards are kept as the acceptance even though
    a divergence has never been observed -- the derivation was checked
    against the emission over 15600 columns when it landed, and the corpus
    is byte-identical under the computed choice.
    """
    if acc < _POOL_WIDTH:
        # The endgame's own first.
        # the pool cannot be printed.
        # one would send its walk.
        # every recorded cell and the.
        # -- the walk-in's own wake --.
        # build reaches rather than a.
        return None
    want = list(truth_table)
    derived: dict[int, tuple[int, ...] | None] = {}
    for read in _READS:
        for cell7 in (0, 1):
            if cell7 not in derived:
                derived[cell7] = _derive_column(j, acc, cell7)
            column = derived[cell7]
            if column is None:
                continue
            digits = column if read == _READS[1] else _complement(column)
            if list(map(str, digits)) != want:
                continue
            probe = j.fork()
            try:
                _endgame(probe, acc, read, cell7)
            except ValueError:  # pragma: no cover - not observed; see below
                # The endgame refuses on.
                # derivation already declined.
                # that cannot reach -- so a.
                # somewhere to go.
                # emission disagreeing is.
                # below exists to catch, and a.
                # disagreement's other spelling.
                continue
            if probe.printed() != want:  # pragma: no cover - the acceptance
                # Never observed -- the.
                # algebra -- but this is the.
                # divergence is reported as a.
                continue
            return probe
    return None


_DEGENERATE_COLUMNS = ("const1", "~b0", "b0", "const0", "~b1", "b1")


def _column_of(name: str, n: int) -> tuple[int, ...] | None:
    """Return the column ``name`` stands for, or None if this arity has no such bit.

    ``b1`` does not exist at one input, and it must come back as None rather
    than as some default: an all-zero stand-in would match wherever
    ``const0`` does, and the route would carry a duplicate cell that means
    nothing.
    """
    rows = range(2**n)
    if name in ("const0", "const1"):
        return tuple(int(name == "const1") for _ in rows)
    negated = name.startswith("~")
    bit = int(name.lstrip("~")[1:])
    if bit >= n:
        return None
    return tuple((((r >> (n - 1 - bit)) & 1) ^ negated) for r in rows)


@cache
def _degenerate_cells(n: int) -> dict[str, int]:
    """Find where the embed leaves the constants and the first two inputs.

    These were six written-down cell numbers, and the reason they were
    constant is also the reason they need not be written down: the carry
    chain preserves ``b0`` and ``b1`` individually before the prefix-XOR
    starts mixing, so the cells holding them can be *read off* the embedded
    tape.  Measured, this reproduces the six exactly at every arity the route
    serves.

    Later inputs are not separable here at any settle count -- the affine
    transform fixes which bits stay apart.  A column search used to pick
    those up; :func:`_mux` builds them instead, so this route is now a pure
    lookup and the whole generator is search-free.

    Only the default settle count is meaningful: :func:`_degenerate` embeds
    with it, and re-crossing the region moves these columns elsewhere.
    """
    joint = _embed(n, sep=_SEP)
    _clamp(joint)
    wanted = {
        name: column
        for name in _DEGENERATE_COLUMNS
        if (column := _column_of(name, n)) is not None
    }
    found: dict[str, int] = {}
    for cell in range(1, _BASE + n * _SPAN + 8):
        column = joint.col(cell)
        for name, target in wanted.items():
            if name not in found and column == target:
                found[name] = cell
    return found


def _degenerate(truth_table: str, n: int) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    Such a table is a constant, a projection, or a negated projection, and
    every one of those already stands as a *column* at a known cell after the
    embed.  So the whole construction is: read off the cell holding the
    answer, then run the endgame on it.

    This is the piece that composes upward: a table with ``k`` essential
    inputs is a ``k``-input problem whatever its arity, so four of the
    fourteen three-input orbits are handled here for free.

    This route is now **entirely a lookup**.  A column search used to sit
    below the cell reads, for the projections of a *later* input the read-off
    cells do not hold -- six tables at ``n <= 4``: ``X2`` and its complement
    at three inputs, ``X2``/``X3`` and theirs at four.  All six build through
    :func:`_mux` in milliseconds and print every row on the shipped
    interpreter, and :func:`_solve` runs that route directly after this one,
    so declining is strictly better than searching: the caller reaches a
    construction rather than a sweep.  A ``fixed_cells_only`` flag that let
    the name-order caller skip the search went with it.
    """
    base = _embed(n, sep=_SEP)
    _clamp(base)

    for acc in _degenerate_cells(n).values():
        hit = _try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template()
    return None


def _project(truth_table: str, essential: list[int], n: int) -> str:
    """Rewrite the table over its essential inputs only.

    A table that ignores some of its inputs is a smaller table wearing extra
    ones.  Reading it at the essential positions gives that smaller table,
    which is a ``len(essential)``-input problem however wide the original was.

    The read itself is :func:`read_at`, shared with
    :func:`permute_truth_table` -- a permutation is the case where every
    input is essential, so nothing is held back.
    """
    return read_at(truth_table, essential, n)


# The fixed head of the.
# ``<``, which clamps rather.
# enough to bring every row.
_RESET_HEAD = "[<[<<[<[<"


def _reset_code(ignored: int) -> str:
    """Return code after which the ignored inputs leave no trace.

    The setters for the inputs a table ignores still have to be emitted --
    the harness has a bit for every input -- and emitting them first is what
    keeps the placeholders in name order.  They do write the tape, though, so
    what follows must erase the difference: after this suffix all
    ``2**ignored`` rows are in *identical* states.

    Identical, not blank.  A blank tape is unreachable -- the all-ones row
    ends a cell to the right of the others and ``<`` clamps without writing,
    so the rows cannot be driven back to the origin together -- but they can
    be driven to a common non-blank state, which is all the rest of the
    construction needs.

    Constructed, not searched.  A breadth-first search used to find this, and
    what it found was a *family*: length 12 at two ignored inputs, the same
    string with one more ``<`` at three, and nothing at all at four, where
    its depth cap bit before the answer.  The pattern is just
    :data:`_RESET_HEAD` followed by ``ignored + 1`` clamping steps, and it
    converges at every arity tried, 1 through 8 -- so the cap that made four
    unreachable went with the search.
    """
    return _RESET_HEAD + "<" * (ignored + 1)


def _reconverged(truth_table: str, essential: list[int], n: int) -> str | None:
    """Build by emitting the ignored inputs first, then erasing them.

    ``_lift`` puts the ignored placeholders last, which leaves name order.
    The alternative is to emit them *first* -- ``{X0}``..``{Xn-1}`` stays
    ascending -- and then reconverge the rows so nothing downstream can tell
    which bits they were.  After that the table is a one-input problem in its
    single essential input, and the rest is the embed geometry every other
    degenerate table uses.

    The walk to ``_BASE - 1`` before the essential setter is what makes this
    cheap rather than a fresh search: it reproduces the standard embed, so
    the essential input lands on the cells :func:`_degenerate_cells` finds,
    and the fixed-cell lookup decides in a fraction of a second.  The
    junk the reset leaves behind is not a problem -- the rows are identical
    by then, so it is a constant starting condition, which is exactly what
    the lookup here is built to run from.
    """
    if not 1 <= len(essential) <= 2:
        return None
    ignored = [i for i in range(n) if i not in essential]
    if ignored != list(range(len(ignored))):
        # The ignored inputs have to be.
        # first to keep the order.
        return None

    # Where to look for the answer.
    # essential input leaves a.
    # leave a two-input table,.
    # that staging and read its own.
    # scan is what costs: at two.
    # seconds without reaching.
    if len(essential) == 1:
        setup: tuple[int, int, int, int] | None = None
        accumulators: tuple[int, ...] = tuple(_degenerate_cells(n).values())
    else:
        inner = _project(truth_table, essential, n)
        plan = _derive_staging(inner, 2)
        if plan is None:
            return None
        sep_index, settle, brackets, acc = plan
        # Every two-input staging is a.
        # form is only used by the one.
        # replaying it here would need.
        if not isinstance(brackets, int):
            return None
        setup = (sep_index, settle, brackets, acc)
        accumulators = (acc,)

    # One constructed reset rather.
    # convergence is still.
    # construction came from.
    # surface much later as a table.
    j = _Joint(n)
    for i in ignored:
        j.emit_setter(i)
    j.emit(_reset_code(len(ignored)))
    if len({m.key() for m in j.ms}) == 1:
        _walk_to(j, _BASE - 1)
        if setup is None:
            j.emit_setter(essential[0])
            j.emit("[x")
        else:
            sep_index, settle, brackets, _acc = setup
            for slot, i in enumerate(essential):
                j.emit_setter(i)
                j.emit("[x")
                if slot + 1 < len(essential):
                    j.emit(_SEPS[sep_index])
            # The staging's settle count,.
            # it: re-crossing the bit.
            # the accumulator was chosen.
            # The enumeration hands back.
            # and six three-input tables.
            # ignoring the field would.
            for _ in range(settle):
                _clamp(j)
                _walk_to(j, _BASE - 1)
            _clamp(j)
            _walk_to(j, _BASE - 1)
            j.emit("[" * brackets + "<")
        _clamp(j)
        for acc in accumulators:
            hit = _try_print(j, truth_table, acc)
            if hit is not None:
                return hit.template()
    return None


# The staged construction: one.
# per complement pair,.
# .
# The embed leaves an affine.
# input bits plus the one.
# plain run of ``k`` brackets.
# exposing a different function.
# the separator, the bracket.
# to the endgame every other.
# .
# Which is small enough to.
# 5 separators x 2 settle.
# a table is built by the first.
# is needed.
# .
# :func:`_derived_plans` runs.
# which is what makes it.
# cheap to test against a.
# (separator, settle), the.
# and the endgame emitted once.
# whatever the table.
# and two inputs in 0.15s; the.
# minutes, because it rebuilds.
# 15s and 0.9s when this was.
# carried forward -- a timing.
# .
# What the three-input arity.
# over all five separators --.
# counts, 94 at zero and 33 at.
# separator 4 carrying four.
# a glance at how often each is.
# .
# Selection is on the.
# that holds the answer.
# applies the running.
# ``(0,0,0,1)`` arrives as the.
# arrives as ``b1``.
# version of this cover 10 of.
# The enumeration sidesteps.
# about which column *ought* to.
# the rows actually printed.
# .
# A table and its complement.
# read polarities and both pool.
# ``NOT(v XOR cell7)``, so the.
# why the counts below are.
_Staging = tuple[int, int, int | str, int]

# **The population every figure.
# complement pairs of.
# on all three inputs: 128.
# less the 16 that ignore an.
# only "non-degenerate" leaves.
# is why two later re-probes.
# reporting 252, which is not a.
# :func:`_staging_index`, twice.
# its complement.
# copy of the test.
# .
# **Coverage, and the one table.
# reaches 108 of those 109 and.
# the table named just below is.
# of a similar size would not.
# The holdout is ``01101101`` /.
# knowing: it was the hardest.
# never built it at all -- both.
# .
# Its answer column is not.
# standing somewhere on the.
# *carries* it to the read,.
# cell.
# enumeration cannot reach it,.
# and the stored suffix.
# .
# The shape of that miss is.
# the tables the wider.
# ``01101101`` stands as a.
# What fails is the carry -- no.
# staging it arrives as.
# its complement.
# ``k <= 40`` and every.
# skipped slices scored worst.
# scored best -- reaching.
# and all missed.
# .
# It is a gap in this family,.
# arrive across the family, and.
# one (all 255 parity masks.
# .
# What closed the *other* gaps.
# set.
# the 252 columns standing, and.
# reach did not stand as a.
# those 120, every one of which.
# .
# The bracket axis is.
# than assumed.
# ``ptr + 1`` and, on the.
# advances -- so once every.
# no further bracket can change.
# changing between ``k == 25``.
# settle count, so the sweep.
# redundant.
# ``k == 26`` at three inputs.
# :data:`_MAX_BRACKETS` comes.
# rather than a bound.
# .
# The other two axes were.
# empty -- settle counts 3 to 5.
# shipped stagings did not.
# .
# **A simpler form was looked.
# enumeration replaced a stored.
# the wish was a *uniform* rule.
# even at the cost of longer.
# fails, which is why all four.
# .
# * **One fixed staging:.
# A staging offers one column.
# over the ranges used here --.
# prefix-XOR is many-to-one and.
# same column.
# single one delivers 13 pairs.
# So this is short by a factor.
# .
# Nor is there a *cheap.
# Measured on the full.
# assignment, which is.
# reaches first): at four.
# condition, every one of the.
# tables reachable nowhere.
# one slice.
# weight 2 and 14 against 18.8%.
# empty, so nothing licenses.
# ``docs/generators/minifuck_gen.
# .
# An earlier version of this.
# cannot be indexed at all,.
# the closed-form column.
# target's first pure-run.
# bitmasks read off the bracket.
# set bit in enumeration order.
# keys at three inputs, 464.
# mismatches).
# opacity: the 4640 stagings.
# vectors, so there is no large.
# per-table inversion of the.
# sub-sweep form, and the pure.
# 0.4-0.75s whole-arity fill.
#   why the tabulation stays.
# * **Two separators: 49 of.
# which was wrong by more than.
# line directly below, whose 99.
# claim survives and is in fact.
# half the population, so the.
# than a longer program, which.
# * **Dropping the settle.
# reachable only at ``settle ==.
#   fields.
# .
# Both ablations are measured.
# index really walks.
# -- it has no callers -- and.
# result, which is a third.
# now produced twice before.
# sculpt).
# it reports the baseline for.
# .
# Separator 0 is the one.
# separators 1 to 4 reach 108.
# first anyway because it.
# :data:`_SEP` and.
# .
# **What happened at four.
# Four-input AND and NAND build.
# 2.4s -- all before the.
# What the searches could not.
# the time was that the pool.
# XOR's failed attempt made.
# same one-in-two rate the.
# .
# That reading was right about.
# now builds from a staging,.
# search nor the pool but the.
# available, the enumeration.
# and :func:`_insert_suffixes`.
# the arity falls through to,.
# .
# Which code answers does shift.
# trimming the list on.
# here, sixteen-row joints were.
# fifth answers almost nothing.
# ``n <= 3`` under-reports what.
# the sample is small: the.
# fifth code alone, while the.
# as "arity changes which code.

# The arities the enumeration.
# five are partial, and are.
# replaces.
# miss: it is not that the.
# has not been shown to.
# made.
# .
# Five was gated shut on.
# at that arity, which is the.
# fully-essential 32-bit.
# them.
# ships on the same argument --.
# cannot cost coverage.
# at all is that.
# rather than for the whole.
# .
# Four inputs is gated on.
# below reaches 15404 of the.
# four-input XOR among them --.
# on.
# admitting the arity cannot.
# .
# What it costs is time, and.
# because it is unlike the.
# derivation stops early: every.
# zero partway through.
# unreachable -- so the.
# about 76 seconds.
# table in a process whether it.
# cached, so it is paid once.
# ignored input are answered by.
# :func:`minifuck` before the.
# .
# The caps are not slack that.
# them -- suffixes to ``k ==.
# at ``k <= 24`` against 15404.
# coverage.
# says this arity wants the.
_STAGED_ARITIES = (2, 3, 4, 5)

# How far the enumeration runs.
# every table plus a margin,.
# and an accumulator of 40, the.
# ``(k=6, acc=20)`` and at.
# those, so the sweep stops a.
_MAX_BRACKETS = 28
_MAX_ACC = 34

# Only the *upper* ends are.
# starts at.
# lower end is not a search.
# pool, which :func:`_endgame`.
# :data:`_POOL_WIDTH`, so the.
# right.
# said the other way round --.

# How much of the enumeration a.
# **stagings visited** rather.
# .
# The unit is the point.
# non-deterministic across.
# host and raise on a slow one,.
# on how loaded the box was.
# suffix, accumulator)`` tuple.
# is identical everywhere -- a.
# a Raspberry Pi and on an M3,.
# The count also tracks real.
# whole accumulator range from.
# constant unit.
# .
# **A budget costs program.
# short of falls through to.
# about 11ms -- so lowering.
# trades is the staged route's.
# inputs: 205 characters.
# gives up.
# .
# ``None`` means no budget,.
# the default must reproduce.
# recorded template changes.
_STAGING_BUDGET: int | None = None

# Five inputs used to ship a.
# longer does is that its.
# argument was that the arity.
# could not place, and that.
# so a miss paid the whole.
# dict lookup:.
# and after that neither a hit.
# .
# So the budget bought nothing.
# pass is 2.4s and reaches 6340.
# **21756 more**, for six.
# wherever they overlap: every.
# because a budget truncates.
# lifting it cannot change a.
# .
# What it does change is.
# separately-verified step.
# enumeration went from a raise.
# and every one builds and.
# .
# ``None`` means no budget,.
_STAGING_BUDGET_N5: int | None = None


def _budget(n: int) -> int | None:
    """Return the staging budget for this arity, in stagings visited."""
    if n >= 5 and _STAGING_BUDGET is None:
        return _STAGING_BUDGET_N5
    return _STAGING_BUDGET


# The ``(separator, settle)``.
# inputs, which is what makes a.
# same 12064 stagings, and what.
# tables for the best against.
# this order buys 77% of the.
# Enumerating in the plain.
# flat trade, since hits are.
# .
# Measured at ``n == 4`` and.
# arity the ranking is.
# unless a budget is actually.
# going to be given up.
# .
# The yield is *marginal*: a.
# to reach walking the plain.
# place alone -- ranking by.
# this is derived rather than.
# ``test_the_slice_order_is_its_.
# ``_staging_index(4)`` each.
# ten counts differ, so.
_SLICE_YIELD_ORDER = (
    (3, 0),
    (2, 0),
    (3, 1),
    (2, 1),
    (4, 0),
    (4, 1),
    (0, 0),
    (0, 1),
    (1, 1),
    (1, 0),
)


def _slices(n: int) -> tuple[tuple[int, int], ...]:
    """Return the ``(separator, settle)`` slices, in the order to spend them.

    Plain enumeration order when there is no budget, so the shipped
    behaviour is exactly what it was.  Under a budget at the arity the
    ranking was measured at, yield order instead -- what is given up should
    be the slices that place the fewest tables.
    """
    plain = tuple(
        (sep_index, settle) for sep_index in range(len(_SEPS)) for settle in (0, 1)
    )
    if _budget(n) is None or n != 4:
        return plain
    return _SLICE_YIELD_ORDER


# The arities whose enumeration.
# offered at two or three.
# arities completely, and.
# every pure run has missed.
_INSERT_ARITIES = (4, 5)


def _insert_suffixes() -> Iterator[str]:
    """Enumerate bracket runs with one ``<`` inside, shortest first.

    The pure runs the enumeration spells as ``'[' * k`` are one string per
    length; putting a single ``<`` at each interior position gives ``k + 1``
    per length instead, which is where the four-input coverage comes from.

    This is not a free search over the alphabet -- that is what cost 29
    minutes to find the three-input suffix this family generalises, back when
    it was stored rather than derived.  It is the smallest generalisation of
    the pure run that that suffix proves necessary: it interleaves ``<`` into
    its bracket run, so a family no wider than "the same run with a ``<`` in
    it" was already known to reach columns no ``'[' * k`` reaches.  A second
    ``<`` reaches further still; that family was removed once the sculpted
    route covered the one pair it served.  What was not known, and what the
    measurement settled, is how *many*: at four inputs the pure runs reach
    1650 fully-essential columns and this family reaches 15404.

    The order is by length and then by the ``<``'s position from the left, so
    it is as deterministic as the bracket count it generalises.
    """
    for k in range(_MAX_BRACKETS + 1):
        for cut in range(k + 1):
            yield "[" * cut + "<" + "[" * (k - cut)


# The insert family,.
# a winning ordinal back as its.
# strings.
_INSERT_SUFFIXES = tuple(_insert_suffixes())


def _stagings(n: int) -> Iterator[_Staging]:
    """Enumerate ``(separator, settle, suffix, accumulator)`` in order.

    The order is what makes the derivation deterministic, and it is chosen so
    the cheap stagings come first: separator, then settle, then the bracket
    run, then the accumulator.  A table is built by the *first* of these that
    prints it, so this order -- not a stored table -- is what fixes which
    program each truth table gets.

    At an arity in :data:`_INSERT_ARITIES` the pure runs are followed by
    :func:`_insert_suffixes`, in a second pass over the same separators and
    settles.  It is a second pass rather than an inner loop deliberately:
    every pure run is tried before any insert, so an arity the pure runs
    already close is assigned exactly the stagings it was assigned before the
    family existed.  Two and three inputs are unchanged, table for table.

    Neither :func:`_derived_plans` nor :func:`_staging_index` calls this:
    the oracle interleaves the same loops with the machines it is advancing,
    so that a bracket count costs one instruction rather than a rebuild, and
    the index walks them over derived columns with no machines at all.  This
    states the order both implement.

    There are therefore *three* spellings of one order -- this one, the
    per-table enumeration, and the inverted index production reads -- and the
    test suite checks they agree.  That is not redundancy for its own sake:
    an index that walks the order wrongly still produces columns that are
    reachable and valid, so only a comparison against another spelling of the
    order catches it.
    """
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            for brackets in range(_MAX_BRACKETS + 1):
                for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
                    yield sep_index, settle, brackets, acc
    if n not in _INSERT_ARITIES:
        return
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            for suffix in _insert_suffixes():
                for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
                    yield sep_index, settle, suffix, acc


def _replay(truth_table: str, n: int, plan: _Staging) -> str | None:
    """Build one staging and return its template, or None if it does not print.

    The suffix is a bracket *count* for the pure runs -- a plain run, which
    the ``<`` terminates so the pointer lands where the endgame expects --
    and a literal string for the insert families, which carry their own
    terminator.
    """
    sep_index, settle, suffix, acc = plan
    j = _embed(n, settle=settle, sep=_SEPS[sep_index])
    _clamp(j)
    _walk_to(j, _BASE - 1)
    j.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return hit.template() if hit is not None else None


@cache
def _derived_plans(n: int, targets: tuple[str, ...]) -> dict[str, _Staging]:
    """Derive a staging for the wanted tables, in one pass of the enumeration.

    **This is the oracle, not the production path.**  :func:`_derive_staging`
    reads :func:`_staging_index`, which inverts the same enumeration once per
    arity; this walks it per table.  It stays because the index's correctness
    claim is *agreement with an independent implementation of the same
    order*, and an oracle that no longer exists cannot be compared against.
    ``tests/tools/test_boolean_parameterized.py`` pins the two together --
    the interesting failure is an index that walks the order wrongly, which
    still yields reachable, valid columns and so is invisible to any check
    that only asks whether the program prints.

    A staging is expensive to *build* and cheap to *test against a table*: the
    embed, the bracket run and the endgame do not depend on which table is
    wanted, and only the comparison at the very end does.  So the loops run
    staging-major -- one embed per ``(separator, settle)``, the bracket run
    extended one ``[`` at a time rather than rebuilt, and the endgame emitted
    once per ``(k, accumulator, read, orientation)`` -- and each printed column
    is looked up among the tables still wanting one.

    ``targets`` narrows *what is being looked for* without changing the
    enumeration: the same loops, the same order, the same first-hit rule.  A
    table is assigned the first staging in :func:`_stagings` order that prints
    it, whatever else was asked for alongside it.

    This used to offer a whole-arity spelling as well, which pre-built
    ``wanted`` over all ``2 ** (2 ** n)`` tables so that one pass answered the
    entire arity.  That could not run at five inputs -- ``2**32`` entries --
    and it is no longer worth its place below five either: what made it faster
    was deriving each column once, and :func:`_printed_column` now memoises
    exactly that, so asking per table costs what asking for the arity did.
    Measured across the whole suite, the two spellings finish within a second
    of each other (105.1s against 104.2s), so the narrower one is the only one
    kept.

    Returns a mapping from truth table to staging.  A table that no staging
    reaches is simply absent, so the caller falls through to :func:`_mux`.
    """
    if n not in _STAGED_ARITIES:
        return {}

    # What each printed column.
    # share a staging, so both.
    # is reached first assigns both.
    wanted: dict[tuple[int, ...], list[str]] = {}
    for table in targets:
        wanted.setdefault(tuple(int(c) for c in table), []).append(table)
    remaining = sum(len(tables) for tables in wanted.values())

    found: dict[str, _Staging] = {}

    def claim(staged: _Joint, suffix: int | str, head: tuple[int, int]) -> bool:
        """Record what every accumulator prints, deriving it rather than printing.

        Returns whether every table has been placed, which is what stops the
        enumeration early.  Both passes below share this: the suffix is
        already emitted by the time it runs, so a bracket count and an insert
        string reach it the same way.

        What an accumulator prints is not searched for.  :func:`_column_sweep`
        derives the whole accumulator range in closed form from the tape one
        walk leaves behind, so an accumulator that answers no wanted table
        costs a dict lookup rather than a walk -- and the range costs one walk
        rather than one each.  The two reads are not enumerated at all: they
        print complementary columns, so both are read off the one derivation.
        Only an accumulator that *does* answer a wanted table pays for an
        endgame, and then only to confirm it -- see :func:`_confirm`.

        The accumulator-major loop order is kept exactly, because it is what
        assigns each table its staging: a table takes the first accumulator
        that prints it, so sweeping orientation-major would reassign
        templates even though it derives the same columns.
        """
        nonlocal remaining
        sweeps = {cell7: _column_sweep(staged, cell7) for cell7 in (0, 1)}
        for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
            for cell7 in (0, 1):
                derived = sweeps[cell7].get(acc)
                if derived is None:
                    continue
                for read in _READS:
                    column = derived if read == _READS[1] else _complement(derived)
                    for table in wanted.get(column, ()):
                        if table in found:
                            continue
                        if not _confirm(staged, acc, read, cell7, column):
                            continue
                        found[table] = (*head, suffix, acc)
                        remaining -= 1
            if not remaining:
                return True
        return False

    # Stagings visited, against.
    # accumulator sweep rather than.
    # a ``(separator, settle,.
    # walks the accumulators for.
    spent = 0
    budget = _budget(n)
    accs = _MAX_ACC - _POOL_WIDTH

    def exhausted() -> bool:
        return budget is not None and spent >= budget

    slices = _slices(n)

    for sep_index, settle in slices:
        if exhausted():
            return found
        base = _embed(n, settle=settle, sep=_SEPS[sep_index])
        _clamp(base)
        _walk_to(base, _BASE - 1)
        run = base.fork()
        for brackets in range(_MAX_BRACKETS + 1):
            staged = run.fork()
            staged.emit("<")
            _clamp(staged)
            if claim(staged, brackets, (sep_index, settle)):
                return found
            spent += accs
            if exhausted():
                return found
            # Extending the run is what.
            # bracket count is one.
            # rebuild from the embed.
            run.emit("[")

    # The insert family, in a.
    # first and the arities the.
    # This pass cannot share the.
    # one place right is not one.
    # each string is emitted onto a.
    if n not in _INSERT_ARITIES:
        return found
    for sep_index, settle in slices:
        # Never taken, and kept for.
        # as a live exit: every `spent.
        # its own `exhausted()` that.
        # that check and this one -- a.
        # already stopped it inside the.
        # spanning the insert pass.
        # the whole enumeration):.
        if exhausted():
            return found  # pragma: no cover - see above
        base = _embed(n, settle=settle, sep=_SEPS[sep_index])
        _clamp(base)
        _walk_to(base, _BASE - 1)
        for suffix in _insert_suffixes():
            staged = base.fork()
            staged.emit(suffix + "<")
            _clamp(staged)
            if claim(staged, suffix, (sep_index, settle)):
                return found
            spent += accs
            if exhausted():
                return found
    return found


def _clear_derived_plans(
    _wrapped: Callable[[], None] = _derived_plans.cache_clear,
) -> None:
    """Clear the plan cache and everything derived alongside it.

    The staging index goes too, and that is the key part now that it
    is what :func:`_derive_staging` reads: a caller asking for a cold
    derivation means a cold one.  Tests harvest ``_find_pool`` call sites
    from a build and assert they saw hundreds, which a warm index cuts to
    six -- clearing the plan cache alone would leave that trap in place, and
    did, until the index was added here.
    """
    _wrapped()
    _PRINTED_COLUMNS.clear()
    _staging_index.cache_clear()
    _row_constraints.cache_clear()


_derived_plans.cache_clear = _clear_derived_plans  # type: ignore[method-assign]


# **A linear-algebra screen sat.
# endgame emits after the.
# that point, so a printed.
# columns, and ``_span_admits``.
# tables before the per-table.
# 143 seconds a doomed sweep.
# obsolete: the arity is.
# screen's only remaining.
# span bases against the 0.88s.
# every process that built any.
# removal: an index key is a.
# printed column by its own.
# lookup answer identically --.
# declines and 120 tables with.
# true; nothing consumes it any.


# How far right the closed-form.
# deepest read is one cell past.
# is bounded by the instruction.
# ``_MAX_BRACKETS`` brackets,.
# skip hands its job to the.
# ``_BASE - 1 + _MAX_BRACKETS +.
_CHAIN_CAP = _BASE + _MAX_BRACKETS + 4


class _Chain:
    """One row's bracket-run algebra: the prefix-XORs and the staircase.

    A suffix is a run of ``[`` walking right from ``_BASE - 1``, and per row
    it is a walk that pays for what it crosses.  Crossing cell ``i`` flips
    it; when the pre-flip value was 1 the flip lands on 0, so the ``[`` also
    flips cell ``i + 1`` and skips the next instruction.  The carry into
    each cell is therefore the pre-flip value of the cell before it, which
    makes the pre-flip values a prefix-XOR of the standing cells --

        v_i = s_i ^ v_{i-1}        (v at ``_BASE - 1`` is 0)

    -- and the cost of crossing cell ``i`` exactly ``1 + v_i`` instructions.
    Everything the column derivation needs is then three prefix arrays: ``v``
    itself, its own prefix-XOR ``w`` (what a read over fully-crossed ground
    reports), and the staircase ``t`` (instructions to settle each cell),
    whose inverse names the run's extent for any budget.

    Derived from the interpreter's ``_step`` and then checked against it
    rather than trusted: over every ``(separator, settle, bracket count,
    row)`` at two, three and four inputs -- 8120 rows -- the predicted tape,
    pointer and pending skip match the simulated run cell for cell.
    """

    __slots__ = ("l15", "s", "t", "v", "w")

    def __init__(self, cells: list[int]) -> None:
        self.s = cells
        # The one cell below ``_BASE``.
        # insert steps back onto it.
        self.l15 = cells[_BASE - 1]
        v = [0] * _CHAIN_CAP
        w = [0] * _CHAIN_CAP
        t = [0] * _CHAIN_CAP
        for i in range(_BASE, _CHAIN_CAP):
            v[i] = cells[i] ^ v[i - 1]
            w[i] = w[i - 1] ^ v[i]
            t[i] = t[i - 1] + 1 + v[i]
        self.v, self.w, self.t = v, w, t

    def extent(self, budget: int) -> tuple[int, bool]:
        """Extent and pending skip of a pure run of ``budget`` brackets.

        The extent is the staircase's inverse -- the last cell whose
        crossing still fits the budget -- and the skip is pending when the
        budget ran out between a crossing and the skip it owes.

        ``t`` is nondecreasing by construction (``t[i] = t[i-1] + 1 + v[i]``
        with ``v`` a bit), so the walk this used to make is a binary search:
        the loop advanced while ``t[m] < budget``, which lands on the first
        index at or past ``_BASE - 1`` whose staircase reaches the budget,
        clamped to the ceiling the loop stopped at.  Same answer, in C --
        checked against the walk over 279000 ``(chain, budget)`` pairs.
        """
        m = bisect_left(self.t, budget, _BASE - 1, _CHAIN_CAP - 2)
        if m > _CHAIN_CAP - 3:
            m = _CHAIN_CAP - 3
        return m, m >= _BASE and budget < self.t[m]


# What a row does under one.
# read below is arithmetic.
# read); 1 is a pure run plus a.
# complemented chain, which no.
_Plan = tuple[int, int, int, int, int]

# Per orientation: the pool's.
# the per-accumulator partial.
# or None where no pool code.
_Pools = dict[int, tuple[int, int, dict[int, int]] | None]


def _suffix_plan(chain: _Chain, cut: int, rest: int) -> _Plan:
    """Reduce one row's response to ``'[' * cut + '<' + '[' * rest``.

    ``rest == 0`` is a pure run: the ``<`` moves the pointer without
    writing.  Otherwise the run splits into two bracket phases around the
    ``<``, and which of three shapes the row takes turns on the state phase
    one leaves at the boundary:

    * **A pending skip** hands the ``<`` its job: the skip a pure run would
      have spent on the next bracket is spent on the ``<`` instead, so the
      whole suffix is the pure run of ``cut + 1 + rest`` instructions.
    * **No pending skip and the re-crossed cell reads 0** (it held 1 before
      phase one flipped it): the second crossing flips it straight back and
      carries nothing, so the suffix is the pure run of ``cut + rest - 1``
      instructions plus a point flip at that cell.
    * **The re-crossed cell reads 1**: the second crossing carries, and the
      carry cancels phase one's -- every later cell reads ``v_i ^ 1``.  The
      complemented chain has its own staircase, ``t2(m) = 2 + 3 * (m - c)
      - t(m) + t(c)``, and no pure-run equivalent, so it is walked here.

    Which case fires is measured, not assumed: filling the four indexes,
    the pending case fires 63559 times, the flip-back case 68456, the
    complemented chain 67197 and ``rest == 0`` 9588, so every branch is
    exercised by the equality checks in :func:`_staging_index`.
    """
    if rest > 0:
        m1, pending1 = chain.extent(cut)
        if pending1:
            m, _ = chain.extent(cut + 1 + rest)
            return (0, m, ((m - _BASE + 1) & 1) ^ chain.w[m], 0, 0)
        c = m1
        u_c = (1 - chain.v[c]) if c >= _BASE else chain.l15
        if u_c == 0:
            m, _ = chain.extent(cut + rest - 1)
            flip_at = c if c >= _BASE else 0
            return (1, m, ((m - _BASE + 1) & 1) ^ chain.w[m], flip_at, 0)
        t, v, w, s = chain.t, chain.v, chain.w, chain.s
        m2 = c
        while m2 + 1 < _CHAIN_CAP - 2 and 2 + 3 * (m2 - c) - t[m2] + t[c] + 1 <= rest:
            m2 += 1
        head = (((c - _BASE) & 1) ^ w[c - 1]) if c >= _BASE else 0
        lo = max(c + 1, _BASE)
        u_m2 = 1 if m2 == c else 1 - v[m2]
        carry_cell = s[m2 + 1] ^ u_m2
        if m2 == c and c >= _BASE:
            carry_cell ^= v[c]  # phase one already carried v_c.
        x_past = head ^ (w[m2] ^ w[lo - 1]) ^ carry_cell
        return (2, c, m2, head, x_past)
    m, _ = chain.extent(cut)
    return (0, m, ((m - _BASE + 1) & 1) ^ chain.w[m], 0, 0)


def _planned_bit(chain: _Chain, plan: _Plan, acc: int) -> int:
    """One row's XOR of post-suffix cells ``_BASE .. acc``, from its plan.

    The pure shape reads the saturated prefix up to the extent and the
    unsaturated tail past it; the complemented shape has three regions --
    phase one's, the re-crossed run's, and past the phase-two extent, where
    the carry cell joins the standing tail.
    """
    mode = plan[0]
    if mode != 2:
        m, g = plan[1], plan[2]
        sat = ((acc - _BASE + 1) & 1) ^ chain.w[acc]
        x = sat if acc <= m else g ^ chain.v[acc]
        if mode == 1 and plan[3] and acc >= plan[3]:
            x ^= 1
        return x
    _, c, m2, head, x_past = plan
    if acc < c:
        return ((acc - _BASE + 1) & 1) ^ chain.w[acc]
    if acc <= m2:
        lo = max(c + 1, _BASE)
        return head ^ (chain.w[acc] ^ chain.w[lo - 1])
    x = x_past
    if acc >= m2 + 2:
        x ^= chain.v[acc] ^ chain.v[m2 + 1]
    return x


def _planned_bits(chain: _Chain, plan: _Plan, accs: range, const: int = 0) -> list[int]:
    """Return every accumulator's :func:`_planned_bit`, resolved by region.

    The per-accumulator spelling re-decides the plan's shape on every call
    -- 2.9 million times filling the five-input index -- when the region
    boundaries (the extent, the re-crossed cell, the phase-two extent) are
    fixed by the plan and the accumulators are asked in order.  This walks
    the same case analysis once per region instead; the loop body is that
    function's arms verbatim, and ``test_the_batched_planned_bits_match``
    holds the two spellings equal over every plan the staged arities build.

    ``const`` is the caller's slice constant, XORed onto every bit.  Every
    arm below is a XOR chain ending in a term the region fixes, so the
    constant folds into that term rather than costing a second pass over
    the list: :func:`_closed_sweeps` used to build the row's bits and then
    rebuild them XORed, 77720 lists an 18-table build.  ``const == 0``
    recovers the plain :func:`_planned_bit` exactly, which is the default
    and what the equality test compares against.
    """
    w, v = chain.w, chain.v
    mode = plan[0]
    # The saturated arm's parity.
    # the constant to the offset.
    # which is exactly XORing it,.
    par = 1 - _BASE + const
    if mode != 2:
        m, g = plan[1], plan[2]
        gc = g ^ const
        out = [
            (((acc + par) & 1) ^ w[acc]) if acc <= m else (gc ^ v[acc]) for acc in accs
        ]
        if mode == 1 and plan[3]:
            for i in range(max(plan[3] - accs.start, 0), len(out)):
                out[i] ^= 1
        return out
    _, c, m2, head, x_past = plan
    hb = head ^ w[max(c + 1, _BASE) - 1] ^ const
    tail = x_past ^ v[m2 + 1] ^ const
    xc = x_past ^ const
    out = []
    for acc in accs:
        if acc < c:
            out.append(((acc + par) & 1) ^ w[acc])
        elif acc <= m2:
            out.append(hb ^ w[acc])
        elif acc >= m2 + 2:
            out.append(tail ^ v[acc])
        else:
            out.append(xc)
    return out


def _slice_chains(n: int, sep_index: int, settle: int) -> tuple[list[_Chain], _Pools]:
    """One slice's row chains and per-orientation pool facts.

    The pool is resolved **once per slice and orientation**, not once per
    suffix, and three measured facts make that sound: a suffix never writes
    below cell ``_BASE - 1`` (its brackets start there and only walk right),
    the embed leaves every cell below ``_BASE`` identical across rows (0
    violations over every slice at two, three and four inputs), and a pool
    code never reaches past cell 6 from its clamped start -- so nothing a
    suffix does can change what :func:`_find_pool` sees, and nothing the
    rows disagree on can reach it.  The facts are also why the sweep's low
    span is a constant: cells below ``_BASE`` contribute the same XOR to
    every row's column, precomputed here per accumulator.
    """
    base = _embed(n, settle=settle, sep=_SEPS[sep_index])
    _clamp(base)
    _walk_to(base, _BASE - 1)
    chains = [_Chain([(m.tape >> i) & 1 for i in range(_CHAIN_CAP)]) for m in base.ms]
    if len({tuple(c.s[:_BASE]) for c in chains}) != 1:
        # The whole slice-constant.
        # violation is a bug in the.
        # Measured over every slice at.
        # violations, which is why the.
        # stays because the property.
        # this function establishes.
        raise AssertionError(  # pragma: no cover - the embed is row-constant
            "embed left a row-dependent cell below _BASE"
        )
    pools: _Pools = {}
    for cell7 in (0, 1):
        staged = base.fork()
        staged.emit("<")
        _clamp(staged)
        code = _find_pool(staged, cell7, 8)
        if code is None:
            pools[cell7] = None
            continue
        probe = staged.fork()
        probe.emit(code)
        cur = probe.ms[0].ptr
        post = [(probe.ms[0].tape >> i) & 1 for i in range(_BASE)]
        lowxor: dict[int, int] = {}
        running = 0
        for i in range(cur + 1, _BASE):
            running ^= post[i]
            if i >= _PROBE_WALK_OUT:
                lowxor[i] = running
        pools[cell7] = (cur, running, lowxor)
    return chains, pools


def _closed_sweeps(
    chains: list[_Chain],
    pools: _Pools,
    suffix: int | str,
) -> dict[int, dict[int, tuple[int, ...]]]:
    """Both orientations' accumulator sweeps for one suffix, derived.

    The same mapping :func:`_column_sweep` builds by emitting the pool code
    and walking, produced arithmetically instead.  The walk-out law is what
    joins the pieces: a ``[x`` walk carries each crossed cell's pre-flip
    value into the next, so the cell the read reports at ``acc`` is the XOR
    of the standing cells from ``cur + 1`` through ``acc`` -- the slice's
    low constant, then each row's :func:`_planned_bit`.  A ``cut == 0``
    insert flips cell ``_BASE - 1`` on its way past, which is the one
    suffix-dependent bit below ``_BASE``; it is row-independent, so it
    lands as a constant too.

    Checked against the emit-and-walk sweep over the *entire* enumeration
    at two, three and four inputs -- 10440 ``(staging, orientation)``
    sweeps across both suffix families -- with no disagreement, on top of
    the whole-index equality recorded at :func:`_staging_index`.
    """
    if isinstance(suffix, int):
        cut, rest = suffix, 0
        lflip = 0
    else:
        cut = suffix.index("<")
        rest = len(suffix) - cut - 1
        lflip = 1 if cut == 0 and rest > 0 else 0
    # The plans are the suffix's.
    # share, but only one.
    # ``cell7 == 1`` with None at.
    # 40, measured), so the region.
    # and hoisting it out of the.
    plans = [_suffix_plan(chain, cut, rest) for chain in chains]
    sweeps: dict[int, dict[int, tuple[int, ...]]] = {}
    for cell7 in (0, 1):
        facts = pools[cell7]
        if facts is None:
            sweeps[cell7] = {}
            continue
        cur, lowfull, lowxor = facts
        columns: dict[int, tuple[int, ...]] = {}
        for acc in range(_PROBE_WALK_OUT, _BASE):
            if acc - 1 < cur:
                # Mirrors _column_sweep's.
                # below the accumulator range,.
                continue  # pragma: no cover - the pool lands below the range
            bit = lowxor[acc] ^ (lflip if acc == _BASE - 1 else 0)
            columns[acc] = (bit,) * len(chains)
        # The accumulators at ``_BASE``.
        # per row rather than one plan.
        # the row-major bits transposed.
        accs = range(_BASE, _MAX_ACC + 1)
        const = lowfull ^ lflip
        rowbits = [
            _planned_bits(chain, plan, accs, const)
            for chain, plan in zip(chains, plans, strict=True)
        ]
        for acc, column in zip(accs, zip(*rowbits, strict=True), strict=True):
            columns[acc] = column
        sweeps[cell7] = columns
    return sweeps


@cache
def _staging_index(n: int) -> dict[tuple[int, ...], _Staging]:
    """Map every column the stagings reach to the staging that prints it.

    The inverse of the enumeration, tabulated once per arity.  **This is
    the oracle spelling now, not the build path**: :func:`_derive_staging`
    assigns through :func:`_first_staging`'s constraint intersection, and
    the tests hold the two equal key for key -- on top of the standing
    index-vs-:func:`_derived_plans` checks, so all three spellings of the
    one order keep pinning each other.

    **The columns are derived, not observed.**  This used to run the
    interpreter for every staging -- fork the embed, emit the pool code,
    walk to each accumulator -- and that walk was the shipped build's
    dominant cost, 63.8M ``_Sim`` steps and 25.6s of a 38.4s five-input
    build.  Every step of it is now arithmetic: the suffix is the bracket
    staircase (:class:`_Chain`), the pool is a slice constant
    (:func:`_slice_chains`), and the walk out is the prefix-XOR the walk-out
    law names (:func:`_closed_sweeps`).  What survives of the old cost is
    ten embeds and twenty pool probes per arity.  Measured cold: 6.5s to
    0.62s at four inputs, 31.5s to 1.12s at five.

    An earlier note here recorded that the printed column "does not reduce
    to a closed form in ``(suffix, accumulator)``" -- three translation
    hypotheses failed against the measured grid, because the pool code
    depends on the state the staging leaves behind.  Both halves were right
    and the conclusion still wasn't: the column is not a *translation* in
    ``(suffix, accumulator)``, but it is closed-form in the embed's
    standing columns, and the pool state-dependence dissolves once the
    state it depends on is proved slice-constant.

    **The order is the contract.**  A table takes the *first* staging that
    prints it, so this fills each column once, walking the enumeration in
    exactly :func:`_stagings` order -- both passes, pure bracket runs across
    every slice before any insert suffix, and the same budget accounting.
    Interleaving the passes per slice instead produces columns that are all
    reachable and all valid, and still assigns five-input XOR ``None`` where
    the enumeration assigns ``(2, 0, 0, 33)``.  That is why the test for this
    compares staging *tuples* against :func:`_derived_plans` rather than
    checking that the programs work -- and why the closed form was accepted
    only on whole-index equality: at every staged arity, the index it fills
    equals the emit-and-walk index key for key and staging for staging
    (16, 252, 15994 and 28096 entries), on top of the standing
    index-vs-oracle tests.
    """
    index: dict[tuple[int, ...], _Staging] = {}
    spent = 0
    budget = _budget(n)
    accs = _MAX_ACC - _POOL_WIDTH

    def exhausted() -> bool:
        return budget is not None and spent >= budget

    def claim(
        sweeps: dict[int, dict[int, tuple[int, ...]]],
        suffix: int | str,
        head: tuple[int, int],
    ) -> None:
        for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
            for cell7 in (0, 1):
                derived = sweeps[cell7].get(acc)
                if derived is None:
                    continue
                for read in _READS:
                    column = derived if read == _READS[1] else _complement(derived)
                    if column not in index:
                        index[column] = (*head, suffix, acc)

    # The slice states are built.
    # pass reads the same embeds,.
    states: dict[tuple[int, int], tuple[list[_Chain], _Pools]] = {}

    slices = _slices(n)
    for sep_index, settle in slices:
        if exhausted():
            return index
        states[sep_index, settle] = _slice_chains(n, sep_index, settle)
        chains, pools = states[sep_index, settle]
        for brackets in range(_MAX_BRACKETS + 1):
            claim(
                _closed_sweeps(chains, pools, brackets),
                brackets,
                (sep_index, settle),
            )
            spent += accs
            if exhausted():
                return index

    if n not in _INSERT_ARITIES:
        return index
    for sep_index, settle in slices:
        # Never taken, for the same.
        # loop: the spend inside the.
        # `exhausted()` return, so.
        if exhausted():
            return index  # pragma: no cover - see _derived_plans
        chains, pools = states[sep_index, settle]
        for suffix in _insert_suffixes():
            claim(
                _closed_sweeps(chains, pools, suffix),
                suffix,
                (sep_index, settle),
            )
            spent += accs
            if exhausted():
                return index
    return index


# One pass's constraint masks.
# suffixes whose sweep reaches.
# under which the row's printed.
_RowMasks = dict[tuple[int, int], tuple[int, tuple[int, ...]]]


@cache
def _row_constraints(n: int) -> dict[tuple[int, int], dict[str, _RowMasks]]:
    """Tabulate, per slice, what every staging does to every row.

    The same walk :func:`_staging_index` makes, transposed: instead of
    filing each staging's finished column under first-claim-wins, this
    records per-row *facts* -- bit ``s`` of a row's mask says the slice's
    suffix ``s`` leaves that row's printed bit at 1 for the direct read at
    that ``(orientation, accumulator)``.  The assignment then stops being a
    property of dict insertion order and becomes the rule
    :func:`_first_staging` states: a table's staging is the first one, in
    enumeration order, that every row's constraint admits.

    The enumeration does not disappear -- it produces row facts instead of
    final answers, and it cannot do less: the 4640 stagings collapse to
    only ~4190 distinct behaviours (the density note above
    :data:`_STAGED_ARITIES`), so anything that answers arbitrary tables
    carries index-equivalent information.  What changes is what the
    tabulated object *means*.  A mask bit is one row's behaviour under one
    staging -- checkable against a single :class:`_Chain` walk -- where an
    index entry is only "the answer", explainable by nothing short of
    replaying the whole claim order.

    Budget-independent, unlike the index: the budget caps which stagings a
    *query* may consult, so it is applied as a mask prefix in
    :func:`_first_staging` rather than baked into the tabulation.
    """
    rows = 2**n
    inserts: tuple[int | str, ...] = _INSERT_SUFFIXES if n in _INSERT_ARITIES else ()
    pures: tuple[int | str, ...] = tuple(range(_MAX_BRACKETS + 1))
    out: dict[tuple[int, int], dict[str, _RowMasks]] = {}
    for sep_index, settle in _slices(n):
        chains, pools = _slice_chains(n, sep_index, settle)
        per: dict[str, _RowMasks] = {}
        for name, suffixes in (("pure", pures), ("insert", inserts)):
            building: dict[tuple[int, int], tuple[int, list[int]]] = {}
            for ordinal, suffix in enumerate(suffixes):
                bit = 1 << ordinal
                sweeps = _closed_sweeps(chains, pools, suffix)
                for cell7 in (0, 1):
                    for acc, column in sweeps[cell7].items():
                        entry = building.get((cell7, acc))
                        if entry is None:
                            entry = building[cell7, acc] = (0, [0] * rows)
                        present, rowmasks = entry
                        building[cell7, acc] = (present | bit, rowmasks)
                        for row, value in enumerate(column):
                            if value:
                                rowmasks[row] |= bit
            per[name] = {
                key: (present, tuple(rowmasks))
                for key, (present, rowmasks) in building.items()
            }
        out[sep_index, settle] = per
    return out


def _first_staging(truth_table: str, n: int) -> _Staging | None:
    """Return the first staging, in enumeration order, printing the table.

    **The order is the contract, and it is stated here once**: the pure
    bracket runs across every slice, then the insert family across every
    slice -- interleaving the passes still yields valid stagings and
    assigns five-input XOR the wrong one -- and within a slice the
    comparison key ``(suffix, accumulator, orientation, read)``, which is
    exactly :func:`_staging_index`'s claim order.  What used to be implicit
    in dict insertion is the ``min`` below.

    The rule itself is one sentence.  A row admits the suffixes whose
    printed bit matches its wanted bit -- its constraint mask directly for
    the direct read, complemented for the complementing one -- so the
    stagings that print the table are the AND of the rows' masks, and the
    winner is the lowest set bit.  Where no bit survives the AND, no
    staging at this slice and accumulator prints the table, which is the
    miss the caller falls through on.

    The budget caps how many stagings may be consulted.  It is counted in
    claims of ``_MAX_ACC - _POOL_WIDTH`` accumulators each, exactly as the
    index's walk spends it, so the cap in suffixes is the ceiling division,
    laid over the passes in the same global order.
    """
    want = [int(c) for c in truth_table]
    budget = _budget(n)
    allowed: int | None = None
    if budget is not None:
        allowed = 0 if budget <= 0 else -(-budget // (_MAX_ACC - _POOL_WIDTH))
    slices = _slices(n)
    inserts = _INSERT_SUFFIXES if n in _INSERT_ARITIES else ()
    constraints = _row_constraints(n)
    passes = (
        ("pure", _MAX_BRACKETS + 1, 0),
        ("insert", len(inserts), len(slices) * (_MAX_BRACKETS + 1)),
    )
    for name, count, done in passes:
        if count == 0:
            continue
        for position, slot in enumerate(slices):
            cap = count
            if allowed is not None:
                cap = min(count, max(0, allowed - done - position * count))
                if cap == 0:
                    break
            capmask = (1 << cap) - 1
            masks = constraints[slot][name]
            best: tuple[int, int, int, int] | None = None
            for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
                for cell7 in (0, 1):
                    entry = masks.get((cell7, acc))
                    if entry is None:
                        continue
                    present, rowmasks = entry
                    for read_index, read in enumerate(_READS):
                        direct = read == _READS[1]
                        admissible = present & capmask
                        for rowmask, target in zip(rowmasks, want, strict=True):
                            wanted = target if direct else 1 - target
                            admissible &= rowmask if wanted else ~rowmask
                            if not admissible:
                                break
                        if admissible:
                            lowest = (admissible & -admissible).bit_length() - 1
                            candidate = (lowest, acc, cell7, read_index)
                            if best is None or candidate < best:
                                best = candidate
            if best is not None:
                ordinal, acc, _cell7, _read_index = best
                suffix: int | str = ordinal if name == "pure" else inserts[ordinal]
                return (*slot, suffix, acc)
    return None


def _derive_staging(truth_table: str, n: int) -> _Staging | None:
    """Return the staging that builds ``truth_table``, or None if none does.

    :func:`_first_staging` answers from the tabulated row constraints --
    the enumeration order is still the whole specification, it decides
    which program a truth table gets, but the assignment is now the stated
    intersection rule rather than a finished-answer dictionary.
    :func:`_staging_index` keeps the dictionary spelling as the oracle the
    tests hold this to, key for key.

    The cost trade, measured: the first staged table at an arity pays the
    tabulation (0.45s at four inputs, 0.9s at five, about a tenth over the
    index fill it replaced) and each table after it costs ~0.6ms of mask
    intersection where the dict hit was ~1us -- the price of an assignment
    that reads as a rule, and small beside the ~10ms replay below.

    Nothing is returned on the strength of the algebra alone.  The
    enumeration used to run :func:`_confirm` on each column it claimed;
    confirming all of them would mean an endgame per reachable column
    (15994 of them at four inputs) for the few a process actually asks
    about, so the check rides on the answer instead -- the plan handed back
    is the one that gets confirmed, the same standard applied to exactly
    the plans that are used.  A plan that fails it is reported as a miss,
    so the caller falls through to :func:`_mux` rather than receiving a
    program that does not print.
    """
    if n not in _STAGED_ARITIES:
        return None
    plan = _first_staging(truth_table, n)
    if plan is None:
        return None
    return plan if _replay(truth_table, n, plan) is not None else None


# **The flipped-embed pass was.
# inputs as they landed, which.
# gain at the time, and dead.
# plain enumeration missed, and.
# exhaustively, not sampled),.
# does not reach.
# four inputs alone, which the.
# .
# What it cost was the.
# by the first four-input table.
# the same table through.
# minutes to the sculpted.
# .
# The trade is program length:.
# the tables it placed, and.
# ones.
# compute -- and paid only by.
# .
# The route trades longer.


def _staged(truth_table: str, n: int) -> str | None:
    """Build from a derived staging without searching, or None if there is none.

    None rather than an exception on a miss, so the caller falls through to
    :func:`_mux` and coverage cannot regress.

    A miss falls through to :func:`_mux`, which closes four inputs.  The
    flipped-embed pass that used to sit here was removed once that route was
    shown to build every table it placed; see the note above
    :data:`_MUX_BASE`.
    """
    plan = _derive_staging(truth_table, n)
    if plan is not None:
        return _replay(truth_table, n, plan)
    return _mux(truth_table, n)


# ------------------------------.
# The sculpted route: separate.
# fix the printed column one.
# .
# This is the construction that.
# each input **exactly once**.
# generator holds to (see.
# The observation it stands on.
# identity on the tape:.
# so after the embed no two.
# state difference into a.
# there, never another copy of.
# .
# **Separation** is that.
# ``n``, no search anywhere.
# ends holding the row's binary.
# .
# for i in range(n):.
# setter(i);.
# .
# :func:`_mux_weight` is what.
# restoring read ``[x<[<``.
# can be read again; ``k`` of.
# exactly ``-k`` times the bit.
# pointer therefore lands at.
# in the inputs and injective.
# separated by construction,.
# row by row.
# .
# Two conditions make the.
# rather than by argument:.
# .
# * the bit must be **fresh**.
# folds the bit into the.
# to 1 -- which is exactly what.
# read as a wall.
# arbitrary rightward padding.
# * gadgets must not reach into.
# ``k - 3`` cells left of its.
# clear air plus the room the.
# threshold ``2**(n-2) - 1`` is.
# exactly right and the misses.
# .
# This replaces four searches.
# reads, a beam over aimed-read.
# colliding pair).
# failed outright at five after.
# four and 0.004s at five.
# .
# It also corrects what this.
# lands does not help and.
# setter-read unit is.
# has crossed the bit.
# construction.
# .
# **Sculpting** then edits the.
# cell ``C`` below every row.
# ``K = b - C + 1`` has three.
# .
# * the row at position ``b``.
# ``C`` -- an *unconditional*.
# is clean whatever that row's.
# * a row above ``b`` starts.
# its own rewind point, so its.
# the value the endgame will.
# * rows below ``b`` cross.
# cascade debris from crossing.
# .
# So repeatedly fixing the.
# frontier, and the loop lands.
# the one non-structural.
# where a state-driven switch.
# through the walkout -- is now.
# at every round, so the code.
# :data:`_SCULPT_POOL_CODE`.
# fall-through anyway, because.
# "a stall returns None" true.
# the ``_FLIP`` lesson again: a.
# skip flag set, and the next.
# to lose.
# .
# **Coverage and cost,.
# families miss build through.
# the shipped interpreter, at.
# in name order -- which closes.
# separation, which used to be.
# construction.
# .
# **A build costs about 220ms.
# cost 7ms by returning the.
# it now sculpts all of them.
# sets the price of every round.
# rewind of ``K = frontier - C.
# Measured over sampled.
# first-descending 700, minimum.
# takes XOR5 from 2511.
# extra work back (a hint.
# at the fixed probe distance.
# both are verified to leave.
# .
# **The arity gate is gone.
# absent because no derivation.
# seconds and failed, always.
# The constructed separation.
# route was never.
# replaced the tuple with.
# construction is aware of.
# argument: every one of the.
# ``n``.
# to end: 200.
# of 200 fully-essential.
# correctly on the shipped.
# 0.14s each.
# the same way: the two tables.
# and 3993 characters in 41.6s.
# prints all 64 rows on the.
# :meth:`test_no_arity_is_gated`.
# wider run,.
# 448 of 448 rows correct at.
# .
# The route sits *after* the.
# table they already build.
# route: the searches that used.
# cannot build -- a pool code.
# raises rather than sweeping.

# Where the sculpted route.
# separation searches must not.
# the uniform wake ``_walk_to``.
# fourteen, so a separation.
# measured, 0 usable pool.
# cells between the guard and.
# scratch there is what lets.
# four-input separation from a.
_MUX_BASE = _BASE + 16
_MUX_GUARD = _MUX_BASE - 8

# The lowest arity the route is.
# to be a tuple ``(2, 3, 4,.
# *verified*, and the route.
# gate, not a construction that.
# ``_mux``.
# total?") now closes all six.
# that carry no residual ``n``:.
# constant 24-cell saturation.
# weights give, the rewind.
# window geometry, and the pool.
# freezes to one value at every.
# the generator partial, and it.
# .
# Two is the floor because.
# projections to.
# itself has no arity-specific.
_MUX_MIN_ARITY = 2

# One derived separation per.
# rather than ``lru_cache``.
_MUX_SEPARATED: dict[int, _Joint] = {}


def _mux_reference(n: int) -> _Joint:
    """Return a joint walked to the embed's start with nothing embedded yet.

    What :func:`_mux_separate`'s guard check compares against: the walk-in is
    common to every row, so this is the tape the construction must leave
    untouched left of :data:`_MUX_GUARD`.
    """
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    """Whether every cell left of the guard survived, on every row."""
    return all(
        m.cells(_MUX_GUARD) == m0.cells(_MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_weight(k: int) -> str:
    """Return the gadget displacing a **fresh** setter bit by exactly ``-k``.

    A single restoring read ``[x<[<`` moves the pointer by the bit's value and
    puts the cell back, so the bit can be read again; rewinding one cell
    between such reads compounds them, and ``k`` of them displace by ``k``
    times the bit.  Measured linear for ``k`` of 1 to 8, with no row dying.

    *Fresh* is required and is the reason an earlier attempt at
    per-setter weighting read 1 for every weight: a single ``[x`` between the
    setter and this gadget folds the bit into the running prefix-XOR, and the
    reads then see the walk's wake rather than the bit.  Emit this directly
    after :meth:`_Joint.emit_setter`, never after a walk.

    The gadget writes at most ``max(0, k - 3)`` cells left of the setter
    (measured over the same range), which is what :func:`_mux_separate`'s pad
    is sized against.
    """
    return ("[x<[<" + "<") * (k - 1) + "[x<[<" if k > 0 else ""


def _mux_weights(n: int) -> tuple[int, ...]:
    """Return the per-input weights: ``2**(n-1-i)``, so the sum is the row."""
    return tuple(2 ** (n - 1 - i) for i in range(n))


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight.

    A gadget of weight ``k`` reaches ``k - 3`` cells left of its setter, so
    the pad has to clear that much *and* keep the deepest rewind above cell
    0.  ``2**(n-2) - 1`` is where the second condition binds and is sharp:
    at four inputs pads 1 and 2 separate 14 of 16 and pad 3 separates all 16;
    at five, pads 1 to 6 reach 21 to 30 of 32 and pad 7 closes it.  Below the
    threshold the weights are still exactly right -- the misses are rows
    whose leading bits clamp at the tape's floor, not a weighting error.

    The shift spells the power rather than ``2 **``, which mypy widens to
    ``Any`` because a negative exponent would make it a float; the arities
    here are always at least two, so the shift is the honest spelling.
    """
    return max((1 << (n - 2)) - 1, 1)


def _mux_start(n: int) -> int:
    """Return where to lay the embed so no gadget writes left of the guard.

    The leftmost write is the first gadget's, and it is the heaviest.  The
    setter lays its bit at the start cell itself, and a weight-``k`` gadget
    then reaches ``k - 2`` cells left of that -- measured directly, and note
    it is ``k - 2`` from the *bit* where the module's older prose says
    ``k - 3``; the two differ by where they count from, not in the geometry.
    With ``start = _MUX_BASE + 2**(n-1) - offset`` and ``k = 2**(n-1)``, the
    ``2**(n-1)`` cancels:

        leftmost write = start - k + 2 = _MUX_BASE - offset + 2

    which does not depend on ``n`` at all -- it is 25 at every arity.  Asking
    that it clear :data:`_MUX_GUARD` by one gives

        offset = _MUX_BASE - _MUX_GUARD + 1

    the expression below, and 9 as shipped.

    **The offset is derived rather than written down, because it is pinned
    rather than chosen.**  It used to be the literal ``9``, which read as a
    tuning; it is not.  Every offset builds and larger ones are shorter --
    measured at five inputs, a mean template of 1443, 1431, 1419, 1407, 1395
    and 1383 characters for offsets 3 through 13 -- so nothing about *length*
    stops the count rising.  What stops it is the guard: the leftmost write
    tracks the offset cell for cell and lands on :data:`_MUX_GUARD` exactly
    here, so one more takes it to cell 22 and :func:`_mux_intact` fails, at
    five and six inputs alike.  The separation still separates there; only
    the guard catches it.  So this is the *shortest legal* start, and moving
    :data:`_MUX_GUARD` should move it too -- which is what spelling it this
    way buys.

    The offset applies only once the first gadget outgrows it, so it is
    nothing at two, three and four inputs -- they already clear the guard --
    and 7 and 23 cells at five and six.
    """
    return _MUX_BASE + max(0, (1 << (n - 1)) - (_MUX_BASE - _MUX_GUARD + 1))


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers.

    Constructed rather than searched.  Each input is weighted as it lands --
    setter, then :func:`_mux_weight` on the still-fresh bit, then a pad wide
    enough that the next gadget starts outside this one's damage -- so the
    pointer ends at ``c0 - sum(2**(n-1-i) * x_i)``.  That is affine in the
    inputs with the binary weights, hence injective, so the rows are
    separated by construction and there is nothing to search for.

    Table-independent, so it is built once per arity and cached; callers get
    a fork.  The return type keeps the ``None`` case the searches needed, so
    :func:`_mux` is unchanged, but the construction does not fail: the
    verification below is what the arity gate now rests on.

    **No right-pad is emitted, because the weighting cannot need one.**  The
    sculpting rounds want ``min(ptrs)`` to stand clear of the span, and the
    lowest pointer is

        min(q) = start + (n-1) * (pad + 1) - 1

    against a span of ``2**n - 1``.  With ``pad + 1 = 2**(n-2)`` the leading
    term is ``(n-1) * 2**(n-2)``, which passes ``2**n`` at five inputs and
    then runs away from it -- the difference is ``2**(n-2) * (n-5)`` -- so the
    clearance is never tight: it is 30, 28, 28, 39, 71, 151 cells at two
    through seven inputs and grows from there.  A right-pad guarding that
    gap used to sit here and could not fire at any arity.
    """
    if n in _MUX_SEPARATED:
        return _MUX_SEPARATED[n].fork()
    weights = _mux_weights(n)
    pad = _mux_pad(n)
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    for i, k in enumerate(weights):
        j.emit_setter(i)
        j.emit_weight(_mux_weight(k), k)
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # The construction is derived,.
    # cached: a separation that.
    # sculpting loop as an.
    # .
    # Neither check fires at any.
    # separation rather than.
    # `n` in.
    # both refusals are the guard.
    # construction, not a live path.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None  # pragma: no cover - the separation never refuses
    if not _mux_intact(_mux_reference(n), j):
        return None  # pragma: no cover - the separation never refuses
    _MUX_SEPARATED[n] = j.fork()
    return j


# : Which pool code a.
# :.
# : The scan this replaces was.
# : by the construction, in.
# :.
# : * **The probe state is.
# : absorb a pending skip and.
# : writes -- so every probe,.
# : rows whose pointers are all.
# : pool region is ``(0, 1, 1,.
# : ``cell7``: exhaustive at.
# : sampled at four and 12 at.
# : are the two values of.
# : * **Nothing outside the.
# : from that state touches at.
# : verdict reads, so the.
# : * **A sculpt cannot disturb.
# : guard ``rewind > min(ptrs).
# : region, and the next round.
# :.
# : So the answer is a constant.
# : property of the table: the.
# : accumulator and every.
# : is what the ``hint``.
# : switches" -- the hint never.
# :.
# : **What this is worth,.
# : entry that opened this.
# : build" as the cost of the.
# : :func:`_mux_probe`, and the.
# : already skipped the list on.
# : takes a warm five-input.
# : when that landed,.
# : left came from.
# : gone now that the.
# : :func:`_pool_reaches` runs.
# : tests -- never on a build's.
# : :func:`_mux_probe` is the.
# : every row, once a round --.
# : to use and is not closed by.
# :.
# : So the value here is the.
# : what remains is arithmetic.
# :.
# : This is the sculpting probe.
# : general rule rather than.
# : same question of the.
# : state, and answers it by.
# : constant stays because the.
# : naming the code costs.
_SCULPT_POOL_CODE = _POOL_CODES[4]


def _sculpt_pool_code(cell7: int) -> str | None:
    """Return the code a sculpting probe reaches, by :data:`_SCULPT_POOL_CODE`.

    ``test_sculpt_pool_code_matches_scan`` replays the replaced scan as the
    specification oracle, so the constant is checked against
    :func:`_pool_reaches` rather than trusted.
    """
    return _SCULPT_POOL_CODE if cell7 == 0 else None


@cache
def _probe_frame(code: str, byte: int) -> tuple[int, int] | None:
    """Return ``(landed, parity)`` for ``code`` run from a converged row.

    ``landed`` is where the code leaves the pointer and ``parity`` is the
    XOR of the pool-region cells it leaves between there and cell 7 -- the
    two constants the closed-form probe column reads.  Derived by running
    the code on the simulator from ``(byte, pointer 0, no skip)``, twice
    with different junk above the pool region; None when the two runs
    disagree or either leaves the region written, a skip pending, the row
    dead, or the pointer past the region -- states the summary cannot speak
    for, which send the caller back to simulation.
    """
    frames = []
    for high in (0, (1 << 64) - 1):
        sim = _Sim(_POOL_WIDTH + _PROBE_WALK_OUT + 4)
        sim.tape = byte | (high << _POOL_WIDTH)
        sim.apply(_runs(code))
        if sim.dead or sim.skip or sim.ptr >= _POOL_WIDTH:
            return None
        if sim.tape >> _POOL_WIDTH != high:
            return None
        frames.append((sim.ptr, sim.tape & _POOL_MASK))
    if frames[0] != frames[1]:  # pragma: no cover - no code both reads and frames
        # The two fills differ only.
        # whose low result *reads* what.
        # write is the guard above.
        # through length 8 from four.
        # covered) and no reader, so.
        # reachable refusal: it keeps.
        return None
    landed, low = frames[0]
    return landed, (low >> (landed + 1)).bit_count() & 1


def _sculpt_columns(j: _Joint, acc: int) -> tuple[int, ...] | None:
    """Return the probe column by the parity law, or None to fall back.

    The probe's forked walk is affine: after the pool code, the cell at
    ``acc`` is the prefix-XOR carry over everything the walk crossed, so a
    row's answer is the frame's parity XOR the parity of its own cells
    ``8..acc``.  Valid only while every row is alive and shares the frame's
    window byte -- the clamp converges the pointers and the probe's ``x``
    eats a pending skip, so neither enters the key.  A row outside that
    summary returns None and the caller simulates instead.
    """
    if acc <= _POOL_WIDTH:
        return None
    ms = j.ms
    byte = ms[0].tape & _POOL_MASK
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:
        return None
    parity = frame[1]
    mask = ((1 << (acc + 1)) - 1) ^ _POOL_MASK
    column = []
    for m in ms:
        if m.dead or (m.tape & _POOL_MASK) != byte:
            return None
        column.append(parity ^ ((m.tape & mask).bit_count() & 1))
    return tuple(column)


def _mux_probe_sim(
    j: _Joint, acc: int, cell7: int
) -> tuple[tuple[int, ...], str] | None:
    """Run the probe by simulation: fork, absorb, clamp, set the pool, walk.

    The specification :func:`_mux_probe`'s parity law is held to -- the
    scout checks the two agree live, once per build -- and the fallback for
    states :func:`_sculpt_columns` refuses to summarise.
    """
    probe = j.fork()
    probe.emit("x")  # absorb a pending skip so the.
    _clamp(probe)
    code = _sculpt_pool_code(cell7)
    if code is None:
        return None
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed; as _printed_column
        # Same shape, and same caveat,.
        # pool code that fits the site.
        # because `_find_pool` ignores.
        # sculpting rounds at two and.
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1)), code


def _mux_probe(
    j: _Joint, acc: int, cell7: int, hint: str | None = None
) -> tuple[tuple[int, ...], str] | None:
    """Return the column printed at ``acc`` and the pool code that got it.

    The code is not searched for.  :data:`_SCULPT_POOL_CODE` names it: the
    probe state here is canonical (the ``x`` and the clamp put every row at
    pointer 0 with the same pool region), so the verdict is a constant of
    the construction.  See that constant for the derivation and the
    measurements behind it.  ``hint`` carried the previous round's winner
    when this was a scan; it is accepted and ignored because the value
    cannot change between rounds, and callers still pass it because
    :func:`_mux` reads the code back out of the return.

    The column is not walked for either.  The probe's fork was pure
    arithmetic -- clamp and walk never depend on anything but the row's
    cells 8..acc once the pool region is uniform -- so
    :func:`_sculpt_columns` computes it by the parity law, one popcount per
    row, and :func:`_mux_probe_sim` remains as the specification and the
    fallback for any state the law's frame refuses.  The two are compared
    live once per build by the scout, on top of the differential tests that
    pin the laws themselves.
    """
    del hint
    code = _sculpt_pool_code(cell7)
    if code is None:
        return None
    column = _sculpt_columns(j, acc)
    if column is None:
        return _mux_probe_sim(j, acc, cell7)
    return column, code


def _mux_sculpt(
    base: _Joint,
    truth_table: str,
    n: int,
    acc: int,
    cell7: int,
    *,
    direct: bool,
    hint: str | None = None,
) -> str | None:
    """Sculpt the printed column at one ``(C, orientation, read)``.

    Derive the column the endgame would print, take the highest-positioned
    row that disagrees, flip its cell ``C`` with one clean round, repeat.
    The frontier argument in the section comment bounds the loop; the cap is
    that bound plus a small allowance, and a stall returns None rather than
    looping.  The allowance was for a pool-code switch, which
    :data:`_SCULPT_POOL_CODE` has since ruled out -- it is kept as slack
    because the cap's job is to make the fall-through true, not to be tight.
    The finished joint is handed to :func:`_try_print`, so what is returned
    was seen to print the table.
    """
    want = tuple(int(c) for c in truth_table)
    j = base.fork()
    for _ in range(2**n + 4):
        found = _mux_probe(j, acc, cell7, hint)
        if found is None:
            return None
        column, hint = found
        got = column if direct else _complement(column)
        disagree = [p for p, g, w in zip(j.ptrs(), got, want, strict=True) if g != w]
        if not disagree:
            break
        frontier = max(disagree)
        rewind = frontier - acc + 1
        if rewind > min(j.ptrs()) - _POOL_WIDTH:
            # Not observed, but the closest.
            # every table at two and three.
            # margin (bound minus rewind).
            # `_mux_separate` leaves is.
            # nothing about the.
            # This is the guard a change to.
            return None  # pragma: no cover - not observed; margin reaches 0
        # Emitted as three runs rather.
        # template is.
        # unchanged -- but a mixed.
        # the loop's hot path: split,.
        # `_Sim.run_left` and.
        # character at a time per row.
        j.emit("<" * rewind)
        j.emit("[x" * rewind)
        j.emit("x")
    else:
        # The loop runs `2**n + 4`.
        # frontier row, so a table that.
        # would be one where a round.
        # over every table at two and.
        # returns None rather than.
        return None  # pragma: no cover - the separation never refuses
    j.emit("x")
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return None if hit is None else hit.template()


# Bit-reversal per byte, for.
_REV_BYTE = bytes(int(f"{value:08b}"[::-1], 2) for value in range(256))


def _rev_bits(value: int, width: int) -> int:
    """Return the low ``width`` bits of ``value``, reversed.

    Byte-reversed via the table, then shifted down by the padding: cheap
    enough to reverse every row's tape once per build.
    """
    size = (width + 7) // 8
    low = value & ((1 << width) - 1)
    full = int.from_bytes(low.to_bytes(size, "little").translate(_REV_BYTE), "big")
    return full >> (size * 8 - width)


def _mux_scout(
    base: _Joint,
    truth_table: str,
    n: int,
    accs: range,
    rewinds_out: dict[tuple[int, bool], list[int]] | None = None,
) -> tuple[tuple[int, bool, int] | None, bool]:
    """Price every ``(accumulator, orientation)`` sculpt without emitting.

    Returns ``(winner, trusted)``.  The winner is ``(acc, direct, length)``
    for the combination :func:`_mux_sweep` would keep -- the shortest build,
    first in sweep order on a tie -- or None when every combination fails.
    ``trusted`` False means the base defeats the shadow's summary and the
    caller must run the sweep itself.

    The shadow replays the sculpt loop in closed form.  The pointers never
    move between rounds -- a round's ``<`` and ``[x`` runs are a round trip
    -- so each row is its tape alone, the probe column is the parity law
    :func:`_sculpt_columns` states, and a round is the walk law applied to
    each row's rewind window.  The frontier strictly descends (a round
    leaves every higher row's cells ``8..acc`` untouched and complements the
    frontier row's carry), so rows above it are settled and skipped, and the
    endgame's read, pool code and lengths are fixed by the frame constants
    -- which is what prices a combination without building it.

    Two exactnesses make the answer the sweep's own.  The guard, cap and
    refusal sites are reproduced one for one, so a combination fails here
    exactly when its sculpt returns None.  And a combination is abandoned
    only when its running length strictly exceeds the best completed one, so
    it can no longer finish at or below it -- ties complete, and the winner
    is chosen over exact lengths in sweep order.  The one live check: the
    first column is computed both ways, and a disagreement distrusts the
    whole scout rather than shipping from the law.

    ``rewinds_out``, when given, collects each completed combination's
    rewinds in firing order -- the one fact beyond the length that
    :func:`_mux_rule_tail` needs to spell the build without sculpting it.
    Recording is free (the pending list already holds them), and leaving
    the parameter off prices exactly as before.
    """
    ms = base.ms
    if any(m.dead or m.skip for m in ms):
        return None, False
    byte = ms[0].tape & _POOL_MASK
    if any((m.tape & _POOL_MASK) != byte for m in ms):
        return None, False
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:
        return None, False
    c_probe = frame[1]
    codes = tuple(_POOL_CODES)
    slice0 = _pool_slice(codes, 0, skip=False)
    # What `_try_print` will do.
    # the pool code `_find_pool`.
    # its walk out carries -- None.
    # orientation's.
    endgames: dict[int, tuple[int, int, int] | None] = {}
    for cell7 in (0, 1):
        chosen = slice0.get((byte, cell7))
        if chosen is None:
            endgames[cell7] = None
            continue
        end_frame = _probe_frame(codes[chosen[0]], byte)
        if end_frame is None or end_frame[0] != chosen[1]:
            return None, False
        endgames[cell7] = (len(codes[chosen[0]]), chosen[1], end_frame[1])

    want = tuple(int(ch) for ch in truth_table)
    ptrs = base.ptrs()
    rows = len(ptrs)
    highest, lowest = max(ptrs), min(ptrs)
    order = sorted(range(rows), key=lambda r: ptrs[r], reverse=True)
    ptrs_s = [ptrs[r] for r in order]
    want_s = [want[r] for r in order]
    # Each row's tape reversed.
    # ``ptr - j`` -- so every row's.
    # whatever its pointer, the.
    # and the parity delta is a.
    # combinations all start from.
    base_tapes = [_rev_bits(ms[r].tape, ptrs[r] + 1) for r in order]
    base_len = len(base.template())
    guard = lowest - _POOL_WIDTH
    cap = 2**n + 4
    checked = False
    best: int | None = None
    lengths: dict[tuple[int, bool], int] = {}
    # Scouted largest accumulator.
    # ``K = frontier - acc + 1``,.
    # pricing them first is what.
    # bottom after a handful of.
    parities: list[int] | None = None
    for acc in reversed(accs):
        # Each row's parity over cells.
        # cells ``8..acc`` of a.
        # run ``acc - 7`` wide.
        # window loses its top cell, so.
        shifts = [p - acc for p in ptrs_s]
        if parities is None:
            pmask = (1 << (acc - _POOL_WIDTH + 1)) - 1
            parities = [
                ((t >> s) & pmask).bit_count() & 1
                for t, s in zip(base_tapes, shifts, strict=True)
            ]
        else:
            parities = [
                par ^ ((t >> (s - 1)) & 1)
                for par, t, s in zip(parities, base_tapes, shifts, strict=True)
            ]
        for direct in (True, False):
            g = 0 if direct else 1
            # `_try_print`'s own trial.
            # read matches when its.
            # between the probe's parity.
            matched = None
            for read, cell7 in (
                (_READS[0], 0),
                (_READS[0], 1),
                (_READS[1], 0),
                (_READS[1], 1),
            ):
                end = endgames[cell7]
                if end is None:
                    continue
                offset = g ^ c_probe ^ end[2]
                if offset == (0 if read == _READS[1] else 1):
                    matched = (read, end)
                    break
            if matched is None:
                # No read prints this.
                # rounds and then `_try_print`.
                continue
            read, (code_len, landed, _) = matched
            # Everything the sculpt emits.
            # front: the trailing ``x``,.
            # code, walk out, read, rewind.
            total = (
                base_len
                + 1
                + (highest + 1)
                + code_len
                + 2 * (acc - 1 - landed)
                + len(read)
                + (acc - _POOL_WIDTH + 1)
                + 3
            )
            flip = c_probe ^ g
            if not checked:
                simmed = _mux_probe_sim(base, acc, 0)
                fast = _sculpt_columns(base, acc)
                if simmed is None or fast is None or fast != simmed[0]:
                    return None, False
                checked = True
            # Rounds reach a row lazily,.
            # The scan never revisits a row.
            # (rows above the frontier keep.
            # above) and one that disagrees.
            # the round itself -- so each.
            # its one examination, and rows.
            # abandoned never pay for the.
            aborted = False
            settled = 0
            pending: list[tuple[int, int]] = []
            for _ in range(cap):
                i = settled
                while i < rows:
                    t = base_tapes[i]
                    got = flip ^ parities[i]
                    s = shifts[i]
                    for width, wmask in pending:
                        win = t & wmask
                        carr = win
                        span = 1
                        while span < width:
                            carr ^= carr >> span
                            span <<= 1
                        delta = win ^ carr ^ wmask
                        t ^= delta
                        got ^= (delta >> s).bit_count() & 1
                    if got != want_s[i]:
                        break
                    i += 1
                if i == rows:
                    break
                frontier = ptrs_s[i]
                rewind = frontier - acc + 1
                if rewind > guard or (
                    best is not None and total + 3 * rewind + 1 > best
                ):
                    aborted = True
                    break
                total += 3 * rewind + 1
                pending.append((rewind, (1 << rewind) - 1))
                settled = i + 1
            else:  # pragma: no cover - the cap cannot be reached
                # A round sets ``settled = i +.
                # ``settled`` strictly.
                # run against a cap of ``rows +.
                # against that invariant.
                aborted = True
            if not aborted:
                lengths[(acc, direct)] = total
                if rewinds_out is not None:
                    rewinds_out[(acc, direct)] = [width for width, _ in pending]
                if best is None or total < best:
                    best = total
    if best is None:
        return None, True
    for acc in accs:
        for direct in (True, False):
            if lengths.get((acc, direct)) == best:
                return (acc, direct, best), True
    raise AssertionError("the scout lost its own winner")  # pragma: no cover


# : The arity where the sculpt.
# : ``(accumulator,.
# : the corpus is.
# : own cost curve makes the.
# : build at nine inputs, 201s.
# : by rule instead: the.
# : scout prices first because.
# : ``3 * (frontier - acc + 1).
# : rewind).
# : constants, which do not.
# : is loosest exactly at the.
#: builds iff any does.
# :.
# : The rule trades length for.
# : arity where the contest.
# : where the trade is cheapest.
# : at six inputs, 0.38s at.
# : payable and nine is not,.
#: cost used to live.
# :.
# : Against the sweep's winner.
# : eight inputs, +6.4% at nine.
# : arities parity picks the.
# : costs exactly one dense.
# : eight and below.
# : would buy 3.8s for a.
# : stops being a trade at all:.
# : accumulator for dense but.
#: and parity +50.7%.
_MUX_RULE_ARITY = 9


def _mux_rule_tail(
    base: _Joint, acc: int, rewinds: list[int], *, direct: bool
) -> tuple[str, str]:
    """Spell the sculpt the scout priced, from its recorded rewinds.

    With the rewinds in firing order every emitted part is a constant of
    the frame: a round is ``<``/``[x`` runs of its rewind and a trailing
    ``x``, the clamp is ``highest + 1`` (rounds move no pointer), and the
    endgame's pool code, walk, read and rewind are fixed by ``acc`` and the
    pool byte -- the same constants the scout priced the combination over.
    Returns ``(rounds, suffix)``, the tail after ``base``'s own template
    split where :func:`_mux_replays` switches laws.

    Nothing ships on this spelling alone: :func:`_mux` replays it over
    every row and accepts on the printed digits, and its length is checked
    against the scout's independent prediction.
    """
    byte = base.ms[0].tape & _POOL_MASK
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:  # pragma: no cover - the scout priced through this frame
        raise AssertionError("no probe frame for a priced combination")
    codes = tuple(_POOL_CODES)
    slice0 = _pool_slice(codes, 0, skip=False)
    g = 0 if direct else 1
    for read, cell7 in (
        (_READS[0], 0),
        (_READS[0], 1),
        (_READS[1], 0),
        (_READS[1], 1),
    ):
        chosen = slice0.get((byte, cell7))
        if chosen is None:
            continue
        end_frame = _probe_frame(codes[chosen[0]], byte)
        if end_frame is None or end_frame[0] != chosen[1]:  # pragma: no cover
            raise AssertionError("the endgame frame drifted from the pool slice")
        if g ^ frame[1] ^ end_frame[1] == (0 if read == _READS[1] else 1):
            code, landed = codes[chosen[0]], chosen[1]
            break
    else:  # pragma: no cover - the scout's winner matched the same trial
        raise AssertionError("the priced combination has no matching read")
    highest = max(base.ptrs())
    rounds: list[str] = []
    for rewind in rewinds:
        rounds.append("<" * rewind)
        rounds.append("[x" * rewind)
        rounds.append("x")
    suffix = "".join(
        (
            "x",
            "<" * (highest + 1),
            code,
            "[x" * (acc - 1 - landed),
            read,
            "<" * (acc - (_POOL_WIDTH - 1)),
            "[x.",
        )
    )
    return "".join(rounds), suffix


def _mux_replays(
    base: _Joint, rewinds: list[int], suffix: str, truth_table: str
) -> bool:
    """Whether the spelled build really prints the table, row by row.

    The module-wide acceptance, applied to the scout's spelling: every row
    advances through the tail by the laws and the digits it prints are
    compared against the table -- the same standard :func:`_try_print`
    holds a sculpted joint to.  The rounds go through the fused
    :meth:`_Sim.run_rewinds` (one window per row where the parsed runs
    cost three law calls a round), the endgame through the parsed runs;
    ``suffix`` must be the tail past the rounds, exactly as
    :func:`_mux_rule_tail` spells it.
    """
    probe = base.fork()
    for m in probe.ms:
        m.run_rewinds(rewinds)
    probe.emit(suffix)
    return probe.printed() == list(truth_table)


def _mux_sweep(base: _Joint, truth_table: str, n: int, accs: range) -> str | None:
    """Sculpt every combination for real and keep the shortest build.

    The specification :func:`_mux_scout` is held to, and the fallback when
    it cannot summarise the base or its replayed winner disagrees.  The
    seed probe settles which orientations can be sculpted at all --
    ``cell7 == 1`` is answered by no code -- and also hands the sculpt its
    ``hint``, which is how the loop always read.
    """
    best: str | None = None
    for acc in accs:
        for cell7 in (0, 1):
            seed = _mux_probe(base, acc, cell7)
            if seed is None:
                continue
            for direct in (True, False):
                built = _mux_sculpt(
                    base, truth_table, n, acc, cell7, direct=direct, hint=seed[1]
                )
                if built is not None and (best is None or len(built) < len(best)):
                    best = built
    return best


def _mux(truth_table: str, n: int) -> str | None:
    """Build by separating the rows, then sculpting the column they print.

    **Every combination is tried and the shortest program wins.**  This used
    to return the first ``(C, orientation, read)`` that printed, and that is
    a poor choice for length: a sculpting round costs ``3 * K + 1``
    characters for a rewind of ``K = frontier - C + 1``, so the accumulator
    decides the price of every round the table needs, and the cheapest one is
    not the first.  Taking the first ascending accumulator measured a mean of
    1046 characters over sampled four-input tables; descending measured 700
    and the minimum over all of them 595, a **43% reduction**.  The curve is
    not monotone in either direction -- sampled tables put their minimum at
    the top, the bottom and the middle -- so there is no cheap rule to prefer
    over measuring, and measuring is what this does.

    The measuring is the scout's.  Sculpting every combination for real
    priced the sweep at ``2**3n`` law applications -- 178 cold seconds at
    eight inputs, 97% of a cold seven-input profile -- so :func:`_mux_scout`
    prices them all in closed form (the same dense build is 1.9s cold) and
    exactly one combination, the winner, is sculpted for real.  Nothing is
    returned on the strength of the shadow: the replayed sculpt simulates
    every row as it always did, `_try_print` accepts on its own output,
    and a replay that misses the scout's exact predicted length falls back
    to :func:`_mux_sweep` -- as does a base state the scout refuses to
    summarise.

    Nothing about *which* tables build changes: a combination that stalls
    still contributes nothing, and this returns None exactly when the old
    loop did, having priced the same set.

    From :data:`_MUX_RULE_ARITY` the contest itself is the build's cost,
    so the accumulator is named rather than measured -- see that constant
    for the rule, the trade and the coverage argument.  Only the
    orientation is still priced (a real contest: 21 to 21 over sampled
    eight-input tables, worth up to 24%), the scout records the winner's
    rewinds as it prices, and the build is spelled from them and accepted
    on its own replay rather than sculpted.
    """
    if n < _MUX_MIN_ARITY:
        return None
    base = _mux_separate(n)
    if base is None:
        # `_mux_separate` refuses only.
        # construction does not trip at.
        # This is that refusal reaching.
        return None  # pragma: no cover - the separation never refuses
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    # ``+ 1`` past the rewind.
    # guard exactly tight rather.
    accs = range(highest - lowest + _POOL_WIDTH + 1, lowest - 1)
    recorded: dict[tuple[int, bool], list[int]] = {}
    if n >= _MUX_RULE_ARITY:
        # The rule replaces the.
        # accumulator.
        # its trust check and its.
        # just no longer asked to price.
        accs = range(accs.stop - 1, accs.stop)
    winner, trusted = _mux_scout(
        base, truth_table, n, accs, recorded if n >= _MUX_RULE_ARITY else None
    )
    if not trusted:
        # The separation's state.
        # at any arity -- the base is.
        # is the guard against a future.
        return _mux_sweep(base, truth_table, n, accs)
    if winner is None:
        return None
    acc, direct, predicted = winner
    if n >= _MUX_RULE_ARITY:
        # Spell the winner from the.
        # replay: the sculpt.
        # arity is most of what remains.
        widths = recorded.get((acc, direct))
        if widths is not None:
            rounds, suffix = _mux_rule_tail(base, acc, widths, direct=direct)
            spelled = base.template() + rounds + suffix
            if len(spelled) == predicted and _mux_replays(
                base, widths, suffix, truth_table
            ):
                return spelled
        # The scout, the spelling and.
        # the trio; the sweep is the.
        # rather than raise.
        return _mux_sweep(base, truth_table, n, accs)  # pragma: no cover
    built = _mux_sculpt(
        base, truth_table, n, acc, 0, direct=direct, hint=_SCULPT_POOL_CODE
    )
    if built is None or len(built) != predicted:
        # The shadow and the sculpt.
        # sweep is the exact spelling,.
        # -- the build that returns is.
        return _mux_sweep(base, truth_table, n, accs)
    return built


def _lift_leaves_name_order(essential: list[int], n: int) -> bool:
    """Whether lifting would emit the ``{Xi}`` out of ascending order.

    :func:`_lift` appends the ignored inputs after the solved template, so
    the result is still sorted when every ignored index is above every
    essential one -- ``{X0}{X1}`` then ``{X2}``.  It is only when an ignored
    index sits *below* an essential one that the append leaves sequence.
    """
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    """Renumber a smaller table's placeholders back onto the wider arity.

    The inner solve used ``{X0}..{Xk-1}``, which correspond to the original
    inputs listed in ``essential``.  The renaming is done in a single pass, so
    a rename cannot collide with a placeholder it has not rewritten yet.

    Every input the function ignores still needs a placeholder, or the harness
    would have a bit with nowhere to put it.  Those go on the end: the fill is
    two characters whichever bit it is, so they cannot make the program's
    length depend on the inputs, and by then the digit has been printed -- the
    ``.`` has already run -- so whatever they do to the tape cannot matter.
    """
    rename = {f"X{slot}": f"X{i}" for slot, i in enumerate(essential)}
    lifted = re.sub(
        r"\{(X\d+)\}",
        lambda m: "{" + rename[m.group(1)] + "}",
        template,
    )
    ignored = "".join("{X" + str(i) + "}" for i in range(n) if i not in essential)
    return lifted + ignored


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minifuck has no usable input command, so this is a parameterized
    generator: the template's ``{Xi}`` placeholders become ``[<`` for a one
    and ``xx`` for a zero -- equal width, so no instantiation leaks its
    inputs through its length -- and the harness instantiates one program per
    input combination.

    The emitted program embeds each input once, computes the table in cells
    past the pool, relays the answer into the *pointer* (values cannot travel
    left, but the pointer can), and prints one ASCII digit.  Every emission
    is tracked against all ``2**n`` rows by the closed-form laws in
    :mod:`esolangs.tools.boolean.minifuck_sim`, and a :class:`ValueError` is
    raised rather than returning a program that has not been seen to print
    the table.

    Cached, because at four inputs and above the derivation is what
    this module costs -- seconds to tens of seconds a table, against
    effectively zero to *run* the program it returns.  Below that nothing
    searches at all: two and three inputs are derived from the staging
    enumeration and the sculpted route, and all 276 tables up to three inputs
    build in about three and a half seconds together.  The build is
    deterministic in ``truth_table`` and the result is an immutable string,
    so repeat calls are free either way.
    """
    n = _validate_shape(truth_table)

    # A table that ignores some of.
    # extra ones, so solve it at.
    # placeholders back.
    # what it costs depends on the.
    # table with a narrow core is.
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projecting is much the.
        # inputs after the ``.``, which.
        # index sits below an essential.
        # slot down in ascending order,.
        # in-order by construction --.
        # lift would disorder, and only.
        # path.
        # at n == 3, ``00000101`` ran.
        # still failed, against seconds.
        # a miss here falls through to.
        # The attempt is a fixed-cell.
        # wins is won; the column.
        # so this is cheap by.
        if _lift_leaves_name_order(essential, n):
            if len(essential) <= 1:
                in_order = _degenerate(truth_table, n)
                if in_order is not None:
                    return in_order
            reconverged = _reconverged(truth_table, essential, n)
            if reconverged is not None:
                return reconverged
            # **The last ten out-of-order.
            # .
            # Ten three-input tables used.
            # the same shape: the ignored.
            # routes above cannot sort.
            # first does not help when it.
            # reconvergence drives every.
            # collapse ``x1`` while.
            # no reset exists.
            # "sorting those needs the.
            # .
            # It does not.
            # order at the *full* arity and.
            # name order by construction --.
            # table ignores an input,.
            # row by row rather than.
            # have disturbed.
            # print every row correctly on.
            # .
            # It goes *after* the two cheap.
            # expensive one and they.
            # is left here is exactly the.
            sculpted = _mux(truth_table, n)
            if sculpted is not None:
                return sculpted
        inner = _solve(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input.
    # and the embed already holds.
    # answer is a cell lookup.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # A planned staging is the.
    # and three inputs are both.
    # the enumeration plus the.
    # runs below four inputs.
    # searches below.
    derived = _staged(truth_table, n)
    if derived is not None:
        return derived

    # The sculpted route: it closes.
    # families miss,.
    # the last route -- **it is.
    # arity**, so the raise below.
    # generator is meant to take.
    sculpted = _mux(truth_table, n)
    if sculpted is not None:
        return sculpted

    # **Reaching this is a bug, not.
    # .
    # This used to be a deliberate.
    # sat at this point; at ``n >=.
    # five-input table the staged.
    # 240-second cap and was still.
    # an indefinite one.
    # comment here recorded that as.
    # "the tables it refuses are.
    # .
    # There are no such tables left.
    # the time, so everything above.
    # :data:`_MUX_MIN_ARITY`), and.
    # closes by an argument uniform.
    # "Is ``_mux`` total?" in.
    # not survive that file's.
    # now, for this generator and.
    # the arities that document.
    # totality argument has been.
    # table that broke it.
    raise ValueError(f"the Minifuck boolean generator could not build {truth_table!r}")


def minifuck(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    The construction is :func:`_solve`; this is the public entry, and the
    difference is the arity check.  ``_solve`` accepts a *nullary* table
    because it recurses into itself after projecting a table onto its
    essential inputs, and a constant table projects to a single entry --
    six such calls happen while building the 276 tables up to three inputs.
    A one-entry table is not a boolean function of any input, though, so it
    is refused at the API the way every other generator refuses it.
    """
    _validate_truth_table(truth_table)
    return _solve(truth_table)


# The construction's cache and.
# but tests and callers reach.
# ``cache_clear``/``cache_info``.
# arity check off did not move.
minifuck.cache_clear = _solve.cache_clear  # type: ignore[attr-defined]
minifuck.cache_info = _solve.cache_info  # type: ignore[attr-defined]
minifuck.__wrapped__ = _solve.__wrapped__  # type: ignore[attr-defined]
