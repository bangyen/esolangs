"""Contract tests every boolean generator must satisfy.

These are cross-cutting invariants rather than per-language behaviour: they
sweep every registered boolean generator instead of asserting against one.
"""

import contextlib
import importlib

import pytest

import esolangs.tools.boolean as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_BOOLEAN, BY_FUNCTION, LANGUAGES
from esolangs.vm import run_until_halt_or_cycle

# One constant table against one that folds nothing.  A generator loses reads
# by *folding*, so a table that folds completely and a table that folds not at
# all are what the comparison needs; near-constant tables in between produce
# intermediate counts but never catch a generator these two miss.  This sweep
# runs every interpreter on every table on every pytest invocation, so the
# cases that add cost without adding detection are not worth carrying --
# ``00000001`` and ``11111110`` were dropped for exactly that reason.
#
# ``01101001`` is parity, the one table with no constant subtree above a
# single row, so nothing about it can fold.
_TABLES = ["00000000", "01101001"]


# Generators that search rather than emit, and so cost seconds per table
# instead of milliseconds.  The rule is a one-second budget per entry in this
# sweep: over that, the case carries ``slow`` and sits out the fast run.
# Measured at the time of writing (``pytest --durations -n 0``, one worker):
# minifuck 41.1s, slow_acv_mammalian 5.5s, and the next entry down is
# polynomial at 0.5s, with the median around 0.03s.
#
# ``ztoalc_l_boolean`` used to be listed here at 2.8s and now runs in 0.02s,
# so it is no longer marked -- the cost moved to the *reordering* sweeps
# below, which is why the two sets are kept separate rather than shared.
#
# ``pct_squared_minus_one`` was briefly in this set, at 4.6s: it searched
# setter assignments and this sweep's parity table is ``n == 3``, which it
# could not separate, so it paid a whole search budget before raising.  It
# now derives its programs instead and rejects that arity outright, which
# puts it below the measurement floor.
#
# Naming the languages rather than timing them at collection time is
# deliberate: a wall-clock threshold evaluated during collection would make
# the selected test set depend on how loaded the machine is, so a run could
# silently cover less than the last one.  Re-measure and edit this set when
# a generator's cost changes.
_SEARCHING_GENERATORS = frozenset({"minifuck", "slow_acv_mammalian_boolean"})

# The same one-second rule, applied to the two reordering sweeps.  Those call
# the ``_*_ordered`` builder once per input order for every table up to three
# inputs, so a generator that *searches* pays that cost repeatedly.  Measured
# one worker, ztoalc_l_boolean is 3.0s in test_reordering_never_grows_a_program
# against 0.02s in the read-count sweep above, and the next entry down is
# streetcode at 0.06s.  A generator can be cheap in one sweep and expensive in
# the other, so this set is maintained independently of the one above.
_SLOW_REORDERING_GENERATORS = frozenset({"ztoalc_l_boolean"})


def _input_reading_generators() -> list[object]:
    """Every boolean generator whose language actually reads input.

    Looked up in ``BY_BOOLEAN``, not ``BY_FUNCTION``.  The latter is keyed
    by the *text* generator's function name, so a boolean-only language is
    missing from it entirely and this sweep skipped such languages in
    silence -- sixteen of them, including the one whose contract violation
    that concealed (Jaune read a number of inputs that depended on its
    truth table).  A generator absent from the index it is swept by does
    not fail; it simply is not there, which is the failure mode worth
    designing against.
    """
    found = []
    for name in sorted(boolean.__all__):
        fn = getattr(boolean, name, None)
        lang = BY_BOOLEAN.get(name)
        if not callable(fn) or lang is None or lang.interpreter is None:
            continue
        try:
            run = importlib.import_module(
                f"esolangs.interpreters.{lang.interpreter}"
            ).run
        except Exception:  # pragma: no cover - interpreter lives outside the pkg
            continue
        if name in _SEARCHING_GENERATORS:
            found.append(pytest.param(name, (fn, lang, run), marks=pytest.mark.slow))
        else:
            found.append((name, (fn, lang, run)))
    return found


def _reads(entry: tuple, table: str) -> int:
    """Run the generated program and report how many inputs it consumed.

    Driven through :func:`run_until_halt_or_cycle` where the interpreter
    exposes a stepping machine.  Some of these programs never terminate by
    design -- Point Break's convention is to halt iff the function is 0 and
    loop forever iff it is 1 -- and waiting those out against an
    interpreter's step cap costs seconds each, which this sweep pays on
    every pytest invocation.  A deterministic machine that revisits its
    exact state has provably looped, so the detector stops it at once: the
    whole sweep drops from minutes to well under a second, and the read
    count at that point is the same number either way.
    """
    fn, lang, run = entry
    try:
        program = str(fn(table))
    except ValueError:
        # A generator that does not cover this table emits no program, and a
        # program that does not exist reads nothing.  Reporting 0 routes the
        # caller into its "does not read input" skip rather than failing on a
        # coverage gap, which is not what this test measures.  %^2^-1 is the
        # case in hand: it derives two-input tables only, and the sweep's
        # parity table has three.
        return 0
    io = ScriptedIO("0\n" * 8)
    source = program.splitlines() if lang.split else program
    module = importlib.import_module("esolangs.interpreters." + lang.interpreter)
    machine_cls = getattr(module, "_Machine", None)
    # A program may halt through its own error path or call exit; either way the
    # read count up to that point is what matters here.
    with contextlib.suppress(Exception, SystemExit):
        if machine_cls is not None:
            run_until_halt_or_cycle(machine_cls(source, io))
        else:
            run(source, io=io, **dict(lang.kwargs))
    return io.position()


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    """A generator reads its ``n`` inputs whatever the truth table says.

    An input-capable language reads each of its ``n`` inputs exactly once per
    run, and that must not depend on the *contents* of the table.  A generator
    that special-cases a constant table by printing the answer outright skips
    the reads, which leaves the caller's bits unread on the input stream for
    whatever runs next, and drops the per-read prompts that a prompting
    language (3x) emits -- prompts ``scripts/verify_extra_generators.py``
    filters precisely because they are part of the observable output.

    Shortening the *body* for a constant table is fine and worth doing; the
    reads are the interface and have to stay.
    """
    counts = {table: _reads(entry, table) for table in _TABLES}
    baseline = counts["01101001"]
    if baseline == 0:
        pytest.skip(f"{name} does not read input in this harness")
    assert set(counts.values()) == {baseline}, (
        f"{name} reads a different number of inputs depending on the table: "
        f"{counts} -- a constant table must still consume all {baseline}"
    )


def _exported_generators() -> dict[str, str]:
    """Every boolean generator the package exports, mapped to its language.

    A generator function is named for its language's canonical id, so the id
    is the join.  Two naming conventions sit on top of it: a ``_boolean``
    suffix distinguishes the boolean generator where the text one already
    owns the plain name (``forbin_boolean``, ``ztoalc_l_boolean``), and a
    few ids drop an underscore (``bf_pda`` -> ``bfpda``).  ``BY_FUNCTION``
    covers the languages whose text generator shares the name.
    """
    by_id = {lang.id: name for name, lang in LANGUAGES.items()}
    squashed = {lang.id.replace("_", ""): name for name, lang in LANGUAGES.items()}
    found = {}
    for fn in boolean.__all__:
        if fn in ("BOOLEAN", "instantiate") or not callable(getattr(boolean, fn, None)):
            continue
        base = fn.removesuffix("_boolean")
        display = (
            by_id.get(base)
            or squashed.get(base.replace("_", ""))
            or (BY_FUNCTION[fn].name if fn in BY_FUNCTION else None)
        )
        if display is not None:
            found[fn] = display
    return found


def test_boolean_set_lists_exactly_the_exported_generators() -> None:
    """``BOOLEAN`` and the package's exports name the same languages.

    ``BOOLEAN`` is what :func:`esolangs.describe` reports as
    ``boolean_generator``, but it is a second, hand-maintained list of what
    the package already exports -- so the two can disagree, and the way they
    disagree is silent.  Adding a generator and updating the import and
    ``__all__`` but not ``BOOLEAN`` leaves a working generator that
    ``describe`` reports as absent, with every other check still passing
    (``set(LANGUAGES) >= BOOLEAN`` only catches a name that is not a
    language at all).

    This pins both directions so that omission fails loudly instead.
    """
    exported = _exported_generators()
    missing = {d for d in exported.values() if d not in boolean.BOOLEAN}
    assert not missing, (
        f"these languages export a boolean generator but are absent from "
        f"BOOLEAN, so describe() reports boolean_generator=False for them: "
        f"{sorted(missing)} -- add them to BOOLEAN in tools/boolean/__init__.py"
    )
    stale = boolean.BOOLEAN - set(exported.values())
    assert not stale, (
        f"BOOLEAN names these languages but the package exports no generator "
        f"resolving to them: {sorted(stale)} -- remove them from BOOLEAN, or "
        f"export the generator from tools/boolean/__init__.py"
    )


# The tree generators that pick their input split order by measuring, and the
# builder that emits one fixed order, so a test can compare the two.
def _reordering_generators() -> list[object]:
    from esolangs.tools.boolean.helpers import _decision_tree_program
    from esolangs.tools.boolean.other import (
        _between_ordered,
        _forbin_ordered,
        _myscript_ordered,
        _nevermind_ordered,
    )
    from esolangs.tools.boolean.parameterized import (
        _bitdeque_ordered,
        _lamfunc_ordered,
        _ram0_ordered,
    )
    from esolangs.tools.boolean.tape import (
        _ASCII_ZERO,
        _basicfuck_ordered,
        _circlefuck_ordered,
        _jaune_ordered,
    )
    from esolangs.tools.boolean.ztoalc_l import _ztoalc_ordered

    entries: list[tuple[str, object, object]] = [
        (
            "brainfuck",
            boolean.brainfuck,
            lambda t, p: _decision_tree_program(t, ">", "<", p),
        ),
        (
            "dimensional",
            boolean.dimensional,
            lambda t, p: _decision_tree_program(t, ">0", "<0", p),
        ),
        ("ram0", boolean.ram0, _ram0_ordered),
        ("between", boolean.between, _between_ordered),
        ("lamfunc", boolean.lamfunc, _lamfunc_ordered),
        ("bitdeque", boolean.bitdeque, _bitdeque_ordered),
        ("ztoalc_l_boolean", boolean.ztoalc_l_boolean, _ztoalc_ordered),
        ("myscript", boolean.myscript, _myscript_ordered),
        ("nevermind", boolean.nevermind, _nevermind_ordered),
        ("basicfuck", boolean.basicfuck, _basicfuck_ordered),
        (
            "circlefuck",
            boolean.circlefuck,
            # The byte-valued builder underneath takes a *byte* table,
            # so the contract's binary-string table is lifted the way
            # circlefuck() itself lifts it.
            lambda t, p: _circlefuck_ordered([_ASCII_ZERO + int(b) for b in t], p),
        ),
        ("forbin_boolean", boolean.forbin_boolean, _forbin_ordered),
        ("jaune", boolean.jaune, _jaune_ordered),
    ]
    return [
        (
            pytest.param(name, fn, ordered, marks=pytest.mark.slow)
            if name in _SLOW_REORDERING_GENERATORS
            else (name, fn, ordered)
        )
        for name, fn, ordered in entries
    ]


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_never_grows_a_program(
    name: str, fn: object, ordered: object
) -> None:
    """Choosing the input order can only shrink the emitted program.

    The identity order is one of the candidates, so the winner is at worst a
    tie with what the generator emitted before reordering existed -- which
    is what makes this optimization safe to apply unconditionally.
    """
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            baseline = ordered(table, tuple(range(n)))
            # A searching generator returns "" for an order it cannot place
            # (ZTOALC L); there is no baseline to be no worse than, and any
            # order that *did* place is an improvement on not building.
            if not baseline:
                continue
            assert len(fn(table)) <= len(baseline), f"{name} grew on {table}"


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_shrinks_the_tables_it_should(
    name: str, fn: object, ordered: object
) -> None:
    """A table only one input order folds well is emitted from that order.

    ``10101010`` depends solely on the *last* input, so splitting on it
    first folds the whole tree to a single leaf, while the identity order
    folds nothing until the bottom level.

    Jaune is exempt because a *different* optimization already collects
    this: it clobbers the inputs no node branches on rather than storing
    them, so the identity order emits the minimal program for a
    single-dependency table and there is nothing for a reorder to win.
    Its gains show up on tables with several real dependencies instead.
    """
    if name == "jaune":
        pytest.skip("clobbering already makes the identity order optimal here")
    # Circlefuck splits last-input-first, so ``10101010`` is the table its
    # identity order already folds; the one only a reorder folds is the
    # same function with its inputs renamed the other way.
    table = "11110000" if name == "circlefuck" else "10101010"
    assert len(fn(table)) < len(ordered(table, (0, 1, 2))), (
        f"{name} did not reorder a table that only reordering folds"
    )


def test_reorder_permutation_preserves_the_function() -> None:
    """Permuting the table renames the inputs without changing the function."""
    from esolangs.tools.boolean.helpers import permute_truth_table

    table = "01101001"
    n = 3
    for perm in [(0, 1, 2), (2, 0, 1), (2, 1, 0)]:
        permuted = permute_truth_table(table, perm)
        for row in range(2**n):
            bits = [(row >> (n - 1 - level)) & 1 for level in range(n)]
            original = sum(bits[level] << (n - 1 - i) for level, i in enumerate(perm))
            assert permuted[row] == table[original]


def test_wide_tables_skip_the_exhaustive_search() -> None:
    """Above the cap the order is picked greedily, so wide tables stay fast.

    ``12!`` is 479 million orders; an uncapped search never returns.  The
    greedy fallback still may not emit more than the identity order does.
    """
    from esolangs.tools.boolean.helpers import _ORDER_SEARCH_MAX, _decision_tree_program

    n = _ORDER_SEARCH_MAX + 2
    table = "0" * (2**n - 1) + "1"
    assert len(boolean.brainfuck(table)) <= len(
        _decision_tree_program(table, ">", "<", tuple(range(n)))
    )


def test_greedy_order_is_correct_when_it_is_not_the_identity() -> None:
    """A greedily-ordered program still computes its table.

    Above ``_ORDER_SEARCH_MAX`` the order is picked greedily rather than
    searched, and this is the only path where a *non-identity* order is
    chosen without every candidate having been built and measured, so it
    gets run rather than merely sized.  ``"01" * 64`` depends only on its
    last input, which the greedy pick fronts.
    """
    import io as _io
    from contextlib import redirect_stdout
    from unittest.mock import patch

    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.brainfuck import run
    from esolangs.tools.boolean.helpers import _greedy_input_order

    n = 7
    table = "01" * 64
    assert _greedy_input_order(table, n) != tuple(range(n)), (
        "this table must exercise a non-identity greedy order"
    )
    program = boolean.brainfuck(table)
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        buffer = _io.StringIO()
        with (
            patch("builtins.input", side_effect=bits),
            redirect_stdout(buffer),
            contextlib.suppress(SystemExit),
        ):
            run(program, io=IO())
        assert buffer.getvalue() == table[combo], f"inputs {bits}"


# The shape each boolean generator's construction takes, which decides which
# optimizations even apply to it: folding, input reordering and dependency
# reduction are tree techniques, complement/polarity is a minterm one.  The
# lists are measured (see the doc's "Which shape a boolean generator is"),
# so this test is what keeps them true rather than a comment that rots.
_MINTERM_SHAPED = {
    "a_painter_ant",
    "bfstack",
    "bit_tilde",
    "cod",
    "collatz_multiverse",
    "container",
    "home_row",
    "nocomment",
    "point_break",
    "qoibl",
    "rotfuck",
    "suffolk",
    "suptiftam",
}

# Neither model describes these.  ``wii2d`` is a route search over a grid,
# not a sum and not a tree.  The other two do not take a boolean truth table
# at all: ``jaune_multiply`` takes no argument (it multiplies two decimal
# numbers, a fixed program), and ``circlefuck_byte`` takes a *byte* table.
#
# ``slow_acv_mammalian_boolean`` is a tree, but a deliberately *unfolded*
# one, so the folding discriminator does not apply to it.  Its nodes are
# what read the input -- the branch condition is the bit ``ACCEPT`` just
# appended -- so collapsing a constant subtree would drop that subtree's
# reads and break the read-count contract above.  The tree therefore stays
# uniform depth ``n`` and its size tracks ``2**n`` whatever the table says.
#
# ``minifuck`` is a search too, and of the same kind as ``wii2d``: it emits
# whatever code it can *see* produce the table's column, so the program has
# no per-row structure to fold and its size tracks the search rather than the
# table's shape.
#
# ``pct_squared_minus_one`` emits no tree at all.  %^2^-1's only branch is
# ``t``, which jumps to position 0 and nowhere else, so the generator
# computes the answer *arithmetically* -- one affine setter per input and a
# single ``l`` -- rather than routing rows to leaves.  Its size tracks the
# constants the solver happens to find, not the table's shape, so the
# folding discriminator has nothing to measure.  It also raises on the
# ``n == 3`` tables this test uses, which it cannot separate.
_UNSHAPED = {
    "wii2d",
    "minifuck",
    "pct_squared_minus_one",
    "jaune_multiply",
    "circlefuck_byte",
    "slow_acv_mammalian_boolean",
}

# Every table depending on exactly one input, at n == 3, both polarities.
# All have ones-count 4, as parity does, so the comparison below is not
# measuring density.
_ONE_DEPENDENCY = (
    "11110000",
    "00001111",
    "11001100",
    "00110011",
    "10101010",
    "01010101",
)
_PARITY = "01101001"


@pytest.mark.parametrize(
    "name",
    sorted(
        n
        for n in boolean.__all__
        if n not in ("BOOLEAN", "instantiate")
        and callable(getattr(boolean, n, None))
        and n not in _UNSHAPED
    ),
)
def test_generator_shape_is_what_the_catalogue_says(name: str) -> None:
    """A tree generator folds a one-dependency table; a minterm sum cannot.

    The discriminator is what the size depends on.  A minterm sum spends
    one term per selected row, so at a fixed ones-count it costs the same
    whichever inputs those rows involve.  A decision tree spends one leaf
    per surviving subtree, so a table depending on a single input collapses
    to two leaves while parity keeps all eight.

    Both sides are compared at ones-count 4 so density cannot confound it.
    The one-dependency tables are tried in both split orders, because a
    generator that branches last-input-first folds ``10101010`` where an
    MSB-first one folds ``11110000`` -- reading only the latter is what
    made an earlier audit call four folding generators unfolding.
    """
    fn = getattr(boolean, name)
    best = min(len(fn(table)) for table in _ONE_DEPENDENCY)
    parity = len(fn(_PARITY))
    folds = 1 - best / parity
    if name in _MINTERM_SHAPED:
        assert folds < 0.05, (
            f"{name} is listed as minterm-shaped but folds {folds:.1%} on a "
            f"one-dependency table -- if it grew a tree, move it to the "
            f"tree-shaped list and consider whether reordering now applies"
        )
    else:
        assert folds >= 0.05, (
            f"{name} is listed as tree-shaped but folds only {folds:.1%} -- "
            f"either its folding regressed or it is a minterm sum and belongs "
            f"in _MINTERM_SHAPED"
        )
