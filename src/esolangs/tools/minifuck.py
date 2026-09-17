"""Build Minifuck Boolean templates by input substitution.

Each input is embedded once at equal width. The construction derives one
program, verifies every instantiated row with the joint simulator, and raises
rather than emit an unverified program. The simulator laws are pinned
differentially against the interpreter; the retired enumerations remain as
test oracles only.
"""

from functools import cache

from esolangs.tools.helpers import (
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.minifuck_mux import (
    _MUX_BASE as _MUX_BASE,
)
from esolangs.tools.minifuck_mux import (
    _MUX_MIN_ARITY,
    _canonical_endgame,
    _mux,
    _mux_lookup,
)
from esolangs.tools.minifuck_mux import (
    _MUX_PRESERVE_RIGHT as _MUX_PRESERVE_RIGHT,
)
from esolangs.tools.minifuck_mux import (
    _SCULPT_POOL_CODE as _SCULPT_POOL_CODE,
)
from esolangs.tools.minifuck_mux import (
    _mux_probe as _mux_probe,
)
from esolangs.tools.minifuck_mux import (
    _mux_probe_sim as _mux_probe_sim,
)
from esolangs.tools.minifuck_mux import (
    _mux_scout as _mux_scout,
)
from esolangs.tools.minifuck_mux import (
    _mux_sculpt as _mux_sculpt,
)
from esolangs.tools.minifuck_mux import (
    _mux_separate as _mux_separate,
)
from esolangs.tools.minifuck_mux import (
    _mux_start as _mux_start,
)
from esolangs.tools.minifuck_mux import (
    _mux_sweep as _mux_sweep,
)
from esolangs.tools.minifuck_mux import (
    _mux_weight as _mux_weight,
)
from esolangs.tools.minifuck_mux import (
    _pascal_parity_row as _pascal_parity_row,
)
from esolangs.tools.minifuck_mux import (
    _probe_frame as _probe_frame,
)
from esolangs.tools.minifuck_mux import (
    _sculpt_columns as _sculpt_columns,
)
from esolangs.tools.minifuck_mux import (
    _sculpt_pool_code as _sculpt_pool_code,
)
from esolangs.tools.minifuck_pool import (
    _BASE,
    _SEP,
    _SEPS,
    _SPAN,
    _embed,
    _try_print,
)
from esolangs.tools.minifuck_pool import (
    _FLIP as _FLIP,
)
from esolangs.tools.minifuck_pool import (
    _PLANS as _PLANS,
)
from esolangs.tools.minifuck_pool import (
    _POOL_CODES as _POOL_CODES,
)
from esolangs.tools.minifuck_pool import (
    _POOL_MASK as _POOL_MASK,
)
from esolangs.tools.minifuck_pool import (
    _POOL_PTR_MAX as _POOL_PTR_MAX,
)
from esolangs.tools.minifuck_pool import (
    _POOL_WIDTH as _POOL_WIDTH,
)
from esolangs.tools.minifuck_pool import (
    _PROBE_WALK_OUT as _PROBE_WALK_OUT,
)
from esolangs.tools.minifuck_pool import (
    _READS as _READS,
)
from esolangs.tools.minifuck_pool import (
    _SCAN_SEPS as _SCAN_SEPS,
)
from esolangs.tools.minifuck_pool import (
    _endgame as _endgame,
)
from esolangs.tools.minifuck_pool import (
    _find_pool as _find_pool,
)
from esolangs.tools.minifuck_pool import (
    _pool_code_for_row as _pool_code_for_row,
)
from esolangs.tools.minifuck_pool import (
    _pool_reaches as _pool_reaches,
)
from esolangs.tools.minifuck_pool import (
    _pool_slice as _pool_slice,
)
from esolangs.tools.minifuck_pool import (
    _printed_column as _printed_column,
)
from esolangs.tools.minifuck_pool import (
    _step as _step,
)

# The machine the construction below emits against.  ``_Sim`` and ``_Joint``
# are re-exported rather than referenced through the module because the test
# suite imports them from here by name, and because every use in this file
# reads as part of the construction rather than as a call into a simulator.
# ``_Sim`` and ``_Joint`` are re-exported rather than referenced through
# the module because the test suite imports them from here by name.
from esolangs.tools.minifuck_sim import (
    _MINIFUCK_INPUT,
)
from esolangs.tools.minifuck_sim import (
    _clamp as _clamp,
)
from esolangs.tools.minifuck_sim import (
    _Joint as _Joint,
)
from esolangs.tools.minifuck_sim import (
    _runs as _runs,
)
from esolangs.tools.minifuck_sim import (
    _Sim as _Sim,
)
from esolangs.tools.minifuck_sim import (
    _walk_to as _walk_to,
)
from esolangs.tools.minifuck_staged import (
    _CHAIN_CAP as _CHAIN_CAP,
)
from esolangs.tools.minifuck_staged import (
    _INSERT_ARITIES as _INSERT_ARITIES,
)
from esolangs.tools.minifuck_staged import (
    _MAX_ACC as _MAX_ACC,
)
from esolangs.tools.minifuck_staged import (
    _MAX_BRACKETS as _MAX_BRACKETS,
)
from esolangs.tools.minifuck_staged import (
    _SLICE_YIELD_ORDER as _SLICE_YIELD_ORDER,
)
from esolangs.tools.minifuck_staged import (
    _STAGED_ARITIES as _STAGED_ARITIES,
)
from esolangs.tools.minifuck_staged import (
    _STAGING_BUDGET as _STAGING_BUDGET,
)
from esolangs.tools.minifuck_staged import (
    _STAGING_BUDGET_N5 as _STAGING_BUDGET_N5,
)
from esolangs.tools.minifuck_staged import (
    _budget as _budget,
)
from esolangs.tools.minifuck_staged import (
    _Chain as _Chain,
)
from esolangs.tools.minifuck_staged import (
    _closed_sweeps as _closed_sweeps,
)
from esolangs.tools.minifuck_staged import (
    _column_sweep as _column_sweep,
)
from esolangs.tools.minifuck_staged import (
    _derive_staging,
    _replay,
)
from esolangs.tools.minifuck_staged import (
    _derived_plans as _derived_plans,
)
from esolangs.tools.minifuck_staged import (
    _first_staging as _first_staging,
)
from esolangs.tools.minifuck_staged import (
    _insert_suffixes as _insert_suffixes,
)
from esolangs.tools.minifuck_staged import (
    _planned_bit as _planned_bit,
)
from esolangs.tools.minifuck_staged import (
    _planned_bits as _planned_bits,
)
from esolangs.tools.minifuck_staged import (
    _slice_chains as _slice_chains,
)
from esolangs.tools.minifuck_staged import (
    _slices as _slices,
)
from esolangs.tools.minifuck_staged import (
    _staging_index as _staging_index,
)
from esolangs.tools.minifuck_staged import (
    _stagings as _stagings,
)
from esolangs.tools.minifuck_staged import (
    _suffix_plan as _suffix_plan,
)

__all__ = ["minifuck"]


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

    The accumulator is named by the embed law: cell 16 prints ``b0``, cell 19
    prints ``~b1``, and a constant stands at 16 for the nullary embed or 17
    otherwise.  The first table bit decides whether the direct or complemented
    read is needed.  Later projections decline to :func:`_mux`.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) > 1:
        return None
    if not essential:
        acc = _BASE if n == 0 else _BASE + 1
        direct = truth_table[0] == ("1" if n == 0 else "0")
    elif essential[0] == 0:
        acc = _BASE
        direct = truth_table[0] == "0"
    elif essential[0] == 1:
        acc = _BASE + 3
        direct = truth_table[0] == "1"
    else:
        return None

    base = _embed(n, sep=_SEP)
    _clamp(base)
    _canonical_endgame(base, acc, direct=direct)
    if base.printed() != list(truth_table):  # pragma: no cover - the law is exact
        raise AssertionError("the degenerate rule printed the wrong column")
    return base.template()


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
    keeps the runs in name order.  They do write the tape, though, so
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

    ``_lift`` puts the ignored inputs' runs last, which leaves name order.
    The alternative is to emit them *first* -- the runs stay in name
    order -- and then reconverge the rows so nothing downstream can tell
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


def _lift_leaves_name_order(essential: list[int], n: int) -> bool:
    """Whether lifting would put the ignored inputs' runs out of name order.

    :func:`_lift` appends the ignored inputs after the solved template, and
    the k-th run *is* input k, so the result names its inputs correctly only
    when every ignored index is above every essential one -- inputs 0 and 1
    then input 2.  It is only when an ignored index sits *below* an
    essential one that the append misnames them.
    """
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    """Widen a smaller table's template back onto the wider arity.

    The inner solve emitted one run per essential input, in order; those
    runs stay where they are and are read as the inputs listed in
    ``essential`` (which :func:`_lift_leaves_name_order` has checked are
    the first ``len(essential)`` names).

    Every input the function ignores still needs a run, or the harness
    would have a bit with nowhere to put it.  Those go on the end: the fill
    is two characters whichever bit it is, so they cannot make the program's
    length depend on the inputs, and by then the digit has been printed --
    the ``.`` has already run -- so whatever they do to the tape cannot
    matter.  An order the append would misname is refused rather than
    emitted: the k-th run is input k, so there is no renaming to fall back on.
    """
    if _lift_leaves_name_order(essential, n):
        raise ValueError(f"lifting {essential} onto {n} inputs misnames a run")
    return template + _MINIFUCK_INPUT * (n - len(essential))


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minifuck has no usable input command, so this is a parameterized
    generator: the template's input runs become ``[<`` for a one
    and ``xx`` for a zero -- equal width, so no instantiation leaks its
    inputs through its length -- and the harness instantiates one program per
    input combination.

    The emitted program embeds each input once, computes the table in cells
    past the pool, relays the answer into the *pointer* (values cannot travel
    left, but the pointer can), and prints one ASCII digit.  Every emission
    is tracked against all ``2**n`` rows by the closed-form laws in
    :mod:`esolangs.tools.minifuck_sim`, and a :class:`ValueError` is
    raised rather than returning a program that has not been seen to print
    the table.

    Cached because the build is deterministic in ``truth_table`` and the
    result is an immutable string.  No route enumerates candidate programs:
    projection, the degenerate cell law, and the fixed mux construction name
    the emitted program directly.
    """
    n = _validate_shape(truth_table)

    # Dependency discovery compares every row at every input and is
    # O(T log T).  Keep the compact legacy routes only below the strip's
    # crossover; the direct lookup is O(T) for every wider table, folded or
    # not, so no preliminary analysis may dominate it.
    if n >= 5:
        return _mux_lookup(truth_table, n)

    # Below the strip crossover, a table that ignores inputs is a smaller
    # table wearing extra ones; solve it there and append the ignored runs.
    essential = essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projection is cheaper, but appending ignored inputs after the print
        # disorders their names when one lies below an essential input.  The
        # full-arity mux embeds every slot in order, so that case uses it.
        if _lift_leaves_name_order(essential, n):
            sculpted = _mux(truth_table, n)
            if sculpted is not None:
                return sculpted
        inner = _solve(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # Nullary and unary inner solves use the embed's named standing column.
    if n < _MUX_MIN_ARITY:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # The one total construction for every non-degenerate inner solve.
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
    # closes by an argument uniform in ``n``.  The section this used to cite,
    # "Is ``_mux`` total?" in ``the relevant generator tests``, did
    # not survive that file's condensing; ``the relevant tests`` carries the claim
    # now, for this generator and the other 68.  So the generator is total on
    # the arities that document states: this raise says the
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
