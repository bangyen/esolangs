r"""Build Minifuck Boolean templates by input substitution."""

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
    r"""Emit the embed: each ``{Xi}`` once, separated by :data:`_SEP`."""
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
    r"""One step of a pool code: carry a mark right, then walk the pointer."""
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
    r"""Spell one plan out as a pool code."""
    codes = []
    for i in range(steps):
        backs, odd = overrides.get(i, (1, True))
        codes.append(_step(carry=2 if i == core else 1, backs=backs, odd=odd))
    return "".join(codes)


_POOL_CODES = tuple(_render(*plan) for plan in _PLANS)


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    r"""Whether ``code`` leaves the pool correct once walked out."""
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
    r"""Return the pool code this row admits and where it leaves it, or."""
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
    r"""Derive the verdict for every window byte at one ``(pointer, skip)``."""
    return {
        (low, cell7): answer
        for low in range(1 << _POOL_WIDTH)
        for cell7 in (0, 1)
        if (answer := _pool_code_for_row(codes, low, ptr, cell7, skip=skip)) is not None
    }


def _find_pool(j: _Joint, cell7: int, walk_out: int) -> str | None:
    r"""Return the pool code for this orientation, or None if none fits."""
    del walk_out

    codes = tuple(_POOL_CODES)

    def answer_for(row: _Sim) -> tuple[int, int] | None:
        r"""Which code this row names, and where that code leaves it."""
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
    r"""Set the pool, relay ``acc`` into the pointer, and print one digit."""
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
    r"""Flip every row of a column."""
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
    r"""Return what the ``'[x<[<'`` read prints here, without printing it."""
    key = (j.template(), acc, cell7)
    hit = _PRINTED_COLUMNS.get(key, _MISSING)
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    column = _derive_column(j, acc, cell7)
    _PRINTED_COLUMNS[key] = column
    return column


def _derive_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    r"""Return the column :func:`_printed_column` memoises, derived fresh."""
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
    r"""Return every accumulator's printed column, from **one** walk."""
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
    r"""Whether the endgame really prints ``column`` here."""
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
    r"""Emit the endgame that prints the table at ``acc``, or None."""
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
    r"""Return the column ``name`` stands for, or None if this arity has no."""
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
    r"""Find where the embed leaves the constants and the first two inputs."""
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
    r"""Build a table depending on at most one input, without the ladder."""
    base = _embed(n, sep=_SEP)
    _clamp(base)

    for acc in _degenerate_cells(n).values():
        hit = _try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template()
    return None


def _project(truth_table: str, essential: list[int], n: int) -> str:
    r"""Rewrite the table over its essential inputs only."""
    return read_at(truth_table, essential, n)


# The fixed head of the.
# ``<``, which clamps rather.
# enough to bring every row.
_RESET_HEAD = "[<[<<[<[<"


def _reset_code(ignored: int) -> str:
    r"""Return code after which the ignored inputs leave no trace."""
    return _RESET_HEAD + "<" * (ignored + 1)


def _reconverged(truth_table: str, essential: list[int], n: int) -> str | None:
    r"""Build by emitting the ignored inputs first, then erasing them."""
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
    r"""Return the staging budget for this arity, in stagings visited."""
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
    r"""Return the ``(separator, settle)`` slices, in the order to spend."""
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
    r"""Enumerate bracket runs with one ``<`` inside, shortest first."""
    for k in range(_MAX_BRACKETS + 1):
        for cut in range(k + 1):
            yield "[" * cut + "<" + "[" * (k - cut)


# The insert family,.
# a winning ordinal back as its.
# strings.
_INSERT_SUFFIXES = tuple(_insert_suffixes())


def _stagings(n: int) -> Iterator[_Staging]:
    r"""Enumerate ``(separator, settle, suffix, accumulator)`` in order."""
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
    r"""Build one staging and return its template, or None if it does not."""
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
    r"""Derive a staging for the wanted tables, in one pass of the."""
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
        r"""Record what every accumulator prints, deriving it rather than."""
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
    r"""Clear the plan cache and everything derived alongside it."""
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
    r"""One row's bracket-run algebra: the prefix-XORs and the staircase."""

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
        r"""Extent and pending skip of a pure run of ``budget`` brackets."""
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
    r"""Reduce one row's response to ``'[' * cut + '<' + '[' * rest``."""
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
    r"""One row's XOR of post-suffix cells ``_BASE ."""
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
    r"""Return every accumulator's :func:`_planned_bit`, resolved by region."""
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
    r"""One slice's row chains and per-orientation pool facts."""
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
    r"""Both orientations' accumulator sweeps for one suffix, derived."""
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
    r"""Map every column the stagings reach to the staging that prints it."""
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
    r"""Tabulate, per slice, what every staging does to every row."""
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
    r"""Return the first staging, in enumeration order, printing the table."""
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
    r"""Return the staging that builds ``truth_table``, or None if none."""
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
    r"""Build from a derived staging without searching, or None if there is."""
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
    r"""Return a joint walked to the embed's start with nothing embedded."""
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    r"""Whether every cell left of the guard survived, on every row."""
    return all(
        m.cells(_MUX_GUARD) == m0.cells(_MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_weight(k: int) -> str:
    r"""Return the gadget displacing a **fresh** setter bit by exactly."""
    return ("[x<[<" + "<") * (k - 1) + "[x<[<" if k > 0 else ""


def _mux_weights(n: int) -> tuple[int, ...]:
    r"""Return the per-input weights: ``2**(n-1-i)``, so the sum is the row."""
    return tuple(2 ** (n - 1 - i) for i in range(n))


def _mux_pad(n: int) -> int:
    r"""Return the slack each gadget gets beyond the previous one's weight."""
    return max((1 << (n - 2)) - 1, 1)


def _mux_start(n: int) -> int:
    r"""Return where to lay the embed so no gadget writes left of the guard."""
    return _MUX_BASE + max(0, (1 << (n - 1)) - (_MUX_BASE - _MUX_GUARD + 1))


def _mux_separate(n: int) -> _Joint | None:
    r"""Emit an embed leaving all ``2**n`` rows at distinct pointers."""
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
    r"""Return the code a sculpting probe reaches, by."""
    return _SCULPT_POOL_CODE if cell7 == 0 else None


@cache
def _probe_frame(code: str, byte: int) -> tuple[int, int] | None:
    r"""Return ``(landed, parity)`` for ``code`` run from a converged row."""
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
    r"""Return the probe column by the parity law, or None to fall back."""
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
    r"""Run the probe by simulation: fork, absorb, clamp, set the pool,."""
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
    r"""Return the column printed at ``acc`` and the pool code that got it."""
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
    r"""Sculpt the printed column at one ``(C, orientation, read)``."""
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
    r"""Return the low ``width`` bits of ``value``, reversed."""
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
    r"""Price every ``(accumulator, orientation)`` sculpt without emitting."""
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
    r"""Spell the sculpt the scout priced, from its recorded rewinds."""
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
    r"""Whether the spelled build really prints the table, row by row."""
    probe = base.fork()
    for m in probe.ms:
        m.run_rewinds(rewinds)
    probe.emit(suffix)
    return probe.printed() == list(truth_table)


def _mux_sweep(base: _Joint, truth_table: str, n: int, accs: range) -> str | None:
    r"""Sculpt every combination for real and keep the shortest build."""
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
    r"""Build by separating the rows, then sculpting the column they print."""
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
    r"""Whether lifting would emit the ``{Xi}`` out of ascending order."""
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    r"""Renumber a smaller table's placeholders back onto the wider arity."""
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
    r"""Build a Minifuck template for the given truth table."""
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
    r"""Build a Minifuck template for the given truth table."""
    _validate_truth_table(truth_table)
    return _solve(truth_table)


# The construction's cache and.
# but tests and callers reach.
# ``cache_clear``/``cache_info``.
# arity check off did not move.
minifuck.cache_clear = _solve.cache_clear  # type: ignore[attr-defined]
minifuck.cache_info = _solve.cache_info  # type: ignore[attr-defined]
minifuck.__wrapped__ = _solve.__wrapped__  # type: ignore[attr-defined]
