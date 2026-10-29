"""Contract tests every boolean generator must satisfy."""

import contextlib
import importlib
from collections.abc import Callable

import pytest

import esolangs
import esolangs.languages.generators as boolean
from esolangs.generation.helpers import essential_inputs
from esolangs.raster import Raster
from esolangs.registry import BY_BOOLEAN, INTERPRETERS, LANGUAGES
from esolangs.registry._language import Shape
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _BranchingStepMachine, run_until_halt, run_until_halt_or_cycle
from scripts.docs.proof_status import load as _load_proof_status
from tests.support.generator_support import (
    assert_proved_resource_cap,
    evaluate_generated,
)
from tests.support.source_support import source_units
from tests.support.witness_tables import dense, parity, row_bits

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
        program = (
            emitted
            if isinstance(emitted, (Raster, esolangs.CompressedText))
            else str(emitted)
        )
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
        machine = build(source, io)
        drive = (
            run_until_halt
            if isinstance(machine, _BranchingStepMachine)
            else run_until_halt_or_cycle
        )
        drive(machine, limit=100_000)
    return io.reads


@pytest.mark.parametrize(
    ("name", "entry"),
    _input_reading_generators(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_table_reads_the_same_number_of_inputs(name: str, entry: tuple) -> None:
    """A generator reads its ``n`` inputs whatever the truth table says."""
    controls = LANGUAGES[esolangs.resolve(name)].benchmark_tables
    if controls:
        assert_proved_resource_cap(name)
        for table in controls:
            assert _reads(entry, table) == len(table).bit_length() - 1
        return
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
        f"{sorted(missing)} -- check their LANGUAGE declarations"
    )
    stale = boolean.BOOLEAN - set(exported.values())
    assert not stale, (
        f"BOOLEAN names these languages but the package exports no generator "
        f"resolving to them: {sorted(stale)} -- remove them from BOOLEAN, or "
        f"export the generator from languages/generators.py"
    )


def test_reorder_permutation_preserves_the_function() -> None:
    """Permuting the table renames the inputs without changing the function."""
    from esolangs.generation.helpers import permute_truth_table

    table = "01101001"
    n = 3
    for perm in [(0, 1, 2), (2, 0, 1), (2, 1, 0)]:
        permuted = permute_truth_table(table, perm)
        for row in range(2**n):
            bits = row_bits(row, n)
            original = sum(bits[level] << (n - 1 - i) for level, i in enumerate(perm))
            assert permuted[row] == table[original]


def test_the_tree_program_spends_its_permutation_on_the_tested_cell() -> None:
    """``perm`` reaches the emission in exactly one place, and it shows."""
    from itertools import permutations

    from esolangs.languages.brainfuck.generator import _bf_ordered

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


# The shape each generator's construction takes (its LANGUAGE's ``shape=``)
# decides which optimizations apply: folding, input reordering and
# dependency reduction are tree techniques.  This test keeps the declared
# shape true; a ``LOOKUP`` renders every table of an arity alike, so there
# is nothing to measure.
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
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None and lang.shape is not Shape.LOOKUP
    ),
)
def test_generator_shape_is_what_the_catalogue_says(name: str) -> None:
    """A tree folds a one-dependency table; a reducing sum drops its inputs."""
    fn = LANGUAGES[name].boolean
    assert fn is not None
    try:
        best = min(source_units(fn(table)) for table in _ONE_DEPENDENCY)
        parity = source_units(fn(_PARITY))
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(name)
        pytest.skip("fold probe exceeds a proved language resource cap")
    folds = 1 - best / parity
    if LANGUAGES[name].shape is Shape.REDUCING:
        # The gain is real but is not a fold, so assert it from the other
        # direction: the saving must come from dropped inputs, which means a
        # table that depends on *every* input cannot be shortened at all.
        assert folds >= 0.05, (
            f"{name} declares Shape.REDUCING but gains only {folds:.1%} on a "
            "one-dependency table -- its reduction has regressed"
        )
        for table in _ONE_DEPENDENCY:
            assert source_units(fn(table)) < parity, table
        return
    assert folds >= 0.05, (
        f"{name} is a tree (the default shape) but folds only {folds:.1%} on "
        "a table that ignores inputs: fold equal subtrees, or declare "
        "shape=Shape.REDUCING or Shape.LOOKUP on its LANGUAGE, with the reason "
        "(from esolangs.registry._language import Shape)"
    )


_SHAPES = (("dense", dense), ("parity", parity))


@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_builds_up_to_five_inputs(name: str) -> None:
    """Every generator builds n=1..5 unless a proved resource cap refuses it.

    The round trips execute n=2..3; the CI deep band builds to n=8 but lets a
    capped row refuse, so this is the local gate on n=1, 4 and 5.
    """
    fn = getattr(boolean, name)
    built = 0
    for n in range(1, 6):
        for shape, make in _SHAPES:
            try:
                program = fn(make(n))
            except esolangs.GeneratorCapError:
                assert_proved_resource_cap(name)
                continue
            built += 1
            assert program, f"{name} built an empty program at n={n} ({shape})"
    assert built, f"{name} never built a positive control"


# language-owners: ["Grapheme"]
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
    try:
        result = evaluate_generated(name, table, timeout=30)
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(name)
        pytest.skip("execution probe exceeds a proved language resource cap")
    assert result == table


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
#: Each language holds its own row as ``documented_sizes=``.
_DOCUMENTED_SIZES: dict[str, tuple[int, int, float]] = {
    name: lang.documented_sizes
    for name, lang in LANGUAGES.items()
    if lang.documented_sizes is not None
}


#: Every generator is held to linear source growth but the ones the ledger
#: bounds below by the language itself (its ``lower bound`` scaling rows).
_LANGUAGE_SUPERLINEAR_SCALING = {
    # The ledger's data, aggregated from the packages' own fragments: the
    # mutation bundle has no ``tests/proofs`` to parse it with.
    row.generator
    for row in _load_proof_status()[0]
    if row.scaling.startswith("lower bound:")
}
_LINEAR_SCALING = sorted(
    name
    for name, lang in LANGUAGES.items()
    if lang.boolean is not None and name not in _LANGUAGE_SUPERLINEAR_SCALING
)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.slow)
        if LANGUAGES[name].slow_scaling
        else name
        for name in _LINEAR_SCALING
    ],
)
def test_generators_scale_linearly(name: str) -> None:
    """Three same-parity rungs grow by four, whatever the prologue."""
    lang = LANGUAGES[name]
    fn = lang.boolean
    assert fn is not None
    arities = lang.scaling_rungs
    sizes = [source_units(fn(parity(n))) for n in arities]
    if lang.size_bound is not None:
        bound = lang.size_bound
        assert all(size <= bound(n) for size, n in zip(sizes, arities, strict=True))
        return
    if len(arities) == 2:
        # Two rungs: one step of n at most doubles the program.
        low, high = arities
        assert sizes[1] <= 2 ** (high - low) * sizes[0]
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
    sizes = (len(esolangs.generate(name, dense(n))) for n in (8, 9))
    assert tuple(sizes) == (at_eight, at_nine), (
        f"{name}'s dense n=8 and n=9 sizes moved; update its "
        "documented_sizes= in its LANGUAGE"
    )
    assert at_nine / at_eight == pytest.approx(ratio, abs=0.35)


@pytest.mark.slow
def test_nothing_else_is_anywhere_near_that_big() -> None:
    """The document's "every other generator is under 600KB at n=9"."""
    for lang in LANGUAGES.values():
        if lang.benchmark_tables:
            assert_proved_resource_cap(lang.name)
    biggest = max(
        (len(esolangs.generate(name, dense(9))), name)
        for name in esolangs.list_languages()
        if name not in _DOCUMENTED_SIZES
        and LANGUAGES[name].boolean is not None
        and not LANGUAGES[name].benchmark_tables
        and esolangs.describe(name)["source_kind"] == "text"
    )
    # language-owners: ["Boolfuck", "SLOW ACV MAMMALIAN", "thisthat"]
    # thisthat leads at 114637 characters; SLOW ACV MAMMALIAN led at 115707
    # until its modulo-255 I/O default (101931), and Boolfuck led at 194026
    # after its admission, until its native bit-cell tree replaced the
    # lowering.  The leader is not pinned: a new language may take the lead
    # without breaking the claim, which is only the ceiling.
    size, name = biggest
    assert size < 600_000, (
        f"{name} emits {size} characters for a dense n=9 table; shrink its "
        "generator, or document it and set documented_sizes= in its LANGUAGE "
        "with its n=8 and n=9 sizes"
    )
