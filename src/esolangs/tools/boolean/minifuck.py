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

# The machine the construction below emits against.  ``_Sim`` and ``_Joint``
# are re-exported rather than referenced through the module because the test
# suite imports them from here by name, and because every use in this file
# reads as part of the construction rather than as a call into a simulator.
from esolangs.tools.boolean.minifuck_sim import _clamp, _Joint, _runs, _Sim, _walk_to

__all__ = ["minifuck"]

# What an acceptance callback keeps: each search names its own result type,
# and returning None means "keep looking".

# Where the embedded bits start.  The pool is cells 0..7, so the working area
# begins past it with a little room for the walk-in.
_BASE = 16

# What separates one embedded bit from the next.  A plain ``[x`` run leaves
# the prefix-XORs too correlated for the one-sided tests the endgame makes;
# the ``<`` steps back over a cell so the parities stay distinguishable.
#
# The separator decides the affine picture the whole construction reads from,
# and the first two here were picked by hand -- the binding constraint rather
# than a detail: between them they leave 126 distinct columns standing in
# :func:`_staging_index` against the 252 all five reach (98 of them, 49 as
# complement pairs, inside the population the coverage figures use).  The
# figure here read 92, which no frame reproduces; it is corrected with its
# frame named, since a bare count is what made it unrecoverable.
# And 112 of the 120 tables the searches could not reach were absent from the
# tape entirely rather than merely hard to print.  Enumerating short strings
# over the same alphabet fixed that -- the three added below carry 118 of
# those 120, and the searches never had to change.
# Only the first two are used by the routes that scan separators (the
# degenerate path and the fallback searches); the rest are reached by the
# staging enumeration, so adding one costs those routes nothing.
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]

# The separators the scanning routes try.  Widening this would multiply every
# search's cost; the plan reaches the others directly instead.
_SCAN_SEPS = _SEPS[:2]

# How far the bits and their working area reach, for sizing the windows.
_SPAN = 6

# The pool spells ASCII '0' (0b00110000) or '1' (0b00110001), so cells 0..6
# are fixed and cell 7 carries the answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# How wide the pool is.  ``.`` reads ``tape[:8]`` as one byte, so this is a
# byte and not a tunable: it is the same 8 that ``_POOL`` above spells out.
#
# **Several numbers in this module are this one wearing different hats**, and
# spelling them as literals hid a relationship the totality argument in
# ``docs/minifuck_generator.md`` turns on.  What derives from it:
#
# * the accumulator floor -- ``_endgame`` refuses ``acc < _POOL_WIDTH``,
#   because the accumulator has to sit past the pool;
# * the sculpting rewind guard, ``rewind > min(ptrs) - _POOL_WIDTH``, which
#   is what keeps a round's writes off the pool;
# * :data:`_PROBE_WALK_OUT` and the lowest cell a round may write, both
#   ``_POOL_WIDTH + 1``;
# * the sculpting accumulator loop's start, ``span + _POOL_WIDTH + 1``.
#
# The last pair is essential. The loop starting one *past* the
# guard is exactly what makes the rewind bound tight rather than slack: the
# worst rewind is ``lo - _POOL_WIDTH``, which is the guard itself, so the
# guard can never fire.  Written as ``8`` and ``9`` the two look independent
# and the identity looks like a coincidence.
#
# The staging path takes the same two: its accumulator loops start at
# :data:`_PROBE_WALK_OUT`, and the counts spelled ``_MAX_ACC - _POOL_WIDTH``
# are the length of that loop.  Only ``_MAX_ACC`` itself is a search bound.
#
# What is *not* this constant is ``_MUX_GUARD``'s ``8``, which is a scratch
# width: collapsing it into this would assert a relationship that does not
# hold.  It is not independent either, though, which is a separate point --
# :func:`_mux_start`'s offset is derived from it, because the embed starts at
# the shortest position whose leftmost write still clears the guard.  So the
# two are coupled, just not through this constant.
_POOL_WIDTH = len(_POOL) + 1

# The two reads.  ``[<`` leaves the pointer at ``(acc-1) + v``; ``[x<[<``
# leaves it at ``(acc-1) + NOT v``, restores the cell, and flips its
# neighbour unconditionally.  The printed digit is ``NOT(v XOR cell7)`` and
# every reachable pool conserves that XOR, so the read polarity -- not the
# pool -- is what makes a table and its complement both printable.
_READS = ("[<", "[x<[<")


# What complements the bit a setter just wrote.  ``<`` steps back over the
# cell the setter used and ``[`` flips it, which cascades into the setter's
# own cell -- so the bit standing there is inverted, and the pointer is left
# where the setter left it.
#
# The trailing character is not padding.  That cascade sets the interpreter's
# skip flag, and a gadget that ends there eats the *next* instruction of the
# template, shifting every later embedding by a cell; the third character
# feeds the skip instead.  Measured rather than reasoned: the two-character
# ``<[`` passes a probe that compares tape and pointer, and the tables built
# on it printed 0 of 12 on the real interpreter.  ``skip`` is part of the
# state, and a probe that omits it reports a gadget that is not one.
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


# Pool codes move a mark right, then place the pointer behind it.
# The five shipped plans are tried in order and accepted only by the same
# joint-state check used for every candidate. Their spellings are behavioral:
# seemingly similar strings can diverge on the live pool state.
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


# Each plan is ``(steps, core, overrides)``: how many steps the code walks,
# which one is the core, and the steps that are not the default.  A default
# step carries the mark one cell and leaves the pointer one behind it; the
# core carries two.  Two of the five need no override at all -- they are the
# construction indexed by where the mark goes, and nothing else.
#
# An override is ``(backs, odd)`` for the step it names, so the two free
# variables stay visible side by side.
#
# **Why these values, and not a shorter description.**  The plans do not
# compress further, which was measured rather than assumed.  ``core`` is not
# derivable from the finished code: on a blank tape every plan with
# ``core > 0`` ends at ``mark = steps + 1`` and ``pointer = steps`` whatever
# the core's index -- verified for ``steps`` 1 to 40 -- so the blank-tape
# outcome cannot pick it.  It is pinned on live states instead, and the two
# properties split the way they do for the codes themselves.  Moving the core
# strands tables at every alternative for three of the plans -- 22 for the
# third, 18 for the fourth, 6 for the fifth -- which for the third and fourth
# is exactly what dropping those codes outright costs.  The second plan's core
# strands nothing at any alternative and is pinned by the quiet property
# instead: slot order goes from 10 out-of-name-order templates to 18, the same
# cost the ablation records for the non-stranding codes.
#
# Only the first plan's core moves freely, and that is not a fact about the
# core.  That code answers no site at ``n <= 3`` at all -- it is one of the two
# the ablation finds strands nothing -- so every spelling of it looks free at
# the arity being measured.  The two spellings are genuinely different
# functions, leaving marks at cells 1, 2, 4 against a single mark at 3.
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


# What the pool derivation probes with.  The verdict is invariant in the walk
# out (measured over 9..39, no ``(site, code)`` pair changes answer), so the
# derivation needs *a* value and not the caller's; naming one here is what lets
# the key omit it.  The smallest legal accumulator, since :func:`_endgame`
# rejects anything under 8 and the probe should sit where every caller's does
# or further left.
_PROBE_WALK_OUT = _POOL_WIDTH + 1

#: The window a pool verdict depends on: cells 0 to ``_POOL_WIDTH - 1``.
_POOL_MASK = (1 << _POOL_WIDTH) - 1


#: How far right a row can sit and still be summarised by its window.
#:
#: The bound is not "where acceptance stops" -- codes answer out to pointer 10
#: -- but **where the window stops being the whole key**.  Two things fail
#: further right, and this is the tighter of them:
#:
#: * At pointer 3 the codes reach above cell 7, so the window no longer
#:   determines the verdict: 3 of 300 random window values changed answer when
#:   the cells above them were re-randomised.  At pointers 0 to 2 that is 0 of
#:   2400, over eight redraws of 28 bits each.
#: * From pointer 4 the verdict also starts depending on the walk out, which
#:   :func:`_find_pool` deletes: 31 keys change answer across walk outs 9 to
#:   39, none of them below pointer 4.
#:
#: So the table is derived over the pointers where one answer is *the* answer,
#: and a row beyond it is refused rather than guessed at.  Nothing is lost:
#: every site a build reaches has the pointer at 0 -- 1956 of 1956 at two and
#: three inputs -- so the refused region is one the generator never asks about,
#: and refusing is what keeps the lookup honest instead of returning a verdict
#: that cells outside the key would contradict.
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
        # Neither guard the scan carried can fire inside the derived domain:
        # over its 7680 (key, code) runs no code leaves a row dead or
        # mid-skip, and none ends right of the probe's walk out.  They were
        # refusals when a *candidate* was being tried; the list is fixed now,
        # so a code that broke either would be a change to the pool rather
        # than a state to skip past, and raising says so where a ``continue``
        # would quietly drop the code from the table.
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
            # A dead row prints nothing, and one past the bound is outside the
            # window's reach.  Both mean "no pool from here".
            return None
        rows = _pool_slice(codes, row.ptr, skip=row.skip)
        return rows.get((row.tape & _POOL_MASK, cell7))

    chosen = answer_for(j.ms[0])
    if chosen is None:
        return None
    for row in j.ms[1:]:
        # Equality covers both conditions at once: the rows must name the same
        # code *and* be left on the same cell by it.
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
    # ``_find_pool`` accepts a code only after checking the pool *past* the
    # walk out, which is the state reached here -- so this is that check
    # restated on what was actually emitted rather than on a simulated walk.
    # It is an AssertionError rather than a ValueError deliberately: the two
    # disagreeing is a bug in the pair, and ``_try_print`` swallows every
    # ValueError, which would turn it into a silently skipped accumulator.
    for cell in range(_POOL_WIDTH):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)


# Derived columns, keyed by ``(template, accumulator, orientation)``.  A plain
# dict rather than ``lru_cache`` because the key is computed from the mutable
# ``_Joint`` rather than being its arguments, and because ``None`` is a real
# answer here -- the sentinel keeps it distinguishable from a miss.
#
# ``_derived_plans.cache_clear`` empties this too, because a caller asking for
# a cold derivation means a cold one: tests harvest ``_find_pool`` call sites
# from a build and assert they saw hundreds, which a warm column cache cuts to
# seventeen.  Clearing the plan cache alone would leave that trap in place.
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
    except ValueError:  # pragma: no cover - not observed; see below
        # Never seen to fire, but *not* dead by construction, which is why
        # this says "not observed" rather than "unreachable".  The obvious
        # argument -- that `_find_pool` was asked for a code reaching
        # `acc - 1`, so the walk must succeed -- does not hold: `walk_out`
        # is deleted rather than forwarded, because the verdict is invariant
        # in it.  So a code that fits the site says nothing about how far
        # right the accumulator can then be relayed.
        #
        # What is measured: 1740 real stagings, captured from builds at two
        # and three inputs, walked over the whole accumulator range with the
        # cache cleared each time -- no failure.  A direct `_walk_to` to an
        # unreachable target raises, as the control.
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
        # Setting the pool is what converges the rows, so a code that fits
        # leaves exactly one pointer: measured over every table at two and
        # three inputs, 27620 sweeps, all of them a single pointer.  The
        # check stays because that convergence is a property of the pool
        # codes rather than something this function establishes.
        return {}  # pragma: no cover - the pool converges the rows
    cur = ptrs.pop()
    columns: dict[int, tuple[int, ...]] = {}
    for acc in range(_PROBE_WALK_OUT, _MAX_ACC + 1):
        if acc - 1 < cur:
            # The walk only ever runs forward into the accumulator range:
            # the pool leaves `cur` at 4 or 5 (measured over the same 27620
            # sweeps) and the loop starts asking at `acc - 1 == 8`, so it is
            # always behind.  Guards the invariant rather than a case.
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
    except ValueError:  # pragma: no cover - not observed; see below
        # The derivation only offers accumulators whose column it already
        # read off a walk, so the endgame it then runs has somewhere to go.
        # Traced over every table at two and three inputs: 268 confirmations,
        # none of them raising.  Kept rather than removed because the whole
        # point of this function is that nothing is recorded on the strength
        # of the algebra alone -- an endgame that could not run is exactly
        # the disagreement it exists to catch.
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
        # The endgame's own first refusal, mirrored: an accumulator inside
        # the pool cannot be printed from, and asking the derivation about
        # one would send its walk leftward instead.  ``_degenerate`` probes
        # every recorded cell and the constant-one column stands at cell 1
        # -- the walk-in's own wake -- so this is a case every degenerate
        # build reaches rather than a guard.
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
                # The endgame refuses on exactly the two conditions the
                # derivation already declined on -- no pool code, or a walk
                # that cannot reach -- so a pair the derivation offered has
                # somewhere to go.  Kept because the derivation and the
                # emission disagreeing is precisely what the acceptance
                # below exists to catch, and a raise here is that
                # disagreement's other spelling.
                continue
            if probe.printed() != want:  # pragma: no cover - the acceptance
                # Never observed -- the derivation is the emission's own
                # algebra -- but this is the "seen to print" standard, so a
                # divergence is reported as a miss rather than shipped.
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


# The fixed head of the reconverging reset.  What follows it is a run of
# ``<``, which clamps rather than writing, so the run only has to be long
# enough to bring every row home; see :func:`_reset_code`.
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
        # The ignored inputs have to be the *leading* ones for emitting them
        # first to keep the order ascending.
        return None

    # Where to look for the answer once the ignored inputs are gone.  One
    # essential input leaves a projection, which stands at a known cell; two
    # leave a two-input table, which has a staging of its own -- so replay
    # that staging and read its own accumulator rather than scanning.  The
    # scan is what costs: at two essential inputs it turns a 0.5s build into
    # seconds without reaching anything the staging does not.
    if len(essential) == 1:
        setup: tuple[int, int, int, int] | None = None
        accumulators: tuple[int, ...] = tuple(_degenerate_cells(n).values())
    else:
        inner = _project(truth_table, essential, n)
        plan = _derive_staging(inner, 2)
        if plan is None:
            return None
        sep_index, settle, brackets, acc = plan
        # Every two-input staging is a plain bracket run; the literal-suffix
        # form is only used by the one stored three-input exception, and
        # replaying it here would need the walk this route does not make.
        if not isinstance(brackets, int):
            return None
        setup = (sep_index, settle, brackets, acc)
        accumulators = (acc,)

    # One constructed reset rather than a handful of searched ones.  The
    # convergence is still *checked* before anything is built on it: the
    # construction came from measurement, and a silent failure here would
    # surface much later as a table that will not print.
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
            # The staging's settle count, replayed the way ``_embed`` does
            # it: re-crossing the bit region advances the affine state, and
            # the accumulator was chosen against the state that produces.
            # The enumeration hands back ``settle == 1`` for AND and NAND,
            # and six three-input tables project onto one of those, so
            # ignoring the field would replay them against the wrong tape.
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


# The staged construction: one ``(separator, settle, suffix, accumulator)``
# per complement pair, *derived* rather than stored.
#
# The embed leaves an affine picture -- every cell holds a linear form in the
# input bits plus the one nonlinear term the ``[`` cascade computes -- and a
# plain run of ``k`` brackets from ``_BASE - 1`` sweeps that picture forward,
# exposing a different function at each step.  So the whole problem is: pick
# the separator, the bracket count and the accumulator, then hand the result
# to the endgame every other route already uses.
#
# Which is small enough to *enumerate*.  :func:`_stagings` gives the order --
# 5 separators x 2 settle counts x 29 bracket counts x 26 accumulators -- and
# a table is built by the first entry that prints it, so no table of answers
# is needed.
#
# :func:`_derived_plans` runs that enumeration for a whole arity at once,
# which is what makes it affordable.  A staging is expensive to build and
# cheap to test against a table, so the loops go staging-major: one embed per
# (separator, settle), the bracket run extended one instruction at a time,
# and the endgame emitted once per (k, accumulator, read, orientation)
# whatever the table.  Measured, the whole three-input arity derives in 2.4s
# and two inputs in 0.15s; the table-major spelling of the same search costs
# minutes, because it rebuilds every staging once per table.  (Those two were
# 15s and 0.9s when this was written and are re-measured here rather than
# carried forward -- a timing in prose ages against every change under it.)
#
# What the three-input arity spends that on is 127 distinct stagings, spread
# over all five separators -- 34, 29, 37, 23 and 4 of them -- and both settle
# counts, 94 at zero and 33 at one.  The load is nowhere near even, and
# separator 4 carrying four stagings is the reason the list is not trimmed on
# a glance at how often each is named.
#
# Selection is on the accumulator's value **at the read**, not on the cell
# that holds the answer beforehand.  Those differ, because the walk out
# applies the running prefix-XOR: at ``acc = 22`` after separator 1, AND
# ``(0,0,0,1)`` arrives as the constant ``(1,1,1,1)``, and XOR ``(0,1,1,0)``
# arrives as ``b1``.  Choosing on the pre-walk column is what made an earlier
# version of this cover 10 of the 16 two-input tables rather than all of them.
# The enumeration sidesteps that trap by construction: it does not reason
# about which column *ought* to arrive, it emits the endgame and reads what
# the rows actually printed.
#
# A table and its complement share a staging, because the endgame tries both
# read polarities and both pool orientations and the printed digit is
# ``NOT(v XOR cell7)``, so the complement costs nothing to reach.  That is
# why the counts below are given in complement pairs.
_Staging = tuple[int, int, int | str, int]

# **The population every figure below is stated over.**  109 is the number of
# complement pairs of three-input tables that are non-degenerate *and* depend
# on all three inputs: 128 pairs, less the 3 the degenerate route claims,
# less the 16 that ignore an input and go to the projection route.  Saying
# only "non-degenerate" leaves 125, and that missing half of the definition
# is why two later re-probes could not reconcile these counts -- one of them
# reporting 252, which is not a population at all but the column count of
# :func:`_staging_index`, twice 126 because the index holds each column and
# its complement.  Derived with :func:`essential_inputs` rather than a local
# copy of the test.
#
# **Coverage, and the one table that must still be stored.**  The enumeration
# reaches 108 of those 109 and all 8 at two inputs.  That the single miss is
# the table named just below is what pins the definition: a wrong population
# of a similar size would not put the holdout there.
# The holdout is ``01101101`` / ``10010010``, and why is worth
# knowing: it was the hardest table here by some margin and the searches
# never built it at all -- both members raise after about 96 seconds.
#
# Its answer column is not scarce: 14375 of 804600 sparse suffixes leave it
# standing somewhere on the tape.  What is scarce is a staging that also
# *carries* it to the read, because the walk's prefix-XOR rewrites the very
# cell.  A pure bracket run never manages it -- which is exactly why the
# enumeration cannot reach it, every entry of :func:`_stagings` being a run --
# and the stored suffix interleaves two ``<`` into the run instead.
#
# The shape of that miss is worth recording so it is not re-run blind.  Unlike
# the tables the wider separator set closed, its answer *is* computed:
# ``01101101`` stands as a column at cell 24 under separator 2 at ``k == 15``.
# What fails is the carry -- no accumulator reads it intact, and from that
# staging it arrives as ``10011101`` or ``01100010``, neither the table nor
# its complement.  A sweep over 13 of the 15 (separator, settle) slices at
# ``k <= 40`` and every accumulator found no staging that delivers it; the two
# skipped slices scored worst on a cheap distance screen, and the five that
# scored best -- reaching Hamming distance 1 but never 0 -- were all covered
# and all missed.
#
# It is a gap in this family, not a wall: 180 of the 256 possible columns
# arrive across the family, and no affine invariant separates them from this
# one (all 255 parity masks checked), so nothing here forbids it.
#
# What closed the *other* gaps was not a better search but a wider separator
# set.  See the note on :data:`_SEPS`: the first two separators leave 126 of
# the 252 columns standing, and 112 of the 120 tables the searches could not
# reach did not stand as a column at all.  Three more separators carry 118 of
# those 120, every one of which builds, computes and emits in name order.
#
# The bracket axis is *exhausted*, not capped, and that is checkable rather
# than assumed.  Nothing in this language writes leftward -- ``[`` writes at
# ``ptr + 1`` and, on the cascade, ``ptr + 2``, and the pointer only ever
# advances -- so once every row's pointer has passed the accumulator window,
# no further bracket can change a staged column.  Measured, the columns stop
# changing between ``k == 25`` and ``k == 38`` depending on separator and
# settle count, so the sweep ran to 40 and anything past it is provably
# redundant.  The deepest first hit the enumeration actually needs is
# ``k == 26`` at three inputs and ``k == 6`` at two, where
# :data:`_MAX_BRACKETS` comes from; stopping at 30 would have been a cap
# rather than a bound.
#
# The other two axes were *sampled* rather than exhausted and came back
# empty -- settle counts 3 to 5 and accumulators 36 to 47 reached nothing the
# shipped stagings did not.  That is evidence they are barren, not proof.
#
# **A simpler form was looked for and does not exist.**  This is what the
# enumeration replaced a stored table with, and not what it could have been:
# the wish was a *uniform* rule -- one staging, or at least one field fewer --
# even at the cost of longer programs.  Every version of that was measured and
# fails, which is why all four fields are still enumerated:
#
# * **One fixed staging: impossible**, and by counting rather than by search.
#   A staging offers one column per accumulator and orientation -- 52 slots
#   over the ranges used here -- but those collapse badly, because the walk's
#   prefix-XOR is many-to-one and different accumulators keep arriving at the
#   same column.  Measured over every staging in the family, **the best
#   single one delivers 13 pairs and the mean is 5.8**, against 109 to place.
#   So this is short by a factor of eight, not marginally.
#
#   Nor is there a *cheap predictor* of which staging serves a table.
#   Measured on the full many-to-many relation (not on the first-hit
#   assignment, which is contaminated by separator 0 claiming everything it
#   reaches first): at four inputs no tested invariant yields a necessary
#   condition, every one of the ten (separator, settle) slices contributes
#   tables reachable nowhere else, and 72% of tables are served by exactly
#   one slice.  Hamming weight does predict a *rate* -- 78.4% reachable at
#   weight 2 and 14 against 18.8% at weight 8 -- but no weight class is
#   empty, so nothing licenses declining early.  See
#   ``docs/minifuck_generator.md``.
#
#   An earlier version of this note said the map "behaves like a hash" and
#   cannot be indexed at all, which overstated that evidence: it predates
#   the closed-form column algebra, and the algebra *inverts*.  Computing a
#   target's first pure-run staging directly -- per-row admissible-``k``
#   bitmasks read off the bracket staircase, intersected across rows, first
#   set bit in enumeration order -- reproduces the index exactly (all 252
#   keys at three inputs, 464 sampled pure-claimed keys at four, zero
#   mismatches).  What the measurements do support is *density*, not
#   opacity: the 4640 stagings collapse to about 4190 distinct plan
#   vectors, so there is no large many-to-one structure to exploit, a
#   per-table inversion of the insert family has no demonstrated
#   sub-sweep form, and the pure inversion runs ~20-30ms a table against a
#   0.4-0.75s whole-arity fill that then answers every table -- which is
#   why the tabulation stays.
# * **Two separators: 49 of 109.**  Re-measured; the figure here read 99,
#   which was wrong by more than half -- most likely copied from the settle
#   line directly below, whose 99 is correct.  The direction of the old
#   claim survives and is in fact stronger: two separators cover well under
#   half the population, so the stragglers need a different separator rather
#   than a longer program, which is why the enumeration walks all five.
# * **Dropping the settle field: 99 of 109.**  Confirmed.  Ten pairs are
#   reachable only at ``settle == 1``, so the staging cannot shrink to three
#   fields.
#
#   Both ablations are measured against :func:`_slices`, the enumeration the
#   index really walks.  Patching :func:`_stagings` instead measures nothing
#   -- it has no callers -- and reports the baseline as the ablation's own
#   result, which is a third instance of the false negative this module has
#   now produced twice before (see :func:`_staging_index` and the mux
#   sculpt).  ``_staging_index`` is cached, so a variant that does not clear
#   it reports the baseline for the same reason.
#
# Separator 0 is the one curiosity: no *three-input* table needs it, since
# separators 1 to 4 reach 108 of the 109 between them.  It is enumerated
# first anyway because it carries every two-input table on its own, and
# :data:`_SEP` and :data:`_SCAN_SEPS` use it.
#
# **What happened at four inputs, back when the searches were here.**
# Four-input AND and NAND build in 0.2s and a table depending on one input in
# 2.4s -- all before the staging, by the degenerate and projection routes.
# What the searches could not build was four-input XOR, and the diagnosis at
# the time was that the pool was fine and the search depth was the wall:
# XOR's failed attempt made 1016 pool lookups, 508 of them successful, the
# same one-in-two rate the three-input arity shows.
#
# That reading was right about the pool and incomplete about the wall.  XOR
# now builds from a staging, and the thing that had to change was neither the
# search nor the pool but the *suffix*: with ``'[' * k`` the only spelling
# available, the enumeration could not reach it.  See :data:`_STAGED_ARITIES`
# and :func:`_insert_suffixes`.  The searches remain what the other 76% of
# the arity falls through to, and the depth is still their limit.
#
# Which code answers does shift with arity, which is worth knowing before
# trimming the list on three-input evidence.  On the four-input tables measured
# here, sixteen-row joints were served by the third and fifth codes, and the
# fifth answers almost nothing below four inputs -- so an ablation at
# ``n <= 3`` under-reports what it is for.  The split is table-dependent and
# the sample is small: the sites from a four-input AND were answered by the
# fifth code alone, while the failing XOR's were answered by both.  Take this
# as "arity changes which code answers", not as a census.

# The arities the enumeration covers.  Two and three are *total*; four and
# five are partial, and are here because partial beats the fall-through each
# replaces.  Beyond five the gate stays explicit rather than implied by a
# miss: it is not that the enumeration is known to fail there, but that it
# has not been shown to succeed, and this list is the place that claim is
# made.
#
# Five was gated shut on exactly that wording until the family was harvested
# at that arity, which is the measurement that opened it: 24582
# fully-essential 32-bit columns, complement-closed, five-input XOR among
# them.  It is a 0.00057% slice rather than four inputs' quarter, and it
# ships on the same argument -- a miss falls through, so admitting the arity
# cannot cost coverage.  The one thing that had to change to make it runnable
# at all is that :func:`_derived_plans` is asked for the tables it wants
# rather than for the whole arity.
#
# Four inputs is gated on measurement rather than hope: the insert family
# below reaches 15404 of the 64594 fully-essential four-input tables (23.9%),
# four-input XOR among them -- the table the searches are recorded as failing
# on.  A table the derivation misses still falls through to the searches, so
# admitting the arity cannot cost *coverage*.
#
# What it costs is time, and the shape of that cost is worth stating plainly
# because it is unlike the other arities.  At two and three inputs the
# derivation stops early: every table is placed, so ``remaining`` reaches
# zero partway through.  At four it never can -- 76% of the arity is
# unreachable -- so the enumeration always runs to its caps, measured at
# about 76 seconds.  That is paid by the first fully-essential four-input
# table in a process whether it hits or misses, and :func:`_derived_plans` is
# cached, so it is paid once.  Constants, projections and any table with an
# ignored input are answered by the degenerate and projection routes in
# :func:`minifuck` before the staging is consulted at all, and never pay it.
#
# The caps are not slack that could shorten this.  Coverage climbs to both of
# them -- suffixes to ``k == 28`` and accumulators to 34 -- with 12256 tables
# at ``k <= 24`` against 15404 at 28, so a trim to buy time is a trim to
# coverage.  ``_stagings`` takes ``n`` for arity-dependent caps; measurement
# says this arity wants the full ones.
_STAGED_ARITIES = (2, 3, 4, 5)

# How far the enumeration runs.  Both caps are the measured maximum over
# every table plus a margin, not guesses: sweeping to a bracket count of 30
# and an accumulator of 40, the deepest first hit at two inputs is
# ``(k=6, acc=20)`` and at three ``(k=26, acc=31)``.  Nothing is reached past
# those, so the sweep stops a little beyond them.
_MAX_BRACKETS = 28
_MAX_ACC = 34

# Only the *upper* ends are measured.  Every accumulator loop in this module
# starts at :data:`_PROBE_WALK_OUT` rather than at a literal, because the
# lower end is not a search bound at all: an accumulator has to sit past the
# pool, which :func:`_endgame` enforces by refusing anything under
# :data:`_POOL_WIDTH`, so the first one worth asking about is one further
# right.  The counts spelled ``_MAX_ACC - _POOL_WIDTH`` are the same fact
# said the other way round -- they are the length of that loop.

# How much of the enumeration a caller is willing to spend, counted in
# **stagings visited** rather than in seconds.
#
# The unit is the point.  A wall-clock budget would make the generator
# non-deterministic across machines: the same table would build on a fast
# host and raise on a slow one, and the template a table gets would depend
# on how loaded the box was.  A staging is one ``(separator, settle,
# suffix, accumulator)`` tuple in :func:`_stagings` order, so counting them
# is identical everywhere -- a budget picks out the *same* set of tables on
# a Raspberry Pi and on an M3, and the emitted programs stay byte-identical.
# The count also tracks real work: :func:`_column_sweep` derives a staging's
# whole accumulator range from one walk, making a visited staging roughly a
# constant unit.
#
# **A budget costs program length, not coverage.**  A table the budget stops
# short of falls through to :func:`_mux`, which is total at four inputs at
# about 11ms -- so lowering this cannot make a table unbuildable.  What it
# trades is the staged route's much shorter template (measured at four
# inputs: 205 characters against the sculpted route's 952) for the tables it
# gives up.  That is why a slow host can lower it safely.
#
# ``None`` means no budget, which is what ships at four inputs and below:
# the default must reproduce the enumeration exactly there, or every
# recorded template changes.
_STAGING_BUDGET: int | None = None

# Five inputs used to ship a budget of 30000 stagings, and the reason it no
# longer does is that its rationale was consumed by the tabulation.  The
# argument was that the arity is only reached by tables the cheaper routes
# could not place, and that "the enumeration cannot stop early on a miss" --
# so a miss paid the whole sweep, a measured 54.7 seconds.  A miss is now a
# dict lookup: :func:`_staging_index` walks the enumeration once per arity,
# and after that neither a hit nor a miss enumerates anything.
#
# So the budget bought nothing but lost coverage.  Measured: the budgeted
# pass is 2.4s and reaches 6340 columns, the full pass 8.5s and 28096 --
# **21756 more**, for six seconds once per process.  And the two agree
# wherever they overlap: every column both reach gets the *same* staging,
# because a budget truncates the enumeration without reordering it, so
# lifting it cannot change a template that already existed.
#
# What it does change is coverage, which is why it is a deliberate,
# separately-verified step rather than a tidy-up: tables that sat late in the
# enumeration went from a raise to a build.  Sampled 20 of the newly reached
# and every one builds and prints all 32 rows on the shipped interpreter.
#
# ``None`` means no budget, which is now what ships at every arity.
_STAGING_BUDGET_N5: int | None = None


def _budget(n: int) -> int | None:
    """Return the staging budget for this arity, in stagings visited."""
    if n >= 5 and _STAGING_BUDGET is None:
        return _STAGING_BUDGET_N5
    return _STAGING_BUDGET


# The ``(separator, settle)`` slices in descending measured yield at four
# inputs, which is what makes a budget worth having.  Every slice costs the
# same 12064 stagings, and what they return is not close to even -- 2874
# tables for the best against 424 for the worst -- so spending a budget in
# this order buys 77% of the hits for half the work, and 91% for 70% of it.
# Enumerating in the plain ``(sep, settle)`` order instead makes a budget a
# flat trade, since hits are spread uniformly through the enumeration.
#
# Measured at ``n == 4`` and **not** assumed to hold elsewhere: at another
# arity the ranking is unmeasured, so the full enumeration order is used
# unless a budget is actually set.  Ordering only matters when something is
# going to be given up.
#
# The yield is *marginal*: a slice is credited with the columns it is first
# to reach walking the plain enumeration, not with every column it could
# place alone -- ranking by independent reach gives a different order.  So
# this is derived rather than frozen, and
# ``test_the_slice_order_is_its_measured_yield`` re-derives it from
# ``_staging_index(4)`` each run instead of trusting the numbers above.  All
# ten counts differ, so descending order is total with no tie-break.
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


# The arities whose enumeration includes the insert family below.  It is not
# offered at two or three inputs because the pure runs already close those
# arities completely, and enumerating a family that can only be reached after
# every pure run has missed would cost those arities time for nothing.
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


# The insert family, materialized once: the constraint query needs to hand
# a winning ordinal back as its suffix string, and the family is 435 short
# strings.  :func:`_insert_suffixes` stays the specification of the order.
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

    # What each printed column would answer.  A table and its complement
    # share a staging, so both spellings map to their own table and whichever
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

    # Stagings visited, against :data:`_STAGING_BUDGET`.  Counted per
    # accumulator sweep rather than per emitted suffix, because a staging is
    # a ``(separator, settle, suffix, accumulator)`` tuple and ``claim``
    # walks the accumulators for one suffix in a single call.
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
            # Extending the run is what makes this cheap: the next
            # bracket count is one instruction on from this one, not a
            # rebuild from the embed.
            run.emit("[")

    # The insert family, in a second pass so that every pure run is tried
    # first and the arities the pure runs close keep the stagings they had.
    # This pass cannot share the incremental trick above -- moving the ``<``
    # one place right is not one instruction on from the last suffix -- so
    # each string is emitted onto a fork of the embed.
    if n not in _INSERT_ARITIES:
        return found
    for sep_index, settle in slices:
        # Never taken, and kept for symmetry with the loop above rather than
        # as a live exit: every `spent += accs` is immediately followed by
        # its own `exhausted()` that returns, so no spend happens between
        # that check and this one -- a budget that would stop the pass has
        # already stopped it inside the body.  Measured over nine budgets
        # spanning the insert pass (7540, where it is entered, to 120640,
        # the whole enumeration): evaluated 35 times, taken 0.
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


# **A linear-algebra screen sat here, and it is gone.**  Everything the
# endgame emits after the suffix is GF(2)-affine in the columns standing at
# that point, so a printed column lies in the span of the staging's standing
# columns, and ``_span_admits`` used that to decline unreachable five-input
# tables before the per-table enumeration -- 3.6 milliseconds against the
# 143 seconds a doomed sweep cost.  The index inversion made both numbers
# obsolete: the arity is tabulated once and a miss is a dict lookup, so the
# screen's only remaining effect was its own setup -- a measured 0.72s of
# span bases against the 0.88s index build it could at best skip, paid by
# every process that built any staged five-input table.  Equivalence at
# removal: an index key is a printed column and the screen admitted every
# printed column by its own standing test, so screen-then-lookup and bare
# lookup answer identically -- checked directly, 400 sampled keys with 0
# declines and 120 tables with 0 divergences.  The affine-span fact stays
# true; nothing consumes it any more.


# How far right the closed-form column derivation tracks the tape.  The
# deepest read is one cell past an insert's phase-two extent, and an extent
# is bounded by the instruction budget: a suffix carries at most
# ``_MAX_BRACKETS`` brackets, plus one instruction's credit when a pending
# skip hands its job to the ``<``, so nothing settles past
# ``_BASE - 1 + _MAX_BRACKETS + 1`` and the reads stop two cells later.
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
        # The one cell below ``_BASE`` a suffix can touch: a ``cut == 0``
        # insert steps back onto it before its brackets run.
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


# What a row does under one suffix, reduced to five ints so the per-``acc``
# read below is arithmetic.  ``mode`` 0 is a pure run (extent, saturated
# read); 1 is a pure run plus a point flip at the re-crossed cell; 2 is the
# complemented chain, which no pure run reproduces.
_Plan = tuple[int, int, int, int, int]

# Per orientation: the pool's landing pointer, the low cells' full XOR, and
# the per-accumulator partial XOR for reads that stop below ``_BASE`` --
# or None where no pool code fits the orientation.
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
            carry_cell ^= v[c]  # phase one already carried v_c into c + 1
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
    # The saturated arm's parity term is ``(acc - _BASE + 1) & 1``; adding
    # the constant to the offset flips which of the two values it takes,
    # which is exactly XORing it, so no arm pays for the fold.
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
        # The whole slice-constant treatment of the pool rests on this, so a
        # violation is a bug in the embed model, not a case to handle.
        # Measured over every slice at two, three and four inputs: zero
        # violations, which is why the raise is never reached -- the check
        # stays because the property belongs to the embed, not to anything
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
    # The plans are the suffix's whole per-row response and cost nothing to
    # share, but only one orientation ever has a pool: ``_find_pool`` answers
    # ``cell7 == 1`` with None at every staged arity and every slice (40 of
    # 40, measured), so the region walk below runs once per suffix, not twice,
    # and hoisting it out of the loop would buy nothing.
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
                # Mirrors _column_sweep's guard; the pool lands at 4 or 5,
                # below the accumulator range, so it never fires.
                continue  # pragma: no cover - the pool lands below the range
            bit = lowxor[acc] ^ (lflip if acc == _BASE - 1 else 0)
            columns[acc] = (bit,) * len(chains)
        # The accumulators at ``_BASE`` and above, batched: one region walk
        # per row rather than one plan dispatch per (row, accumulator), and
        # the row-major bits transposed to columns at the C level.
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

    # The slice states are built once and shared by both passes: the second
    # pass reads the same embeds, and nothing between the passes writes them.
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
        # Never taken, for the same reason as the oracle's copy of this
        # loop: the spend inside the body is followed immediately by its own
        # `exhausted()` return, so nothing accrues across the loop boundary.
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


# One pass's constraint masks for a slice, keyed by ``(cell7, acc)``: the
# suffixes whose sweep reaches that pair at all, and, per row, the suffixes
# under which the row's printed bit is 1 for the direct read.
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


# **The flipped-embed pass was here, and it is gone.**  It complemented some
# inputs as they landed, which took four inputs from 23.9% to 94.35% -- a real
# gain at the time, and dead weight now.  Every table it placed is a table the
# plain enumeration missed, and :func:`_mux` builds all 49190 of those (swept
# exhaustively, not sampled), so nothing reached it that the sculpted route
# does not reach.  Nor was it a fallback for another arity: it was gated to
# four inputs alone, which the sculpted route also covers.
#
# What it cost was the whole-arity sweep behind it -- over 300 seconds, paid
# by the first four-input table to miss the stagings, against about 11ms for
# the same table through :func:`_mux`.  Deleting it takes that miss from
# minutes to the sculpted route's own derivation.
#
# The trade is program length: the flipped pass emitted shorter templates for
# the tables it placed, and those tables now get the sculpted route's longer
# ones.  Taken deliberately -- a shorter program is not worth minutes to
# compute -- and paid only by tables the plain enumeration already missed.
#
# The route trades longer output for a much faster build.


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


# ---------------------------------------------------------------------------
# The sculpted route: separate every row into its own pointer position, then
# fix the printed column one row at a time, from the highest position down.
#
# This is the construction that closes the four-input residue, and it embeds
# each input **exactly once** -- the repo-wide rule every parameterized
# generator holds to (see ``docs/limitations.md``) is kept, not carved out.
# The observation it stands on is that the embed already put the whole row
# identity on the tape: ``_embed``'s walk transform is affine and invertible,
# so after the embed no two rows are in the same state, and converting that
# state difference into a *pointer* difference needs reads of what is already
# there, never another copy of an input.
#
# **Separation** is that conversion, and it is *constructed* -- closed form in
# ``n``, no search anywhere.  Weight each input as it lands, so the pointer
# ends holding the row's binary expansion:
#
#     for i in range(n):
#         setter(i); weight(2**(n-1-i)); pad
#
# :func:`_mux_weight` is what makes a bit worth more than one step.  A
# restoring read ``[x<[<`` displaces by the bit and puts the cell back, so it
# can be read again; ``k`` of them with a one-cell rewind between compound to
# exactly ``-k`` times the bit -- measured linear for ``k`` of 1 to 8.  The
# pointer therefore lands at ``c0 - sum(2**(n-1-i) * x_i)``, which is affine
# in the inputs and injective by binary expansion: all ``2**n`` rows are
# separated by construction, and nothing has to be searched for or checked
# row by row.
#
# Two conditions make the weights compose, and both were found by measuring
# rather than by argument:
#
# * the bit must be **fresh**.  One ``[x`` between the setter and the gadget
#   folds the bit into the running prefix-XOR, and every weight collapses
#   to 1 -- which is exactly what an earlier per-setter attempt measured and
#   read as a wall.  Once the displacement is banked in the pointer, though,
#   arbitrary rightward padding preserves it (measured pad 0 to 10).
# * gadgets must not reach into each other.  Weight ``k`` writes at most
#   ``k - 3`` cells left of its setter, so :func:`_mux_pad` puts that much
#   clear air plus the room the deepest rewind needs above cell 0.  The
#   threshold ``2**(n-2) - 1`` is sharp -- below it the weights are still
#   exactly right and the misses are rows clamping at the tape floor.
#
# This replaces four searches (a pointer-census BFS, a greedy pass over aimed
# reads, a beam over aimed-read sequences, and a two-machine BFS on one
# colliding pair).  They cost 2.8s at three inputs and 15.0s at four, and
# failed outright at five after 191 seconds; the construction is 0.0007s at
# four and 0.004s at five.
#
# It also corrects what this comment used to claim.  "Reading a bit as it
# lands does not help and cannot" was measured over a *stale* bit -- the
# setter-read unit is shift-invariant over the uniform wake only once a walk
# has crossed the bit.  Read while fresh and sandboxed, it is the whole
# construction.
#
# **Sculpting** then edits the separated rows individually.  Fix a target
# cell ``C`` below every row.  One round ``'<' * K + '[x' * K`` with
# ``K = b - C + 1`` has three provable effects:
#
# * the row at position ``b`` rewinds to ``C - 1`` and its first landing is
#   ``C`` -- an *unconditional* flip, nothing crossed before it, so the flip
#   is clean whatever that row's tape holds;
# * a row above ``b`` starts its walk right of ``C`` and writes nothing below
#   its own rewind point, so its cells at and left of ``C`` -- and therefore
#   the value the endgame will read for it -- are untouched;
# * rows below ``b`` cross ``C`` on the way back and pick up value-dependent
#   cascade debris from crossing ``C - 1``: scrambled, not controlled.
#
# So repeatedly fixing the *highest* disagreeing row strictly lowers the
# frontier, and the loop lands in at most ``2**n`` rounds.  What used to be
# the one non-structural residue -- the pool code, re-derived each round,
# where a state-driven switch could in principle have disturbed a fixed row
# through the walkout -- is now closed by name: the probe state is canonical
# at every round, so the code is a constant and cannot switch.  See
# :data:`_SCULPT_POOL_CODE`.  The loop keeps its allowance and its
# fall-through anyway, because they cost nothing and the cap is what makes
# "a stall returns None" true.  The trailing ``x`` on every round is
# the ``_FLIP`` lesson again: a walk whose last ``[`` cascades leaves the
# skip flag set, and the next instruction must be one the program can afford
# to lose.
#
# **Coverage and cost, measured.**  All 3652 four-input tables the staged
# families miss build through this route and print all 16 rows correctly on
# the shipped interpreter, at one program width per table and with the slots
# in name order -- which closes the arity: 64594 of 64594.  The arity's
# separation, which used to be a 15-17s search, is now 0.0007s of
# construction.
#
# **A build costs about 220ms and buys a 43% shorter program.**  It used to
# cost 7ms by returning the first ``(C, orientation, read)`` that printed;
# it now sculpts all of them and keeps the shortest, because the accumulator
# sets the price of every round -- a round is ``3 * K + 1`` characters for a
# rewind of ``K = frontier - C + 1`` -- and the first is a poor choice.
# Measured over sampled four-input tables: first-ascending 1046 characters,
# first-descending 700, minimum over all 594.  At five inputs the same change
# takes XOR5 from 2511 characters to 1174.  Two probe savings pay part of the
# extra work back (a hint carried between rounds, and scanning the pool codes
# at the fixed probe distance rather than at the caller's accumulator), and
# both are verified to leave the emitted template byte for byte identical.
#
# **The arity gate is gone entirely.**  This section used to say five was
# absent because no derivation had separated 32 rows -- the searches ran 191
# seconds and failed, always stalling on pairs differing in the first input.
# The constructed separation above does it in 0.004s, and the rest of the
# route was never arity-specific.  That first lifted five; what has since
# replaced the tuple with :data:`_MUX_MIN_ARITY` is that "nothing in the
# construction is aware of ``n``" stopped being an observation and became an
# argument: every one of the route's six refusal sites closes uniformly in
# ``n`` (``docs/minifuck_generator.md``, "Is ``_mux`` total?").  Sampled end to end: 200
# of 200 fully-essential five-input tables build and print all 32 rows
# correctly on the shipped interpreter, five-input XOR among them, at about
# 0.14s each.  Six inputs is the arity the gate used to refuse and it builds
# the same way: the two tables that raised in 0.000s before the lift emit 4040
# and 3993 characters in 41.6s and 53.8s, and a fixed fully-essential table
# prints all 64 rows on the shipped interpreter in
# :meth:`test_no_arity_is_gated`.  ``docs/minifuck_generator.md`` carries the wider run,
# 448 of 448 rows correct at five, six and seven inputs.
#
# The route sits *after* the staged families in :func:`_solve`, so every
# table they already build keeps its template byte for byte.  It is the last
# route: the searches that used to sit behind it are gone, so a table it
# cannot build -- a pool code refusing every ``(C, orientation, read)`` --
# raises rather than sweeping.

# Where the sculpted route embeds, and how much of the tape to its left the
# separation searches must not write.  The pool codes were designed against
# the uniform wake ``_walk_to`` leaves and their marks reach to about cell
# fourteen, so a separation that scribbles there strands every probe --
# measured, 0 usable pool probes against 14 with the region intact.  Eight
# cells between the guard and the embed are deliberately left writable:
# scratch there is what lets the searches finish, and sealing it turns the
# four-input separation from a 15-second derivation into a failure.
_MUX_BASE = _BASE + 16
_MUX_GUARD = _MUX_BASE - 8

# The lowest arity the route is offered.  There is no upper bound: this used
# to be a tuple ``(2, 3, 4, 5)`` recording the arities that had been
# *verified*, and the route declined outside it in 0.0s -- a configuration
# gate, not a construction that failed.  ``docs/minifuck_generator.md`` ("Is ``_mux``
# total?") now closes all six of the route's ``None``-sites with arguments
# that carry no residual ``n``: the separation is affine and injective by the
# constant 24-cell saturation margin plus the strict non-overlap the halving
# weights give, the rewind guard is an algebraic identity, the round cap is
# window geometry, and the pool probe reads only cells the initial walk
# freezes to one value at every arity.  So the gate was the last thing making
# the generator partial, and it is gone.
#
# Two is the floor because ``_solve`` routes constants and single-input
# projections to :func:`_degenerate` before ever reaching here; the route
# itself has no arity-specific step at all.
_MUX_MIN_ARITY = 2

# One derived separation per arity, handed out as forks.  A plain dict
# rather than ``lru_cache`` because the value is a mutable ``_Joint``.
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
        j.emit(_mux_weight(k))
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # The construction is derived, but it is still *checked* before it is
    # cached: a separation that quietly lost a row would be found by the
    # sculpting loop as an unfixable table rather than as a bad separation.
    #
    # Neither check fires at any arity -- which is the point of deriving the
    # separation rather than searching for one, and is argued uniformly in
    # `n` in ``docs/minifuck_generator.md`` under "Is ``_mux`` total?" -- so
    # both refusals are the guard against a future weighting that breaks the
    # construction, not a live path.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None  # pragma: no cover - the construction separates by design
    if not _mux_intact(_mux_reference(n), j):
        return None  # pragma: no cover - the construction separates by design
    _MUX_SEPARATED[n] = j.fork()
    return j


#: Which pool code a *sculpting* probe reaches, named rather than searched.
#:
#: The scan this replaces was re-deriving a constant.  The verdict is fixed
#: by the construction, in three steps:
#:
#: * **The probe state is canonical.**  :func:`_mux_probe` emits ``x`` to
#:   absorb a pending skip and then :func:`_clamp`\ s, and ``<`` never
#:   writes -- so every probe, at every round of every sculpt, asks about
#:   rows whose pointers are all 0, with no skip and no dead row, and whose
#:   pool region is ``(0, 1, 1, 1, 1, 1, 1, 1)``.  Measured as one state per
#:   ``cell7``: exhaustive at ``n == 3`` (256 tables, 50688 probes), 200
#:   sampled at four and 12 at five -- 2 distinct full states in all, which
#:   are the two values of ``cell7`` and nothing else.
#: * **Nothing outside the pool region can matter.**  Running any pool code
#:   from that state touches at most cell 6, inside the 8-wide region the
#:   verdict reads, so the region *is* the whole input to the question.
#: * **A sculpt cannot disturb it.**  A round rewinds by ``K`` under the
#:   guard ``rewind > min(ptrs) - _POOL_WIDTH``, so it never writes into the
#:   region, and the next round re-clamps to the same state.
#:
#: So the answer is a constant of the arity-free construction, not a
#: property of the table: the fifth code answers ``cell7 == 0`` at every
#: accumulator and every round, and ``cell7 == 1`` is answered by none.  That
#: is what the ``hint`` parameter was observing when it measured "zero
#: switches" -- the hint never switched because it never could.
#:
#: **What this is worth, measured rather than inherited.**  The roadmap
#: entry that opened this frontier read "14.5s of a 17.9s warm five-input
#: build" as the cost of the *scan*.  That was cumulative time in
#: :func:`_mux_probe`, and the scan was the smaller half of it: the ``hint``
#: already skipped the list on all but the first round, so naming the code
#: takes a warm five-input build from ~3.1s to ~2.8s, about 10%.  Profiled
#: when that landed, :func:`_pool_reaches` was 3% of a build and every call
#: left came from :func:`_find_pool` on the derivation path; those calls are
#: gone now that the derivation path looks the code up too, and
#: :func:`_pool_reaches` runs only when a slice is first derived and in the
#: tests -- never on a build's own path.  The rest of
#: :func:`_mux_probe` is the *column derivation* -- the walk and clamp over
#: every row, once a round -- which is a different question from which code
#: to use and is not closed by this constant.
#:
#: So the value here is the rule, not the seconds: the search is gone, and
#: what remains is arithmetic the module was always going to do.
#:
#: This is the sculpting probe only, and it is now the special case of a
#: general rule rather than the one closed corner: :func:`_find_pool` asks the
#: same question of the *derivation* path, whose joints are not clamped to this
#: state, and answers it by :data:`_POOL_CODE_OF` without a scan either.  This
#: constant stays because the sculpting probe's state is known at import, so
#: naming the code costs nothing at all; the general path needs the lookup.
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
    if frames[0] != frames[1]:
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
    probe.emit("x")  # absorb a pending skip so the clamp below is exact
    _clamp(probe)
    code = _sculpt_pool_code(cell7)
    if code is None:
        return None
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed; as _printed_column
        # Same shape, and same caveat, as the copy in `_printed_column`: a
        # pool code that fits the site does not by itself promise the walk,
        # because `_find_pool` ignores `walk_out`.  Not observed over 38144
        # sculpting rounds at two and three inputs.
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
            # Not observed, but the closest of any guard here: measured over
            # every table at two and three inputs, 38144 rewinds with a
            # margin (bound minus rewind) between 0 and 24 -- so the padding
            # `_mux_separate` leaves is exactly enough at its tightest, and
            # nothing about the construction makes it *more* than enough.
            # This is the guard a change to either side would trip first.
            return None  # pragma: no cover - not observed; margin reaches 0
        # Emitted as three runs rather than one concatenated string.  The
        # template is ``"".join(parts)`` either way, so the program is
        # unchanged -- but a mixed string has no closed form, and this is
        # the loop's hot path: split, the rewind's two long runs go through
        # `_Sim.run_left` and `_Sim.run_walk` instead of being stepped one
        # character at a time per row.
        j.emit("<" * rewind)
        j.emit("[x" * rewind)
        j.emit("x")
    else:
        # The loop runs `2**n + 4` rounds and each fixes at least the
        # frontier row, so a table that needs more rounds than it has rows
        # would be one where a round undid an earlier fix.  Not observed
        # over every table at two and three inputs; kept because "stall
        # returns None rather than looping" is the contract this else is.
        return None  # pragma: no cover - a round never undoes an earlier fix
    j.emit("x")
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return None if hit is None else hit.template()


# Bit-reversal per byte, for reversing a row's tape about its pointer.
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
    base: _Joint, truth_table: str, n: int, accs: range
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
    # What `_try_print` will do from the sculpted state: per orientation,
    # the pool code `_find_pool` names there, where it lands, and the parity
    # its walk out carries -- None when no code answers, which is that
    # orientation's `_derive_column` returning None.
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
    # Each row's tape reversed about its own pointer -- bit ``j`` is cell
    # ``ptr - j`` -- so every row's rewind window is its low ``K`` bits
    # whatever its pointer, the prefix XOR runs as maskless right shifts,
    # and the parity delta is a shift and a popcount.  Built once: the
    # combinations all start from this state, and ints never mutate.
    base_tapes = [_rev_bits(ms[r].tape, ptrs[r] + 1) for r in order]
    base_len = len(base.template())
    guard = lowest - _POOL_WIDTH
    cap = 2**n + 4
    checked = False
    best: int | None = None
    lengths: dict[tuple[int, bool], int] = {}
    # Scouted largest accumulator first: rounds cost ``3 * K + 1`` with
    # ``K = frontier - acc + 1``, so the cheap builds sit at the top and
    # pricing them first is what lets the strict-abort prune the expensive
    # bottom after a handful of rounds.  The order prices; it never picks.
    parities: list[int] | None = None
    for acc in reversed(accs):
        # Each row's parity over cells ``8..acc`` of the *base* state --
        # cells ``8..acc`` of a reversed row start ``ptr - acc`` bits up and
        # run ``acc - 7`` wide.  Walked down one accumulator at a time: the
        # window loses its top cell, so the parity flips by that one bit.
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
            # `_try_print`'s own trial order, decided by the constants: a
            # read matches when its polarity cancels the constant offset
            # between the probe's parity and the endgame code's.
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
                # No read prints this orientation: the sculpt would run its
                # rounds and then `_try_print` would refuse.  Same outcome.
                continue
            read, (code_len, landed, _) = matched
            # Everything the sculpt emits outside its rounds, priced up
            # front: the trailing ``x``, the clamp, then the endgame's pool
            # code, walk out, read, rewind to the pool, and ``[x.``.
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
            # Rounds reach a row lazily, when the frontier scan reads it.
            # The scan never revisits a row -- one that agrees is settled
            # (rows above the frontier keep their parity, the invariant
            # above) and one that disagrees is the frontier, whose fix is
            # the round itself -- so each row replays the rounds pending at
            # its one examination, and rows below wherever a combination is
            # abandoned never pay for the rounds above them at all.
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
            else:
                aborted = True
            if not aborted:
                lengths[(acc, direct)] = total
                if best is None or total < best:
                    best = total
    if best is None:
        return None, True
    for acc in accs:
        for direct in (True, False):
            if lengths.get((acc, direct)) == best:
                return (acc, direct, best), True
    raise AssertionError("the scout lost its own winner")  # pragma: no cover


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
    """
    if n < _MUX_MIN_ARITY:
        return None
    base = _mux_separate(n)
    if base is None:
        # `_mux_separate` refuses only through its own two guards, which the
        # construction does not trip at any arity -- see the pragmas there.
        # This is that refusal reaching its caller.
        return None  # pragma: no cover - the separation never refuses
    positions = base.ptrs()
    lowest, highest = min(positions), max(positions)
    # ``+ 1`` past the rewind guard's ``_POOL_WIDTH``, which is what makes the
    # guard exactly tight rather than slack -- see the constant's own comment.
    accs = range(highest - lowest + _POOL_WIDTH + 1, lowest - 1)
    winner, trusted = _mux_scout(base, truth_table, n, accs)
    if not trusted:
        # The separation's state defeats the shadow's summary: not observed
        # at any arity -- the base is canonical by construction -- so this
        # is the guard against a future separation the scout cannot price.
        return _mux_sweep(base, truth_table, n, accs)
    if winner is None:
        return None
    acc, direct, predicted = winner
    built = _mux_sculpt(
        base, truth_table, n, acc, 0, direct=direct, hint=_SCULPT_POOL_CODE
    )
    if built is None or len(built) != predicted:
        # The shadow and the sculpt disagreeing is a bug in the pair; the
        # sweep is the exact spelling, so answer from it rather than raise
        # -- the build that returns is still one `_try_print` accepted.
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

    # A table that ignores some of its inputs is a *smaller* table wearing
    # extra ones, so solve it at the arity it actually uses and renumber the
    # placeholders back.  This is the part of the construction that composes:
    # what it costs depends on the essential inputs, not on ``n``, so a wide
    # table with a narrow core is as cheap as that core.
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projecting is much the cheaper route, but it emits the ignored
        # inputs after the ``.``, which leaves name order whenever an ignored
        # index sits below an essential one.  ``_embed`` already lays every
        # slot down in ascending order, so solving at the *full* arity is
        # in-order by construction -- try it first for exactly the tables the
        # lift would disorder, and only when it is the cheap closed-form
        # path.  A table with two or more essential inputs is not: measured
        # at n == 3, ``00000101`` ran the old searches for 132 seconds and
        # still failed, against seconds to project.  Coverage comes first, so
        # a miss here falls through to the projection rather than raising.
        # The attempt is a fixed-cell lookup, which is where every table it
        # wins is won; the column search that used to sit behind it is gone,
        # so this is cheap by construction rather than by a flag.
        if _lift_leaves_name_order(essential, n):
            if len(essential) <= 1:
                in_order = _degenerate(truth_table, n)
                if in_order is not None:
                    return in_order
            reconverged = _reconverged(truth_table, essential, n)
            if reconverged is not None:
                return reconverged
            # **The last ten out-of-order tables are sorted here.**
            #
            # Ten three-input tables used to emit ``{X0}{X2}{X1}``, all with
            # the same shape: the ignored input is the *middle* one.  The two
            # routes above cannot sort those -- emitting the ignored setter
            # first does not help when it already follows ``{X0}``, and
            # reconvergence drives every row to one state, so it cannot
            # collapse ``x1`` while preserving ``x0``.  Searched to depth 14,
            # no reset exists.  The comment that recorded this closed with
            # "sorting those needs the solver to assign names".
            #
            # It does not.  :func:`_mux` lays every slot down in ascending
            # order at the *full* arity and never projects, so it emits in
            # name order by construction -- and it does not care that the
            # table ignores an input, because it sculpts the printed column
            # row by row rather than reading a column the ignored bit would
            # have disturbed.  Measured: all ten come back ascending and
            # print every row correctly on the shipped interpreter.
            #
            # It goes *after* the two cheap routes because it is the more
            # expensive one and they already sort everything they reach; what
            # is left here is exactly the residue they cannot.
            sculpted = _mux(truth_table, n)
            if sculpted is not None:
                return sculpted
        inner = _solve(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input means a constant or a (negated) projection,
    # and the embed already holds every one of those as a column -- so the
    # answer is a cell lookup rather than a search.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # A planned staging is the cheapest route by far, so it goes first.  Two
    # and three inputs are both complete -- the enumeration closes two, and
    # the enumeration plus the sculpted route closes three -- so nothing ever
    # runs below four inputs.  A miss at a wider arity falls through to the
    # searches below.
    derived = _staged(truth_table, n)
    if derived is not None:
        return derived

    # The sculpted route: it closes four inputs (all 3652 tables the staged
    # families miss, interpreter-verified) at milliseconds a table, and it is
    # the last route -- **it is expected to build every table at every
    # arity**, so the raise below is a guard rather than a branch the
    # generator is meant to take.
    sculpted = _mux(truth_table, n)
    if sculpted is not None:
        return sculpted

    # **Reaching this is a bug, not a refusal.**
    #
    # This used to be a deliberate cost gate.  The column and parked searches
    # sat at this point; at ``n >= 5`` they were reachable and *unbounded* (a
    # five-input table the staged enumeration cannot place ran past a
    # 240-second cap and was still going), so they turned a fast failure into
    # an indefinite one.  Deleting them made a miss raise at once, and the
    # comment here recorded that as a trade of coverage for bounded cost:
    # "the tables it refuses are unreached, not unbuildable".
    #
    # There are no such tables left.  :func:`_mux` carried an arity gate at
    # the time, so everything above five landed here; that gate is gone (see
    # :data:`_MUX_MIN_ARITY`), and every one of the route's six ``None``-sites
    # closes by an argument uniform in ``n`` -- ``docs/minifuck_generator.md``, "Is
    # ``_mux`` total?".  So the generator is total: this raise says the
    # totality argument has been broken by a change, and the message names the
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


# The construction's cache and its undecorated body live on ``_solve`` now,
# but tests and callers reach for them through the public name: keep
# ``cache_clear``/``cache_info`` and ``__wrapped__`` here so splitting the
# arity check off did not move the surface.
minifuck.cache_clear = _solve.cache_clear  # type: ignore[attr-defined]
minifuck.cache_info = _solve.cache_info  # type: ignore[attr-defined]
minifuck.__wrapped__ = _solve.__wrapped__  # type: ignore[attr-defined]
