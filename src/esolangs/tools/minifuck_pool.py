"""The Minifuck embed and the pool the endgame prints through.

Every route embeds each input once with :func:`_embed` and ends by walking out
to an accumulator and printing through cells 0..7 -- the *pool*.  What differs
between the routes is only what happens in between, so the embed, the pool
codes, the column derivation and the endgame are shared from here.
"""

from functools import cache

from esolangs.tools.minifuck_sim import _clamp, _Joint, _runs, _Sim, _walk_to

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
# the totality argument in ``the relevant generator tests`` turns on the
# relationship: the accumulator floor ``_endgame`` refuses below, the
# sculpting rewind guard ``rewind > min(ptrs) - _POOL_WIDTH``,
# :data:`_PROBE_WALK_OUT` and the lowest cell a round may write (both
# ``_POOL_WIDTH + 1``), and the sculpting accumulator loop's start,
# ``span + _POOL_WIDTH + 1``.
#
# That last pair is essential: the loop starting one *past* the guard is what
# makes the rewind bound tight rather than slack, since the worst rewind is
# ``lo - _POOL_WIDTH``, the guard itself, so the guard can never fire.
# Spelled ``8`` and ``9`` the identity looks like a coincidence.
#
# The staging path takes the same two, and only ``_MAX_ACC`` itself is a
# search bound.  ``_MUX_GUARD``'s ``8`` is *not* this constant but a scratch
# width; it is not independent either, since :func:`_mux_start`'s offset
# derives from it, but the two are coupled elsewhere.
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
# **These values do not compress further**, which was measured.  ``core`` is
# not derivable from the finished code: on a blank tape every plan with
# ``core > 0`` ends at ``mark = steps + 1`` and ``pointer = steps`` whatever
# the core's index (verified for ``steps`` 1 to 40).  It is pinned on live
# states instead.  Moving it strands tables at every alternative for three of
# the plans -- 22 for the third, 18 for the fourth, 6 for the fifth -- which
# for the third and fourth is what dropping those codes outright costs.  The
# second plan's core strands nothing and is pinned by slot order instead, 10
# out-of-name-order templates going to 18.
#
# Only the first plan's core moves freely, which is a fact about the arity
# rather than the core: that code answers no site at ``n <= 3``, so every
# spelling looks free there.  The two spellings are genuinely different
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
