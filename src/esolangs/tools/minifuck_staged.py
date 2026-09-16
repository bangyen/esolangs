"""The Minifuck staged route: derive one staging per complement pair.

A plain run of brackets sweeps the embed's affine picture forward, exposing a
different function at each step, so a table is built by the first
``(separator, settle, suffix, accumulator)`` in :func:`_stagings` order that
prints it.  Total at two and three inputs, partial at four and five.
"""

from bisect import bisect_left
from collections.abc import Callable, Iterator
from functools import cache

from esolangs.tools.minifuck_pool import (
    _BASE,
    _POOL_WIDTH,
    _PRINTED_COLUMNS,
    _PROBE_WALK_OUT,
    _READS,
    _SEPS,
    _complement,
    _confirm,
    _embed,
    _find_pool,
    _try_print,
)
from esolangs.tools.minifuck_sim import _clamp, _Joint, _walk_to


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


# The staged construction: one ``(separator, settle, suffix, accumulator)``
# per complement pair, *derived* rather than stored.
#
# The embed leaves an affine picture -- every cell holds a linear form in the
# input bits plus the one nonlinear term the ``[`` cascade computes -- and a
# plain run of ``k`` brackets from ``_BASE - 1`` sweeps that picture forward,
# exposing a different function at each step.  So the whole problem is: pick
# the separator, the bracket count and the accumulator, then hand the result
# to the endgame every other route already uses.  That is small enough to
# *enumerate*: :func:`_stagings` gives the order -- 5 separators x 2 settle
# counts x 29 bracket counts x 26 accumulators -- and a table is built by the
# first entry that prints it.
#
# :func:`_derived_plans` runs that enumeration for a whole arity at once,
# which is what makes it affordable.  A staging is expensive to build and
# cheap to test against a table, so the loops go staging-major: one embed per
# (separator, settle), the bracket run extended one instruction at a time,
# and the endgame emitted once per (k, accumulator, read, orientation)
# whatever the table.  Measured, three inputs derive in 2.4s and two in
# 0.15s; the table-major spelling costs minutes, rebuilding every staging
# once per table.
#
# Selection is on the accumulator's value **at the read**, not on the cell
# holding the answer beforehand: the walk out applies the running prefix-XOR,
# so at ``acc = 22`` after separator 1, AND arrives as a constant and XOR as
# ``b1``.  The enumeration sidesteps that by emitting the endgame and reading
# what the rows actually printed.  A table and its complement share a staging
# -- the endgame tries both read polarities and both pool orientations, and
# the printed digit is ``NOT(v XOR cell7)`` -- so counts below are in pairs.
_Staging = tuple[int, int, int | str, int]

# Coverage is stated over the 109 complement pairs of three-input tables that
# are non-degenerate *and* depend on all three inputs (128 pairs, less the 3
# the degenerate route claims and the 16 that go to the projection route).
# The enumeration reaches 108 of them and all 8 at two inputs.
#
# The one holdout is ``01101101`` / ``10010010``, and the shape of the miss is
# worth recording so it is not re-run blind.  Its answer column is not scarce
# -- it stands at cell 24 under separator 2 at ``k == 15``, and 14375 of
# 804600 sparse suffixes leave it standing somewhere -- but no staging
# *carries* it to the read, because the walk's prefix-XOR rewrites that very
# cell.  A pure bracket run never manages it, which is exactly why every
# entry of :func:`_stagings` being a run puts it out of reach; the stored
# suffix interleaves two ``<`` into the run instead.  A sweep over 13 of the
# 15 (separator, settle) slices at ``k <= 40`` and every accumulator reached
# Hamming distance 1 and never 0.  It is a gap in this family rather than a
# wall: 180 of the 256 possible columns arrive, and no affine invariant
# separates them from this one (all 255 parity masks checked).
#
# What closed the *other* gaps was a wider separator set rather than a better
# search -- see :data:`_SEPS`.  The bracket axis is *exhausted*, not capped:
# nothing here writes leftward, so once every row's pointer has passed the
# accumulator window no further bracket can change a staged column.  Measured,
# columns stop changing between ``k == 25`` and ``k == 38``, the sweep ran to
# 40, and the deepest first hit needed is ``k == 26`` at three inputs, which
# is where :data:`_MAX_BRACKETS` comes from.  The settle and accumulator axes
# were sampled rather than exhausted and came back empty.
#
# **All four fields are enumerated because the simpler forms were measured
# and fail.**  One fixed staging is impossible by counting: it offers 52
# slots, but the prefix-XOR is many-to-one, so the best single staging
# delivers 13 pairs and the mean is 5.8, against 109 to place.  Two
# separators reach 49 of 109; dropping the settle field reaches 99, ten pairs
# being reachable only at ``settle == 1``.  (Ablations must patch
# :func:`_slices`, the enumeration the index really walks; patching
# :func:`_stagings`, which has no callers, reports the baseline as the
# ablation's result.  ``_staging_index`` is cached and must be cleared too.)
#
# Nor is there a cheap predictor of which staging serves a table: at four
# inputs no tested invariant yields a necessary condition, every (separator,
# settle) slice contributes tables reachable nowhere else, and 72% of tables
# are served by exactly one slice.  The column algebra does *invert* -- a
# target's first pure-run staging can be computed directly from per-row
# admissible-``k`` bitmasks, reproducing the index exactly -- but the 4640
# stagings collapse to about 4190 distinct plan vectors, so there is no
# many-to-one structure to exploit, and a per-table inversion runs 20-30ms
# against a 0.4-0.75s whole-arity fill that then answers every table.
#
# Separator 0 is enumerated first although no three-input table needs it:
# it carries every two-input table on its own, and :data:`_SEP` and
# :data:`_SCAN_SEPS` use it.

# The arities the enumeration covers.  Two and three are *total*; four and
# five are partial, and ship because a miss falls through to the searches, so
# admitting an arity cannot cost coverage.  Beyond five the gate stays
# explicit: not that the enumeration is known to fail, but that it has not
# been shown to succeed.
#
# Four reaches 15404 of the 64594 fully-essential four-input tables (23.9%),
# four-input XOR among them -- the table the searches are recorded as failing
# on, and what closed it was the *suffix* rather than the search or the pool
# (see :data:`_STAGED_ARITIES` and :func:`_insert_suffixes`).  Five ships on
# a harvest of 24582 fully-essential 32-bit columns, complement-closed, with
# five-input XOR among them; what made it runnable is that
# :func:`_derived_plans` is asked for the tables it wants rather than for the
# whole arity.
#
# Four inputs costs time in a way the others do not.  At two and three every
# table is placed, so the derivation stops early; at four it never can, so
# the enumeration runs to its caps -- about 76 seconds, paid by the first
# fully-essential four-input table in a process whether it hits or misses,
# and once, since :func:`_derived_plans` is cached.  Constants, projections
# and tables with an ignored input never reach it.  The caps are not slack:
# coverage climbs to both of them, with 12256 tables at ``k <= 24`` against
# 15404 at 28, so trimming to buy time trims coverage.
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
# The unit is the point: a wall-clock budget would build a table on a fast
# host and raise on a slow one.  A staging is one tuple in
# :func:`_stagings` order, so a budget picks out the *same* set of tables
# everywhere and the emitted programs stay byte-identical.  It also tracks
# real work, since :func:`_column_sweep` derives a staging's whole
# accumulator range from one walk.
#
# **A budget costs program length, not coverage.**  A table it stops short of
# falls through to :func:`_mux`, total at four inputs at about 11ms, so
# lowering this cannot make a table unbuildable -- it trades the staged
# route's shorter template (205 characters at four inputs against the
# sculpted route's 952) for the tables it gives up.
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
