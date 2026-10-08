"""Contract tests every boolean generator must satisfy."""

import contextlib
import hashlib
import importlib
from collections.abc import Callable

import pytest

import esolangs
import esolangs.tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.raster import Raster
from esolangs.registry import BY_BOOLEAN, INTERPRETERS, LANGUAGES
from esolangs.tools.helpers import essential_inputs
from esolangs.vm import run_until_halt_or_cycle
from tests.generator_support import evaluate_generated
from tests.source_support import source_units

# Every sweep here runs an interpreter over a generated program -- the whole
# file is the execution gate -- so the module is `medium` and the inner loop
# leaves it out.  42.9s of the fast band's 193.8s was this file alone.  The
# per-param `slow` marks below still apply on top.
pytestmark = pytest.mark.medium

# A generator loses reads by folding, so compare a table that folds
# completely against parity, which has no constant subtree above one row.
_TABLES = ["00000000", "01101001"]


def _input_reading_generators() -> list[object]:
    """Every boolean generator whose language actually reads input."""
    found = []
    for name in sorted(boolean.__all__):
        fn = getattr(boolean, name, None)
        lang = BY_BOOLEAN.get(name)
        if not callable(fn) or lang is None or lang.name not in INTERPRETERS:
            continue
        # A parameterized program embeds its inputs and reads none.
        if esolangs.describe(lang.name)["parameterized"]:
            continue
        try:
            run = importlib.import_module(INTERPRETERS[lang.name]).run
        except Exception:  # pragma: no cover - interpreter lives outside the pkg
            continue
        found.append((name, (fn, lang, run)))
    return found


def _reads(entry: tuple, table: str) -> int:
    """Run the generated program and report how many inputs it consumed."""
    fn, lang, _run = entry
    try:
        emitted = fn(table)
        program = emitted if isinstance(emitted, Raster) else str(emitted)
    except ValueError:
        # A generator that does not cover this table emits no program, and a
        # program that does not exist reads nothing.  Reporting 0 routes the
        # caller into its "does not read input" skip rather than failing on a
        # coverage gap, which is not what this test measures.
        return 0
    io = ScriptedIO(esolangs.encode_inputs(lang.name, [0] * 8))
    source = (
        program.splitlines() if lang.split and isinstance(program, str) else program
    )
    module = importlib.import_module(INTERPRETERS[lang.name])
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
    return io.reads


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    """A generator reads its ``n`` inputs whatever the truth table says."""
    counts = {table: _reads(entry, table) for table in _TABLES}
    baseline = counts["01101001"]
    assert baseline > 0, f"{name} read no input from parity"
    assert set(counts.values()) == {baseline}, (
        f"{name} reads a different number of inputs depending on the table: "
        f"{counts} -- a constant table must still consume all {baseline}"
    )


def _exported_generators() -> dict[str, str]:
    """Every boolean generator the package exports, mapped to its language."""
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
    """``BOOLEAN`` and the package's exports name the same languages."""
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
def _reordering_generators() -> list[tuple[str, object, object]]:
    from esolangs.tools.bitdeque import _bitdeque_ordered
    from esolangs.tools.painfuck import _painfuck_ordered

    entries: list[tuple[str, object, object]] = [
        ("painfuck", boolean.painfuck, _painfuck_ordered),
        ("bitdeque", boolean.bitdeque, _bitdeque_ordered),
    ]
    return entries


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_never_grows_a_program(
    name: str, fn: object, ordered: object
) -> None:
    """Choosing the input order can only shrink the emitted program."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            baseline = ordered(table, tuple(range(n)))
            # A searching generator returns "" for an order it cannot place;
            # there is no baseline to be no worse than, and any order that
            # *did* place is an improvement on not building.
            if not baseline:
                continue
            assert source_units(fn(table)) <= len(baseline), f"{name} grew on {table}"


@pytest.mark.parametrize(("name", "fn", "ordered"), _reordering_generators())
def test_reordering_shrinks_the_tables_it_should(
    name: str, fn: object, ordered: object
) -> None:
    """A table only one input order folds well is emitted from that order."""
    table = "10101010"
    assert source_units(fn(table)) < len(ordered(table, (0, 1, 2))), (
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
    from esolangs.tools.brainfuck import _bf_ordered

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
    """A greedily-ordered program still computes its table."""
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
        stdin = "".join(f"{bit}" for bit in bits)
        got = run_program(run, program, stdin)
        assert got == table[combo], f"inputs {bits}"


def test_the_greedy_order_is_the_documented_one() -> None:
    """What the heuristic picks, per table, not merely that it is valid."""
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
    """``perm`` reaches the emission in exactly one place, and it shows."""
    from itertools import permutations

    from esolangs.tools.brainfuck import _bf_ordered

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
# ``b_tapemark`` copies the whole table onto the blank grid, one mark per
# row, and each input walks the mark pointer by its weight -- so every table
# of one arity renders to the same length and a 0% fold is its construction
# working.  ``slow_acv_mammalian`` is a branch-free
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
# ``circlefuck`` reduces for the same reason from the other shape: its
# lookup tabulates the essential inputs alone, so a one-dependency table is
# a two-entry table and not a collapsed tree.
_REDUCING = {
    "circlefuck",
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
# ``qoibl`` encodes a lookup: the whole table is one
# binary literal and the reads build the power of two that divides it down,
# so the only thing a one-dependency table spares is the literal's leading
# zeros.
#
# ``befunge``, ``clockwise``, ``dimensional`` and ``modulous``
# are branch-free lookups: Befunge reads a grid cell with ``g`` (six packed
# bits per cell above ten inputs), Clockwise stops a countdown on the entry's
# own column, Modulous
# pops a ``PSH STR`` table down to the indexed character, so a 0% fold is
# the construction working.
# Dimensional paints one cell an entry along dimension 1 and stops at the last
# one, so a constant-zero tail reads as a 6.9% fold with nothing collapsing.
_UNSHAPED = {
    "a_painter_ant",
    "befunge",
    "fish",
    "bio",
    "alight",
    "clockwise",
    "dimensional",
    "egl",  # one painted grid cell per entry, walked to by weighted guards
    "forbin",  # one painted call argument per entry, halved down to the first
    # One deque push per entry; equal neighbours share a set node, which is
    # 16 characters (4.2%) at n == 3 against the byte I/O's fixed overhead.
    "flowchart",
    "malbolge",
    "minsky_swap",
    "cyclic_tag",
    "slashes",
    "subleq",
    "b_tapemark",
    "bitwise_cyclic_tag",  # no branch, so every table of an arity is one length
    "minifuck",
    "modulous",
    "one_two_three",
    "packlang",  # one painted array cell per differing row, read by index
    "qoibl",
    "slow_acv_mammalian",
    # The table is the state and the bit read rewrites every pair down to
    # one, so nothing collapses and a 0% fold is the construction working.
    "thue",
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
    """A tree generator folds a one-dependency table; a minterm sum cannot."""
    fn = getattr(boolean, name)
    best = min(source_units(fn(table)) for table in _ONE_DEPENDENCY)
    parity = source_units(fn(_PARITY))
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
            assert source_units(fn(table)) < parity, table
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
    """A dense table whose every arity *extends* the one below it."""
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


@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_builds_up_to_five_inputs(name: str) -> None:
    """Every boolean generator builds n=1..5 on both shapes, refusing none.

    The round trips execute n=2..3; the CI deep band builds to n=8 but lets a
    capped row refuse, so this is the local gate on n=1, 4 and 5.
    """
    fn = getattr(boolean, name)
    for n in range(1, 6):
        for shape, make in _SHAPES:
            program = fn(make(n))
            assert program, f"{name} built an empty program at n={n} ({shape})"


def test_cm_constants_builds_only_the_bootstrap_for_small_values() -> None:
    """Nothing above k2 is needed, so the plan sieve is never entered."""
    from esolangs.tools.helpers import _cm_constants

    lines = _cm_constants([1, 2])
    assert len(lines) == 4
    assert all(line.endswith("NOT PRINT.") for line in lines)
    assert _cm_constants([]) == lines


# The build sweep above proves every generator *returns* a program up to five
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
# There is deliberately no exclusion table here.
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
    """1 exactly where one input is set."""
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
    """Build a table using all six inputs, execute it, and check every row."""
    table = make(_ONE_MINTERM_ARITY)
    assert evaluate_generated(name, table, timeout=30) == table


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
def test_the_exec_tables_really_need_every_input(make: Callable[[int], str]) -> None:
    """The guards above are worthless if their tables fold."""
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
    "Polynomial": (1_589_968, 5_016_851, 3.2),
    "Factor": (12_592, 24_463, 2.1),
}


# The roadmap's original scaling queue.  A row leaves ``_OPEN_SCALING`` only
# after an O(T) construction or a language-wide lower bound; it enters when
# the construction is read super-linear, whatever the twelve doublings
# measure.  Streetcode left: its per-level hall was the
# ``Theta(T log T)`` source, and the tree it hung off has since gone too --
# the table is one street cell per entry and the inputs address it.
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
    "fractran",
    "inject",
    "jaune",
    "laserfuck",
    "malbolge",
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
    "polynomial",
}


def test_remaining_scaling_audit_is_exhaustive() -> None:
    """The scaling classes are disjoint and name real generators."""
    classes = (_LINEAR_SCALING, _LANGUAGE_SUPERLINEAR_SCALING, _OPEN_SCALING)
    classified = set().union(*classes)
    assert sum(map(len, classes)) == len(classified)
    assert classified <= set(BY_BOOLEAN)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.slow) if name == "streetcode" else name
        for name in sorted(_LINEAR_SCALING)
    ],
)
def test_converted_generators_scale_linearly(name: str) -> None:
    """Three same-parity rungs grow by four, whatever the prologue."""
    fn = getattr(boolean, name)
    if name == "circuit_diagram":
        # The H-layout is not asymptotic below n=8, so it has no room for a
        # third rung; the deep contract carries it on a backstop for the
        # same reason, and its area recurrence is checked with the
        # construction invariants.
        sizes = [len(fn(_parity(n))) for n in (8, 9)]
        assert sizes[1] <= 2 * sizes[0]
        return
    arities = (8, 10, 12)
    sizes = [len(fn(_parity(n))) for n in arities]
    if name == "minifuck":
        assert all(size <= 70 * 2**n for size, n in zip(sizes, arities, strict=True))
        return
    if name == "malbolge":
        # Every Malbolge source loads into 59,049 cells, so every program --
        # this generator's or any other -- is bounded by a constant.
        assert all(size <= 59_049 for size in sizes)
        return
    # The bound is ``linearity.MAX_DIFF_RATIO``.  That module imports the
    # table shapes from this one, so the constant cannot travel the other
    # way without a cycle; it is restated here rather than shared.
    assert sizes[1] > sizes[0]
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(_DOCUMENTED_SIZES))
def test_the_expensive_generators_grow_as_documented(name: str) -> None:
    """``docs/limitations.md`` tells a reader whether n=11 is affordable."""
    at_eight, at_nine, ratio = _DOCUMENTED_SIZES[name]
    assert len(esolangs.generate(name, _dense(8))) == at_eight
    assert len(esolangs.generate(name, _dense(9))) == at_nine
    assert at_nine / at_eight == pytest.approx(ratio, abs=0.35)


@pytest.mark.slow
def test_nothing_else_is_anywhere_near_that_big() -> None:
    """The document's "every other generator is under 600KB at n=9"."""
    biggest = max(
        (len(esolangs.generate(name, _dense(9))), name)
        for name in esolangs.list_languages()
        if name not in _DOCUMENTED_SIZES
        and LANGUAGES[name].boolean is not None
        and esolangs.describe(name)["source_kind"] == "text"
    )
    assert biggest[0] < 600_000, biggest
    # thisthat leads at 114637 characters; SLOW ACV MAMMALIAN led at 115707
    # until its modulo-255 I/O default (101931), and Boolfuck led at 194026
    # after its admission, until its native bit-cell tree replaced the lowering.
    assert biggest[1] == "thisthat", biggest
