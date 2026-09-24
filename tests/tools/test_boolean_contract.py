"""Contract tests every boolean generator must satisfy.

These are cross-cutting invariants rather than per-language behaviour: they
sweep every registered boolean generator instead of asserting against one.
"""

import contextlib
import hashlib
import importlib
import re
from collections.abc import Callable

import pytest

import esolangs
import esolangs.tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import BY_BOOLEAN, LANGUAGES
from esolangs.tools.helpers import essential_inputs
from esolangs.vm import run_until_halt_or_cycle

# Every sweep here runs an interpreter over a generated program -- the whole
# file is the execution gate -- so the module is `medium` and the inner loop
# leaves it out.  42.9s of the fast band's 193.8s was this file alone.  The
# per-param `slow` marks below still apply on top.
pytestmark = pytest.mark.medium

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
# sweep's 18.0s, and left when the emitter stopped stepping
# its straight runs one character at a time: the entry now measures 0.03s
# against the one-second budget.  ``the relevant generator tests`` has the
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
# ZTOALC L was this set's only member, at 3.0s in
# test_reordering_never_grows_a_program against 0.02s in the read-count sweep
# above; it left the set when it stopped reordering and the language has
# since been dropped.  The next entry down was streetcode at 0.06s,
# comfortably under budget, which is why the set is empty rather than
# re-pointed.
#
# A generator can be cheap in one sweep and expensive in the other, so this
# set is maintained independently of the one above.
_SLOW_REORDERING_GENERATORS: frozenset[str] = frozenset()


def _input_reading_generators() -> list[object]:
    """Every boolean generator whose language actually reads input.

    Looked up in ``BY_BOOLEAN``.  This swept a twin index keyed by the
    *text* generator's function name, so a boolean-only language was
    missing from it entirely and the sweep skipped such languages in
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
    design -- the termination convention is to halt iff the function is 0
    and loop forever iff it is 1 -- and waiting those out against an
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
        # coverage gap, which is not what this test measures.
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
    is the join.  One convention sits on top of it: a few ids drop an
    underscore the function keeps (``bf_pda`` -> ``bfpda``).
    """
    by_id = {lang.id: name for name, lang in LANGUAGES.items()}
    squashed = {lang.id.replace("_", ""): name for name, lang in LANGUAGES.items()}
    found = {}
    for fn in boolean.__all__:
        if fn in ("BOOLEAN", "instantiate") or not callable(getattr(boolean, fn, None)):
            continue
        display = (
            by_id.get(fn)
            or squashed.get(fn.replace("_", ""))
            or (BY_BOOLEAN[fn].name if fn in BY_BOOLEAN else None)
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
        f"{sorted(missing)} -- add them to BOOLEAN in tools/__init__.py"
    )
    stale = boolean.BOOLEAN - set(exported.values())
    assert not stale, (
        f"BOOLEAN names these languages but the package exports no generator "
        f"resolving to them: {sorted(stale)} -- remove them from BOOLEAN, or "
        f"export the generator from tools/__init__.py"
    )


# The tree generators that pick their input split order by measuring, and the
# builder that emits one fixed order, so a test can compare the two.
def _reordering_generators() -> list[object]:
    from esolangs.tools.algebraic_programming_language import _apl_tree_ordered
    from esolangs.tools.dimensional import _dimensional_ordered
    from esolangs.tools.egl import _egl_ordered
    from esolangs.tools.other import _forbin_ordered
    from esolangs.tools.painfuck import _painfuck_ordered
    from esolangs.tools.parameterized import (
        _bitdeque_ordered,
        _ram0_ordered,
    )
    from esolangs.tools.tape import (
        _ASCII_ZERO,
        _bf_ordered,
        _circlefuck_ordered,
        _jaune_ordered,
    )
    from esolangs.tools.three_d_brainfuck import _three_d_ordered

    entries: list[tuple[str, object, object]] = [
        (
            "algebraic_programming_language",
            boolean.algebraic_programming_language,
            _apl_tree_ordered,
        ),
        (
            "brainfuck",
            boolean.brainfuck,
            _bf_ordered,
        ),
        ("dimensional", boolean.dimensional, _dimensional_ordered),
        ("painfuck", boolean.painfuck, _painfuck_ordered),
        ("three_d_brainfuck", boolean.three_d_brainfuck, _three_d_ordered),
        ("egl", boolean.egl, _egl_ordered),
        ("ram0", boolean.ram0, _ram0_ordered),
        ("bitdeque", boolean.bitdeque, _bitdeque_ordered),
        (
            "circlefuck",
            boolean.circlefuck,
            # The byte-valued builder underneath takes a *byte* table,
            # so the contract's binary-string table is lifted the way
            # circlefuck() itself lifts it.
            lambda t, p: _circlefuck_ordered([_ASCII_ZERO + int(b) for b in t], p),
        ),
        ("forbin", boolean.forbin, _forbin_ordered),
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
            # A searching generator returns "" for an order it cannot place;
            # there is no baseline to be no worse than, and any order that
            # *did* place is an improvement on not building.
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
    from esolangs.tools.helpers import permute_truth_table

    table = "01101001"
    n = 3
    for perm in [(0, 1, 2), (2, 0, 1), (2, 1, 0)]:
        permuted = permute_truth_table(table, perm)
        for row in range(2**n):
            bits = [(row >> (n - 1 - level)) & 1 for level in range(n)]
            original = sum(bits[level] << (n - 1 - i) for level, i in enumerate(perm))
            assert permuted[row] == table[original]


def test_greedy_order_never_grows_a_wide_program() -> None:
    """The identity candidate keeps the greedy heuristic from growing output."""
    from esolangs.tools.tape import _bf_ordered

    n = 8
    table = "0" * (2**n - 1) + "1"
    assert len(boolean.brainfuck(table)) <= len(_bf_ordered(table, tuple(range(n))))


def test_order_selection_builds_at_most_two_candidates() -> None:
    """Small arities no longer trigger an exhaustive permutation contest."""
    from esolangs.tools.helpers import best_input_order

    built: list[tuple[int, ...]] = []

    def build(table: str, perm: tuple[int, ...]) -> str:
        built.append(perm)
        return table

    best_input_order("01011010", build)
    assert 1 <= len(built) <= 2
    assert built[0] == (0, 1, 2)


def test_wide_order_selection_builds_only_identity() -> None:
    """The optional greedy scorer stays off the asymptotic build path."""
    from esolangs.tools.helpers import best_input_order

    built = 0

    def build(table: str, _perm: tuple[int, ...]) -> str:
        nonlocal built
        built += 1
        return table

    table = "01" * 2**10
    assert best_input_order(table, build) == table
    assert built == 1


def test_greedy_order_is_correct_when_it_is_not_the_identity() -> None:
    """A greedily-ordered program still computes its table.

    The order is chosen without every candidate having been built and
    measured, so it gets run rather than merely sized.  ``"01" * 64``
    depends only on its last input, which the greedy pick fronts.
    """
    from esolangs.interpreters.tape_based.brainfuck import run
    from esolangs.tools.helpers import _greedy_input_order
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
    from esolangs.tools.helpers import _greedy_input_order

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

    The layout puts input ``i``'s bit at cell ``2 * perm[i]`` with that
    node's flag cell alongside, and that is the only place the permutation
    is spent -- the reads above the tree run in their own order.  So a
    mutated cell formula (``3 * perm[i]``, ``perm[i - 1]``, an off-by-one on
    the move) still emits a *runnable* brainfuck program over a
    differently-shaped tape; the generators that consume this are checked by
    running them, and running still gives the right answer whenever the
    layout is merely stretched.

    The emitted length is what the formula moves.  The six three-input
    permutations take five distinct lengths -- not six, since two orders can
    move the pointer the same total distance -- so the whole dict is
    asserted rather than one length per order, and any entry changing fails
    this.
    """
    from itertools import permutations

    from esolangs.tools.tape import _bf_ordered

    lengths = {
        perm: len(_bf_ordered("00010111", perm)) for perm in permutations(range(3))
    }
    assert lengths == {
        (0, 1, 2): 299,
        (0, 2, 1): 313,
        (1, 0, 2): 309,
        (1, 2, 0): 317,
        (2, 0, 1): 313,
        (2, 1, 0): 311,
    }

    # One and two inputs, where the tape is short enough that an off-by-one
    # in the move would still land inside it.
    assert len(_bf_ordered("01", (0,))) == 115
    assert len(_bf_ordered("0110", (0, 1))) == 205
    assert len(_bf_ordered("0110", (1, 0))) == 211


# The shape each boolean generator's construction takes, which decides which
# optimizations even apply to it: folding, input reordering and dependency
# reduction are tree techniques, complement/polarity is a minterm one.  The
# lists are measured (see the doc's "Which shape a boolean generator is"),
# so this test is what keeps them true rather than a comment that rots.
_MINTERM_SHAPED = {
    "bfstack",
}

# Neither model describes these.  ``minifuck`` is a route search over a
# grid, not a sum and not a tree.
#
# ``b_tapemark`` is a tree, but a deliberately *unfolded* one, so the
# folding discriminator does not apply: its nodes read the input, and
# collapsing a constant subtree would drop that subtree's reads and break
# the read-count contract above.  ``slow_acv_mammalian`` is a branch-free
# chain into a flat leaf table -- every table of one arity renders to the
# same length, so a 0% fold is its construction working.
#
# ``minifuck`` is a search too: it emits
# whatever code it can *see* produce the table's column, so the program has
# no per-row structure to fold and its size tracks the search rather than the
# table's shape.
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
    "home_row",
    "nocomment",
    "rotfuck",
    "suffolk",
    "super_snusp",
}

# ``minsky_swap`` is a branch-free lookup of the same class as
# ``slow_acv_mammalian``: a stage per input adds its weight to the index
# register, and a ``~`` cascade routes the index to one of two shared
# leaves, a one-digit target per row.  Every table of one arity renders to
# the same length, so a 0% fold is the construction working.  (Its
# earlier leaves were three or four commands by whether the row's LSB
# matched its answer, which read as a fold on the one-dependency table
# that *is* the LSB and on nothing else.)
#
# ``alight`` is a branch-free lookup: the inputs are folded into a row
# index by Horner's rule and the table is a string literal read with
# ``at{table, i+0.5}``, so there are no subtrees to collapse and every
# table of a given arity renders to exactly the same length.  A 0% fold is
# the construction working.
#
# ``a_painter_ant`` is a branch-free lookup of the same class: one white
# corridor cell per row, one answer paint per one-row, and the inputs walk
# the corridor by their weights, so two tables with the same ones-count
# render to the same length and a 0% fold is the construction working.
#
# ``bio`` is a telescope of one nested level per row whatever the table
# says; a one-dependency table only spares it the flat edges' adjustments,
# which is 4.4% once the doubling between the input runs is in the text.
#
# ``befunge`` and ``whitespace`` are branch-free lookups of the same class:
# Befunge writes one grid cell per table entry and reads it with ``g``, and
# Whitespace halves one literal once per index step, so two tables with the
# same ones-count render to the same length and a 0% fold is the construction
# working.
_UNSHAPED = {
    "a_painter_ant",
    "befunge",
    "bio",
    "alight",
    "malbolge",
    "minsky_swap",
    "b_tapemark",
    "minifuck",
    "one_two_three",
    "slow_acv_mammalian",
    "container",
    "whitespace",
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
    ("name", "fn"),
    sorted(
        (lang.id, lang.boolean)
        for lang in LANGUAGES.values()
        if lang.boolean is not None
    ),
    ids=lambda v: v if isinstance(v, str) else "",
)
@pytest.mark.parametrize(
    ("table", "fragment"),
    [("011", "power-of-two"), ("0123", "only '0' and '1'")],
)
def test_a_malformed_table_is_refused_in_the_shared_words(
    name: str, fn: object, table: str, fragment: str
) -> None:
    """Every generator rejects a malformed table in the *shared* validator's words.

    The sibling above pins that a nullary table is refused; this pins the
    other two rejections, and pins them by wording rather than by type.  The
    registered generators route these through
    :func:`~esolangs.tools.helpers._validate_truth_table`, so the
    message is uniform today -- a generator that grows its own validator
    keeps raising ``ValueError`` and passes every other check while telling
    the caller something different from its siblings.

    That gap is not hypothetical.  It is what a blind reconstruction of
    ``packlang`` did: inlined its own checks, reported ``"must be a binary
    string"`` for ``"0123"`` and ``"needs at least one input: a power-of-two
    length"`` for ``"011"``, and nothing in the suite noticed.  These two
    messages were pinned per generator in four files and packlang was in
    none of them; the generator-convention test checks the signature, not
    the words.

    The second assertion is what catches that ``"011"`` case, and is the
    reason this is not merely a substring check: a *malformed* table and a
    *nullary* one are different defects, so the nullary wording must not
    appear here.  Reporting "needs at least one input" for a three-entry
    table names the wrong problem while still containing the right
    substring.  No registry generator conflates them today.

    Swept from the registry for the same reason as the nullary check: it has
    to stay true when the next language lands.
    """
    assert callable(fn), name
    with pytest.raises(ValueError, match=re.escape(fragment)) as caught:
        fn(table)
    assert "at least one input" not in str(caught.value), (
        f"{name} on {table!r} said {str(caught.value)!r}, which reports a "
        f"nullary table -- {table!r} is malformed, not nullary, and the two "
        f"are separate rejections with separate words"
    )


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
# the whole registry was swept at n=1..10 on both shapes.
#
# Ten is here because it was made affordable, not because the cost was
# waved through.  This sweep stopped at five for a long time, then briefly
# at eight: n<=10 cost 141s of CPU, and n=9 alone was 53s of it.  Three
# generators were then measured and rewritten:
#
#     minifuck        42.8s -> 8.6s     polynomial      28.4s -> 5.5s
#     one_two_three   17.8s -> 3.7s
#
# plus a generic pass on input ordering.  Exhaustive ordering was later
# removed: its n=6 registry sweep cost 10.7s instead of 0.79s for a 0.06%
# aggregate size saving.  Generators now compare the identity with at most
# one greedy order; stack languages without a safe greedy mapping retain
# their natural order.
#
# Across everything here, 1357 of the registry's 1380 programs are
# byte-identical: the 23 that moved are nine factor arities that used to
# refuse and one_two_three's n=4..10 both shapes, which the mark respacing
# cut by 82% overall.  Minifuck's Pascal inverse restored the n=9 contest.
#
# Ten still peaks at 619MB RSS on Polynomial's n=10 dense table, 17MB of
# program text (Circuit Diagram's H-layout, once the peak at 306MB of text,
# is 8MB and 255MB RSS since it was sized from its lattice).  Of that RSS
# only 154MB is ever live -- the last merge's 59M-digit product held as a
# decimal, its C string and its Python copy at once -- and the rest is
# pages the allocator keeps after freeing them.  That memory, not the
# time, is what keeps the band split:
# n <= _QUICK_ARITY runs in the default gate and the rest is marked slow.
# Both bands assert the same thing; splitting them keeps the fast gate at
# the whole registry and ~3s it had when this swept to five.
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

# No generator falls short of _MAX_ARITY on either shape any more.  The
# caps that used to bind below it were constructions' limits:
# interprogck8's ``DownAccLines`` reach (a long hop needed an express
# through one-line rungs parked in meadows) left with its language, and
# factor's digit budget (a size policy rather than anything Factor says)
# was retired.  If a generator stops building at some arity,
# ``test_every_generator_builds_up_to_ten_inputs`` fails and the
# measurement that put the cap here belongs back in this table, with the
# phrase its own refusal is built around.
# Malbolge's five-cell mixer is injective with pairwise gap >= 3 through ten
# inputs, so it now covers the whole sweep; the fifteen-input refusal lives in
# ``tests/tools/test_boolean_malbolge.py``.  No generator falls short of
# _MAX_ARITY on either shape any more.
_ARITY_CAPPED: dict[tuple[str, str], tuple[int, str]] = {}


# The two table shapes every generator is built against.  A dense
# pseudo-random table and parity fail *differently*: factor's retired digit
# budget ran out a rung earlier on parity than on dense, and Polynomial's
# 1934-instruction cap refuses dense n=11 (2447) while parity fits far past
# it.  A single-shape sweep reports the wrong ceiling for all three, which
# is why both shapes are built at every arity and why the cap table is
# keyed by shape.
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


def _nested_dense(n: int) -> str:
    """A dense table whose every arity *extends* the one below it.

    :func:`_dense` seeds on ``n``, so its tables at consecutive arities are
    independent draws: how much of each one folds is an accident of that
    draw, and a statistic comparing two arities reads the difference between
    two unrelated tables as growth.  That is fine for the coverage sweeps,
    which want one hard table per arity and pin its size, but it is noise to
    anything measuring a *series* -- re-drawing the tables moves the scaling
    contract's reading by +-2% for the generators whose size depends on the
    table at all.

    Here one stream is drawn once and every arity takes a prefix of it, so
    ``_nested_dense(n)`` restricted to ``x_n = 0`` is exactly
    ``_nested_dense(n - 1)``.  The arities then form a family of functions
    rather than a sample, which is what a growth measurement needs.
    """
    digest = hashlib.sha256(b"nested-dense").digest()
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


# Every table of arity one, two and three: 4 + 16 + 256 = 276 of them.  The
# sweep above sees two tables per arity, so a generator that refuses some
# *third* shape -- an all-but-one-row table, a table whose fold leaves one
# essential input, a single minterm -- passes it and fails here.  This is the
# exhaustive-domain half, and n <= 3 is the last arity where exhaustive is a
# thing one can afford: n=4 is 65536 tables per generator.
#
# It is the executable witness `the relevant tests` names for the totality
# entries.  A structural argument says a generator returns on every table of
# every arity; this checks the whole domain at the arities where "whole" is
# reachable, which is what stops the argument from resting on its own prose.
_EXHAUSTIVE_ARITY = 3


def _all_tables(arity: int) -> list[str]:
    """Every truth table of every arity from one up to ``arity``."""
    return [
        format(k, f"0{2**n}b") for n in range(1, arity + 1) for k in range(2 ** (2**n))
    ]


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_is_total_on_every_small_table(name: str) -> None:
    """Every generator returns a program for *every* table up to three inputs.

    Totality, on the domain where it can be checked outright rather than
    argued: no table in it raises, and none yields the empty string.  A
    generator that refuses one table in 276 is not total, and the two-shape
    sweep above would not see it -- ``_dense`` and ``_parity`` are two
    points, and the constructions here fold, complement and reorder, so
    which table is hardest is not a property either point has.

    Non-empty rather than correct: a returned program is what the claim is
    about.  ``test_every_generator_runs_what_it_builds`` is what runs one.
    """
    fn = getattr(boolean, name)
    for table in _all_tables(_EXHAUSTIVE_ARITY):
        program = str(fn(table))
        assert program, f"{name} built an empty program for {table!r}"


def test_cm_constants_builds_only_the_bootstrap_for_small_values() -> None:
    """Nothing above k2 is needed, so the plan sieve is never entered.

    ``_cm_constants`` bootstraps k1 and k2 unconditionally and only then
    extends; a caller wanting nothing larger gets those four lines and no
    build plan at all.
    """
    from esolangs.tools.helpers import _cm_constants

    lines = _cm_constants([1, 2])
    assert len(lines) == 4
    assert all(line.endswith("NOT PRINT.") for line in lines)
    assert _cm_constants([]) == lines


# The build sweep above proves every generator *returns* a program up to ten
# inputs.  It never runs one, and nothing else ran one past
# four inputs either.  Grapheme's variable keys collided with two of its own
# command characters from slot 5 onward, so from six essential inputs it
# emitted a program its own interpreter could not execute -- and the sweep
# saw a healthy non-empty string every time.
#
# The property that matters is not table *size* but how many inputs are
# *essential*: a dense n=9 table that folds down to one input exercises one
# slot and sails through.  A single-minterm table is the cheap way to force
# all n of them -- its one 1 makes every input matter, while the program
# stays small enough to execute.  Grapheme n=9 costs 0.18s that way against
# 11.7s for an all-essential random table, which is the difference between a
# test and a nightly job.
#
# n=6 is the floor that would have caught the bug and is affordable for all
# 60: 13.4s of work in total, no language over 4.3s, and none excluded.
# Restoring the old key alphabet makes this fail, which is the only
# evidence that the arity is high enough.
# There is deliberately no exclusion table here -- an empty one is the
# finding, and if a language ever needs to be added, it needs a reason and a
# cost beside it like ``_ARITY_CAPPED`` carries.
#
# A wider probe backs the choice rather than a hunch: 517 evaluations over
# the whole registry, both shapes, n=5..8, found zero further failures of this
# kind, so Grapheme was the only one.  22 language/arity pairs were too
# expensive to reach and are *unchecked*, not passing.
_ONE_MINTERM_ARITY = 6


def _one_minterm(n: int) -> str:
    """A single 1, which makes every input essential at minimum size."""
    return "1" + "0" * (2**n - 1)


def _one_hot(n: int) -> str:
    """1 exactly where one input is set.

    The second shape, and it is here because one minterm was not enough.
    Sophie emitted programs that read ``n + 1`` inputs and died on their own
    generator's output, and this sweep did not see it: parity, dense, a
    single minterm, majority and a mux all passed at n=6, and one-hot
    failed.  Arity was never the missing coordinate -- Sophie is clean on
    every one of the 65536 tables at n <= 4 and collides on 35% of random
    tables at n=7 -- so a second *shape* buys what a seventh input does not.

    It costs 30.5s of work across the registry, against 13.4s for one minterm.  A
    third shape was measured and dropped: a 2-CNF at n=6 costs 67.2s, 37s of
    it Circuit Diagram alone, and caught nothing this does not.
    """
    return "".join(str(int(bin(row).count("1") == 1)) for row in range(2**n))


#: The table shapes every generator's *output* is executed against.
_EXEC_SHAPES = (("one_minterm", _one_minterm), ("one_hot", _one_hot))


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
@pytest.mark.parametrize(
    "name",
    sorted(n for n in esolangs.list_languages() if LANGUAGES[n].boolean is not None),
)
@pytest.mark.slow
def test_every_generator_runs_what_it_builds(
    name: str, make: Callable[[int], str]
) -> None:
    """Build a table using all six inputs, execute it, and check every row.

    Parameterized per language rather than looped so that a failure names
    the one that broke instead of stopping at the first.
    """
    table = make(_ONE_MINTERM_ARITY)
    assert esolangs.evaluate(name, table, timeout=30) == table


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
def test_the_exec_tables_really_need_every_input(make: Callable[[int], str]) -> None:
    """The guards above are worthless if their tables fold.

    This is the assumption the whole sweep rests on, and it is one line to
    check, so it is checked rather than asserted in a comment.
    """
    table = make(_ONE_MINTERM_ARITY)
    assert len(essential_inputs(table, _ONE_MINTERM_ARITY)) == _ONE_MINTERM_ARITY


#: What ``docs/limitations.md`` says the expensive generators cost, as
#: ``(n=8 size, n=9 size, growth per input)``.  Sizes are exact because a
#: program's length is deterministic for a fixed generator and table; the
#: ratio carries a band because it drifts a little with arity.
#:
#: Timings are deliberately absent.  The document states a few and calls
#: them approximate, and asserting one here would fail whenever the machine
#: is busy -- which, on a suite that runs four workers, is always.
_DOCUMENTED_SIZES: dict[str, tuple[int, int, float]] = {
    "Circuit Diagram": (1_780_773, 2_505_897, 1.4),
    "ROTfuck": (15_240, 29_472, 1.9),
    "Polynomial": (1_589_968, 5_016_851, 3.2),
    "SLOW ACV MAMMALIAN": (456_394, 798_829, 1.8),
    "bit~": (28_210, 56_676, 2.0),
    "123": (22_964, 45_728, 2.0),
    "Factor": (16_711, 35_323, 2.1),
}


# The roadmap's original scaling queue.  A row leaves ``_OPEN_SCALING`` only
# after an O(T) construction or a language-wide lower bound; it enters when
# the construction is read super-linear, whatever the twelve doublings
# measure.  Streetcode left: its per-level hall was the
# ``Theta(T log T)`` source and the alternating-axis H-tree replaced it.
_LINEAR_SCALING = {
    "a_painter_ant",
    "addsubjump",
    "arrowqueue",
    "back",
    "bitdeque",
    "brainif",
    "circuit_diagram",
    "clockwise",
    "container",
    "dig",
    "forth",
    "flowchart",
    "inject",
    "jaune",
    "laserfuck",
    "minifuck",
    "one_two_three",
    "ram0",
    "sbleq",
    "slow_acv_mammalian",
    "streetcode",
    "vandevelo",
}
_LANGUAGE_SUPERLINEAR_SCALING = {"factor"}
_OPEN_SCALING = {
    "malbolge",
    "polynomial",
}


def test_remaining_scaling_audit_is_exhaustive() -> None:
    """Every generator in the scaling audit remains classified."""
    expected = {
        "a_painter_ant",
        "one_two_three",
        "circuit_diagram",
        "minifuck",
        "factor",
        "polynomial",
        "addsubjump",
        "arrowqueue",
        "back",
        "bitdeque",
        "brainif",
        "clockwise",
        "container",
        "dig",
        "flowchart",
        "forth",
        "inject",
        "jaune",
        "laserfuck",
        "malbolge",
        "ram0",
        "sbleq",
        "slow_acv_mammalian",
        "streetcode",
        "vandevelo",
    }
    classified = _LINEAR_SCALING | _LANGUAGE_SUPERLINEAR_SCALING | _OPEN_SCALING
    assert classified == expected
    assert classified <= set(BY_BOOLEAN)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.slow) if name == "streetcode" else name
        for name in sorted(_LINEAR_SCALING)
    ],
)
def test_converted_generators_scale_linearly(name: str) -> None:
    """Doubling a wide unfolded table at most doubles generated text."""
    fn = getattr(boolean, name)
    # The grid H-layouts have different odd/even finite-size constants; their
    # all-arity area bounds are checked with their construction invariants.
    arities = (8, 9) if name == "circuit_diagram" else (11, 12)
    sizes = [len(fn(_parity(n))) for n in arities]
    if name == "minifuck":
        assert all(size <= 70 * 2**n for size, n in zip(sizes, arities, strict=True))
    else:
        assert sizes[1] <= 2 * sizes[0]


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(_DOCUMENTED_SIZES))
def test_the_expensive_generators_grow_as_documented(name: str) -> None:
    """``docs/limitations.md`` tells a reader whether n=11 is affordable.

    It answers that with a growth law rather than an ``estimate()`` API,
    because the generators the question is about have no cap arithmetic to
    consult -- Circuit Diagram and ROTfuck never refuse -- so an
    estimator for them would be a hand-fitted size model, which is the kind
    of frozen table this repository turns back into a rule.  A rule in prose
    is only worth having if it is checked, so this is the check.

    n=9 is the ceiling here on purpose: Circuit Diagram's deliberately roomy
    H-layout is already 2.5MB there, and one more arity does not check its
    proved area recurrence better.
    """
    at_eight, at_nine, ratio = _DOCUMENTED_SIZES[name]
    assert len(esolangs.generate(name, _dense(8))) == at_eight
    assert len(esolangs.generate(name, _dense(9))) == at_nine
    assert at_nine / at_eight == pytest.approx(ratio, abs=0.35)


@pytest.mark.slow
def test_nothing_else_is_anywhere_near_that_big() -> None:
    """The document's "every other generator is under 600KB at n=9".

    A claim about the *rest* of the registry is the half a table of named
    languages cannot make, and it is the half that decides whether a reader
    has to think about size at all.  The first draft said "under a megabyte"
    and two generators were over it, which is why this exists.
    """
    biggest = max(
        (len(esolangs.generate(name, _dense(9))), name)
        for name in esolangs.list_languages()
        if name not in _DOCUMENTED_SIZES and LANGUAGES[name].boolean is not None
    )
    assert biggest[0] < 600_000, biggest
    assert biggest[1] == "Streetcode"
