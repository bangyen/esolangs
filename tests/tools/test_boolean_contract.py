"""Contract tests every boolean generator must satisfy.

These are cross-cutting invariants rather than per-language behaviour: they
sweep every registered boolean generator instead of asserting against one.
"""

import contextlib
import hashlib
import importlib
import re

import pytest

import esolangs.tools.boolean as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_BOOLEAN, BY_FUNCTION, LANGUAGES
from esolangs.vm import run_until_halt_or_cycle

# One constant table against one that folds nothing.  A generator loses reads
# by *folding*, so the comparison needs a table that folds completely and one
# that folds not at all; near-constant tables in between produce intermediate
# counts but never catch a generator these two miss.  This sweep runs every
# interpreter on every table on every pytest invocation, so cases that add
# cost without adding detection are not worth carrying -- ``00000001`` and
# ``11111110`` were dropped for that reason.
#
# ``01101001`` is parity, the one table with no constant subtree above a
# single row, so nothing about it can fold.
_TABLES = ["00000000", "01101001"]


# Generators marked ``slow`` for a cost that is a *regression*, not the cost
# the construction ought to carry.  The rule is a one-second budget per entry
# in this sweep.  The mark keeps the fast run fast; it does not make the cost
# acceptable, so an entry leaves when the cost is paid for rather than when
# it stops being noticed.
#
# The set is empty.  ``minifuck`` was its last member, at 14.9s of the
# sweep's 18.0s, and left on 2026-09-06 when the emitter stopped stepping
# its straight runs one character at a time: the entry now measures 0.03s
# against the one-second budget.  ``docs/minifuck_generator.md`` has the
# full ledger of what entered and left this set, with the measurement
# behind each.
_SEARCHING_GENERATORS_REGRESSED: frozenset[str] = frozenset()

# Naming the languages rather than timing them at collection time is
# deliberate: a wall-clock threshold evaluated during collection would make
# the selected test set depend on how loaded the machine is, so a run could
# silently cover less than the last one.  Re-measure and edit this set when
# a generator's cost changes.
_SEARCHING_GENERATORS: frozenset[str] = frozenset()

# The same one-second rule, applied to the two reordering sweeps.  Those call
# the ``_*_ordered`` builder once per input order for every table up to three
# inputs, so a generator that *searches* pays that cost repeatedly.
#
# ``ztoalc_l_boolean`` was this set's only member, at 3.0s in
# test_reordering_never_grows_a_program against 0.02s in the read-count sweep
# above.  It no longer reorders at all -- it constructs one branch-free
# lookup whose length is permutation-invariant -- so it left both the sweep
# and this set.  The next entry down was streetcode at 0.06s, comfortably
# under budget, which is why the set is now empty rather than re-pointed.
#
# A generator can be cheap in one sweep and expensive in the other, so this
# set is maintained independently of the one above.
_SLOW_REORDERING_GENERATORS: frozenset[str] = frozenset()


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
        if name in _SEARCHING_GENERATORS | _SEARCHING_GENERATORS_REGRESSED:
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
    fn, lang, _run = entry
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
    machine_cls = getattr(module, "_Machine")  # noqa: B009
    # Every interpreter names its state object ``_Machine``, so this reads
    # the same count for every language.  It used to fall back to ``run``
    # for the three that spelled the class ``State``: that measured a whole
    # run rather than a stepped one, silently, for exactly those three.
    # A program may halt through its own error path or call exit; either way the
    # read count up to that point is what matters here.
    with contextlib.suppress(Exception, SystemExit):
        of = getattr(machine_cls, "of", None)
        build = of if callable(of) else machine_cls
        run_until_halt_or_cycle(build(source, io))
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
    from esolangs.interpreters.tape_based.brainfuck import run
    from esolangs.tools.boolean.helpers import _greedy_input_order
    from tests.interpreters.runner import run_program

    n = 7
    table = "01" * 64
    assert _greedy_input_order(table, n) != tuple(range(n)), (
        "this table must exercise a non-identity greedy order"
    )
    program = boolean.brainfuck(table)
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        stdin = "".join(f"{bit}\n" for bit in bits)
        got = run_program(run, program, stdin)
        assert got == table[combo], f"inputs {bits}"


def test_the_greedy_order_is_the_documented_one() -> None:
    """What the heuristic picks, per table, not merely that it is valid.

    ``_greedy_input_order`` scores each unchosen input by how many constant
    subtrees splitting on it would produce, and takes the best.  A corrupted
    score still returns *a* permutation, so every generator downstream still
    emits a correct program -- just a longer one -- and no truth-table check
    anywhere sees the difference.  The chosen order is the observable.

    Both halves of the split are scored, and the tie rule is "keep the
    lowest index", which is what makes the identity the answer for a table
    no order helps.  94 of the 256 three-input tables get a non-identity
    order, so the two rules are separable here rather than only in theory.
    """
    from esolangs.tools.boolean.helpers import _greedy_input_order

    # Tables the heuristic reorders, and the order it picks.
    assert _greedy_input_order("00000101", 3) == (0, 2, 1)
    assert _greedy_input_order("00010001", 3) == (1, 2, 0)

    # Tables no split helps: ties keep the lowest index, giving the identity.
    for table in ("00011011", "01000111", "00111100", "01101001"):
        assert _greedy_input_order(table, 3) == (0, 1, 2), table

    # And the wide table the run-it test above uses, pinned positively.
    assert _greedy_input_order("01" * 64, 7) == (6, 0, 1, 2, 3, 4, 5)

    reordered = sum(
        1
        for value in range(256)
        if _greedy_input_order(format(value, "08b"), 3) != (0, 1, 2)
    )
    assert reordered == 94


def test_the_tree_program_spends_its_permutation_on_the_tested_cell() -> None:
    """``perm`` reaches the emission in exactly one place, and it shows.

    The layout puts input ``i``'s bit at cell ``2 * perm[i]`` with its
    complement alongside, and that is the only place the permutation is
    spent -- the reads and the complement construction above the tree run
    in their own order.  So a mutated cell formula (``3 * perm[i]``,
    ``perm[i - 1]``, an off-by-one on the move) still emits a *runnable*
    brainfuck program over a differently-shaped tape; the generators that
    consume this are checked by running them, and running still gives the
    right answer whenever the layout is merely stretched.

    The emitted length is what the formula moves.  All six three-input
    permutations come out distinct, so the mapping is pinned rather than
    just its identity case.
    """
    from itertools import permutations

    from esolangs.tools.boolean.helpers import _decision_tree_program

    lengths = {
        perm: len(_decision_tree_program("00010111", ">", "<", perm))
        for perm in permutations(range(3))
    }
    assert lengths == {
        (0, 1, 2): 769,
        (0, 2, 1): 785,
        (1, 0, 2): 783,
        (1, 2, 0): 799,
        (2, 0, 1): 797,
        (2, 1, 0): 797,
    }

    # One and two inputs, where the tape is short enough that an off-by-one
    # in the move would still land inside it.
    assert len(_decision_tree_program("01", ">", "<", (0,))) == 225
    assert len(_decision_tree_program("0110", ">", "<", (0, 1))) == 485
    assert len(_decision_tree_program("0110", ">", "<", (1, 0))) == 499


# The shape each boolean generator's construction takes, which decides which
# optimizations even apply to it: folding, input reordering and dependency
# reduction are tree techniques, complement/polarity is a minterm one.  The
# lists are measured (see the doc's "Which shape a boolean generator is"),
# so this test is what keeps them true rather than a comment that rots.
_MINTERM_SHAPED = {
    "a_painter_ant",
    "algebraic_programming_language",
    "bfstack",
    "container",
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
# ``ztoalc_l_boolean`` emits no tree either, and for a reason the folding
# discriminator cannot see.  It builds one branch-free chunked lookup: the
# inputs are folded into a chunk index and a bit index, the table's
# four-row chunks are stored as codes, and a shared decode array turns the
# selected code's bit into the answer.  There are no subtrees to collapse,
# and the program's size tracks the nonzero-chunk and distinct-code counts,
# not the table's shape.  (It is not minterm-shaped either: a minterm sum's
# cost is one term per selected row, where a chunk set carries four rows
# and the emitted length is a Collatz placement -- the L-th smallest value
# of a committed anchor's trajectory -- rather than a function of the row
# count.)
#
# ``pct_squared_minus_one`` emits no tree at all.  %^2^-1's only branch is
# ``t``, which jumps to position 0 and nowhere else, so the generator
# computes the answer *arithmetically* -- one affine setter per input and a
# single ``l`` -- rather than routing rows to leaves.  Its size tracks the
# constants the solver happens to find, not the table's shape, so the
# folding discriminator has nothing to measure.  It also raises on the
# ``n == 3`` tables this test uses, which it cannot separate.
#
# ``one_two_three`` emits no tree either, and for a related reason: 123's
# answer is whether the program halts, and what decides that is the pointer
# phase the embeds leave behind, so the generator emits a flat plan whose
# length tracks the modulo-four decode rather than any table shape.  It also
# raises on the ``n == 3`` tables this test uses -- an ignored input still
# has to be embedded, and every fill moves the pointer that carries the
# answer, so the projection this test's folding measures cannot happen.
# Minterm sums that nonetheless gain on a one-dependency table, and *not* by
# folding: they apply dependency reduction (technique 10), emitting the
# smaller table that a degenerate one really is.  The distinction the shape
# test would otherwise lose is that these have no subtrees at all -- the sum
# is simply over fewer rows because the table was rewritten over its
# essential inputs, so the gain tracks the dropped *arity* rather than any
# collapsed structure.  Reordering does not become applicable to them the way
# it would if they had grown a tree, which is why they are neither list.
_REDUCING = {
    "bit_tilde",
    "cod",
    "collatz_multiverse",
    "home_row",
    "nocomment",
    "point_break",
    "qoibl",
    "rotfuck",
    "suffolk",
    "suptiftam",
    "super_snusp",
}

# ``alight`` is a branch-free lookup of the same class as
# ``ztoalc_l_boolean``: the inputs are folded into a row index by Horner's
# rule and the table is a string literal read with ``at{table, i+0.5}``, so
# there are no subtrees to collapse and every table of a given arity renders
# to exactly the same length.  A 0% fold is the construction working.
# (ZTOALC L's chunked variant of the same fold keeps it in this list for
# the same reason: lookup size does not track table shape.)
_UNSHAPED = {
    "alight",
    "wii2d",
    "minifuck",
    "ztoalc_l_boolean",
    "pct_squared_minus_one",
    "one_two_three",
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
    ("name", "fn"),
    sorted(
        (lang.id, lang.boolean)
        for lang in LANGUAGES.values()
        if lang.boolean is not None
    ),
    ids=lambda v: v if isinstance(v, str) else "",
)
@pytest.mark.parametrize("table", ["0", "1"])
def test_a_one_entry_table_is_refused(name: str, fn: object, table: str) -> None:
    """No generator builds a program for a nullary table.

    ``"0"`` and ``"1"`` are well-formed tables of length ``2**0``, so they
    clear the power-of-two check -- and used to reach the generators, where
    forty-four of them built a program, twenty-four raised ``IndexError``
    reaching for an input that was not there, and sixteen more raised
    ``negative shift count``.  A nullary table is a constant rather than a
    function of any input, and these generators exist to build programs
    that read and branch, so every one of them refuses it with the shared
    validator's ``ValueError``.

    Swept from the registry rather than written per generator: this is the
    check that has to stay true when the next language lands.
    """
    assert callable(fn), name
    with pytest.raises(ValueError, match="at least one input") as caught:
        fn(table)
    assert "at least one input" in str(caught.value), f"{name} on {table!r}"


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
    if name in _REDUCING:
        # The gain is real but is not a fold, so assert it from the other
        # direction: the saving must come from dropped inputs, which means a
        # table that depends on *every* input cannot be shortened at all.
        assert folds >= 0.05, (
            f"{name} is listed as applying dependency reduction but gains "
            f"only {folds:.1%} on a one-dependency table -- its reduction "
            f"has regressed"
        )
        for table in _ONE_DEPENDENCY:
            assert len(fn(table)) < parity, table
        return
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


# Every boolean generator builds a table at n <= _MAX_ARITY.  Ten inputs:
# the whole registry was swept at n=1..10 on both shapes, and exactly one
# generator falls short -- WII2D, dense only, recorded below.  Every other
# one of the 69 builds both shapes at n=10.
#
# Ten is here because it was made affordable, not because the cost was
# waved through.  This sweep stopped at five for a long time, then briefly
# at eight: n<=10 cost 141s of CPU, and n=9 alone was 53s of it.  Five
# generators were then measured and rewritten:
#
#     minifuck        42.8s -> 8.6s     interprogck8    14.7s -> 3.5s
#     polynomial      28.4s -> 5.5s     wii2d            7.2s -> 1.3s
#     one_two_three   17.8s -> 3.7s
#
# plus a generic pass on the order search below.  The whole n=1..10 sweep
# is now 46.1s of CPU.  Per arity: n=6 6.2s, n=7 1.0s, n=8 5.7s, n=9 7.2s,
# n=10 23.8s.
#
# n=6 costing six times n=7 is not a measurement error and not warmup -- it
# is ``_ORDER_SEARCH_MAX = 6`` in ``helpers.py``.  At n <= 6 a reordering
# generator builds all ``n!`` = 720 candidate orders and keeps the
# shortest; at n=7 it switches to the greedy ``O(n**2)`` pick, so a
# *bigger* table is hundreds of times faster (laserfuck 1.03s at six
# against 0.002s at seven, streetcode 0.56s against 0.002s).
#
# What that 720-build search buys, measured by running the registry at n=6
# with the cap at 6 and at 5: 3,193,830 chars in 10.7s against 3,195,778 in
# 0.79s.  Only 13 of 138 cases differ and the registry total is 0.06%, but
# the win is concentrated, not absent -- ram0 parity 29.9% shorter under the
# search, circlefuck dense 26.4%, six_five dense 14.2%, unsquare dense
# 13.5%.  Lowering the cap is a bad trade rather than a free 10s.
#
# **Measuring that requires patching six modules, not one.**  ``laserfuck``,
# ``streetcode``, ``stack``, ``six_five`` and ``tape`` each do ``from
# .helpers import _ORDER_SEARCH_MAX``, a by-value import, so patching
# ``helpers`` alone leaves the two most expensive generators exhaustive and
# reports the greedy side as 5.17s instead of 0.79s.
#
# n=6 was 10.0s until the candidates themselves were made cheap.  The
# search still builds every one of the 720 and measures it -- see the
# ``best_input_order`` docstring for why the count cannot come down without
# going per-language -- so that pass left all 1380 programs byte-identical.
#
# Across everything here, 1356 of the registry's 1380 programs are
# byte-identical: the 24 that moved are nine factor arities that used to
# refuse, minifuck's dense n=9 at +6.4%, and one_two_three's n=4..10 both
# shapes, which the mark respacing cut by 82% overall.
#
# Ten still peaks at 637MB RSS on Circuit Diagram's n=10 dense table, 306MB
# of program text.  That memory, not the time, is what keeps the band split:
# n <= _QUICK_ARITY runs in the default gate and the rest is marked slow.
# Both bands assert the same thing; splitting them keeps the fast gate at
# the 69 items and ~3s it had when this swept to five.
_MAX_ARITY = 10
_QUICK_ARITY = 5

_ARITY_BANDS = (
    pytest.param(range(1, _QUICK_ARITY + 1), id="quick"),
    pytest.param(
        range(_QUICK_ARITY + 1, _MAX_ARITY + 1),
        id="deep",
        marks=pytest.mark.slow,
    ),
)

# The generators that do not reach _MAX_ARITY, keyed by ``(name, shape)``
# because a cap can bind on one table shape and not the other.  WII2D is
# exactly that: a per-name cap of 9 would demand its parity n=10 refuse,
# which it does not -- that shape builds in 350 characters.
#
#   wii2d refuses n=10 dense because the decode spans 512 index points past
#   the ``_WII2D_MAX_INDEX_DOMAIN = 256`` cost guard.  Unlike the two caps
#   below, raising the constant does *not* buy the table: at domain 512 the
#   decode ratchets -- live count crawls 512 -> 475 over 19 steps while the
#   bit length doubles every step, reaching 1.09M bits, the 19th step alone
#   144s -- and refuses on the magnitude bound instead.  It is a wall of the
#   exactly-once embed convention; ``docs/walls.md`` carries the curve.
#
# Two generators that used to be here are gone, and both of those refusals
# were the *construction's* limit rather than the language's:
#
#   interprogck8 capped at n=3 because one ``DownAccLines`` reaches 255
#   lines and the n=4 bit-0 crossing spans 452.  Long hops now ride an
#   express through one-line rungs parked in meadows.
#
#   factor capped at n=3 on CPython's 4300-digit ``int``-render guard, then
#   at n=6 on the 16000-digit budget that replaced it.  Both are size
#   policies rather than anything Factor says.
#
# An entry needs the measurement that put it there and the phrase its own
# refusal is built around -- asserting only that something refused would
# accept a generator that had started failing for an unrelated reason,
# since an encoding bug reads exactly like a cap from the outside.
_ARITY_CAPPED: dict[tuple[str, str], tuple[int, str]] = {
    ("wii2d", "dense"): (9, "cost guard; below the bound this is a size/time"),
}


# The two table shapes every generator is built against.  A dense
# pseudo-random table and parity fail *differently*: WII2D reaches n=10 on
# parity but stops at n=9 dense, factor's digit budget runs out a rung
# earlier on parity than on dense, and Polynomial's 1934-instruction cap
# refuses dense n=11 (2910) while parity fits far past it.  A single-shape
# sweep reports the wrong ceiling for all three, which is why both shapes
# are built at every arity and why the cap table is keyed by shape.
def _dense(n: int) -> str:
    """A deterministic dense pseudo-random table -- the worst case to fold."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _parity(n: int) -> str:
    """Parity -- the table with no constant subtree above a single row."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**n))


_SHAPES = (("dense", _dense), ("parity", _parity))


@pytest.mark.parametrize("arities", _ARITY_BANDS)
@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_builds_up_to_ten_inputs(name: str, arities: range) -> None:
    """Every boolean generator builds every arity up to :data:`_MAX_ARITY`.

    The sweep that pins the registry's *coverage*: a generator that
    silently stops covering an arity it used to cover is a regression no
    per-language suite catches, because each of those tests picks the
    arities it asserts against.

    Both shapes are built at every arity, since a generator can cover one
    and refuse the other at the same n.  A capped generator must still
    build everything up to its cap and must refuse past it with the
    ``ValueError`` its entry pins -- a refusal that raises something else
    is a bug, and one that returns a program is a wrong answer, which is
    worse than either.
    """
    fn = getattr(boolean, name)
    for n in arities:
        for shape, make in _SHAPES:
            cap, pattern = _ARITY_CAPPED.get((name, shape), (_MAX_ARITY, ""))
            table = make(n)
            if n <= cap:
                program = str(fn(table))
                assert program, f"{name} built an empty program at n={n} ({shape})"
            else:
                with pytest.raises(ValueError, match=re.escape(pattern)):
                    fn(table)


def test_arity_caps_are_still_caps() -> None:
    """A capped generator that grew past its cap must leave ``_ARITY_CAPPED``.

    The table above is a record of measurements, so it goes stale in the
    direction that matters: a generator whose construction is extended
    keeps its entry and this suite keeps asserting the *old* refusal, which
    turns a fixed limitation into a permanently pinned one.  Asserting the
    cap is still binding is what makes the entry falsifiable.

    A cap below :data:`_MAX_ARITY` is only a cap if it is also the *last*
    arity that builds, so both ends are checked on the shape the entry is
    keyed to -- an entry whose cap drifted low would otherwise pass here
    while hiding coverage the generator still has.
    """
    makers = dict(_SHAPES)
    for (name, shape), (cap, pattern) in sorted(_ARITY_CAPPED.items()):
        fn = getattr(boolean, name)
        make = makers[shape]
        assert str(fn(make(cap))), (
            f"{name} no longer builds at its cap n={cap} ({shape})"
        )
        with pytest.raises(ValueError, match=re.escape(pattern)):
            fn(make(cap + 1))
