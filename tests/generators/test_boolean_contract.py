"""Contract tests every boolean generator must satisfy."""

from collections.abc import Callable

import pytest

import esolangs
from esolangs.generation.helpers import essential_inputs
from esolangs.registry import BY_BOOLEAN, LANGUAGES
from esolangs.registry._backend import Shape
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from scripts.docs.proof_status import load as _load_proof_status
from scripts.source_units import source_units
from tests.support.generator_support import (
    assert_proved_resource_cap,
    evaluate_generated,
    generator_for,
)
from tests.support.witness_tables import _one_minterm, dense, parity, row_bits

# Every sweep here runs an interpreter over a generated program -- the whole
# file is the execution gate -- so the module is `medium` and the inner loop
# leaves it out.  42.9s of the fast band's 193.8s was this file alone.  The
# per-param `slow` marks below still apply on top.
pytestmark = pytest.mark.medium


def test_boolean_index_lists_all_declared_backends() -> None:
    declared = {name for name, lang in LANGUAGES.items() if lang.backend is not None}
    assert {lang.name for lang in BY_BOOLEAN.values()} == declared


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

    from esolangs.generation.helpers import permute_truth_table
    from esolangs.languages.brainfuck.generator import _bf_ordered
    from esolangs.languages.brainfuck.interpreter import _Machine

    lengths = {
        perm: len(_bf_ordered("00010111", perm)) for perm in permutations(range(3))
    }
    assert lengths == {
        (0, 1, 2): 270,
        (0, 2, 1): 286,
        (1, 0, 2): 280,
        (1, 2, 0): 290,
        (2, 0, 1): 286,
        (2, 1, 0): 286,
    }

    # One and two inputs, where the tape is short enough that an off-by-one
    # in the move would still land inside it.
    assert len(_bf_ordered("01", (0,))) == 108
    assert len(_bf_ordered("0110", (0, 1))) == 186
    assert len(_bf_ordered("0110", (1, 0))) == 198

    # Include an asymmetric table: majority and parity alone hide wrong maps.
    for table in ("01", "0110", "00010111", "00110110"):
        n = len(table).bit_length() - 1
        for perm in permutations(range(n)):
            source = _bf_ordered(permute_truth_table(table, perm), perm)
            for row, expected in enumerate(table):
                io = ScriptedIO(f"{row:0{n}b}Q")
                machine = _Machine(source, io)
                commands = 0
                while not machine.halted:
                    machine.step()
                    commands += 1
                    assert commands <= 2_000
                assert io.getvalue() == expected
                assert io.reads == n
                assert io.past_end == 0
                assert io.input_char() == ord("Q")


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
        if lang.backend is not None and lang.backend.shape is not Shape.LOOKUP
    ),
)
def test_generator_shape_is_what_the_catalogue_says(name: str) -> None:
    """A tree folds a one-dependency table; a reducing sum drops its inputs."""
    fn = generator_for(name)
    assert fn is not None
    try:
        best = min(source_units(fn(table)) for table in _ONE_DEPENDENCY)
        parity = source_units(fn(_PARITY))
    except esolangs.GeneratorCapError:
        assert_proved_resource_cap(name)
        pytest.skip("fold probe exceeds a proved language resource cap")
    folds = 1 - best / parity
    if LANGUAGES[name].backend.shape is Shape.REDUCING:
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
        "(from esolangs.registry._backend import Shape)"
    )


_SHAPES = (("dense", dense), ("parity", parity))


@pytest.mark.parametrize("name", sorted(BY_BOOLEAN))
def test_every_generator_builds_up_to_five_inputs(name: str) -> None:
    """Every generator builds n=1..5 unless a proved resource cap refuses it.

    The round trips execute n=2..3; the CI deep band builds to n=8 but lets a
    capped row refuse, so this is the local gate on n=1, 4 and 5.
    """
    fn = generator_for(BY_BOOLEAN[name].name)
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


def _one_hot(n: int) -> str:
    """1 exactly where one input is set."""
    return "".join(str(int((row).bit_count() == 1)) for row in range(2**n))


#: The table shapes every generator's *output* is executed against.
_EXEC_SHAPES = (("one_minterm", _one_minterm), ("one_hot", _one_hot))


@pytest.mark.parametrize(
    "make", [make for _, make in _EXEC_SHAPES], ids=[s for s, _ in _EXEC_SHAPES]
)
@pytest.mark.parametrize(
    "name",
    sorted(n for n in esolangs.list_languages() if LANGUAGES[n].backend is not None),
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


#: Every generator is held to linear source growth but the ones the ledger
#: bounds below by the language itself (its ``lower bound`` scaling rows).
_LANGUAGE_SUPERLINEAR_SCALING = {
    # The ledger's data, aggregated from the packages' own fragments: the
    # mutation bundle has no ``tests/proofs`` to parse it with.
    row.generator
    for row in _load_proof_status()[0]
    if row.scaling_evidence == "lower bound"
}
_LINEAR_SCALING = sorted(
    name
    for name, lang in LANGUAGES.items()
    if lang.backend is not None and name not in _LANGUAGE_SUPERLINEAR_SCALING
)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.slow)
        if load_certification(LANGUAGES[name]).slow_scaling
        else name
        for name in _LINEAR_SCALING
    ],
)
def test_generators_scale_linearly(name: str) -> None:
    """Three same-parity rungs grow by four, whatever the prologue."""
    lang = LANGUAGES[name]
    fn = generator_for(lang.name)
    assert fn is not None
    arities = load_certification(lang).scaling_rungs
    sizes = [source_units(fn(parity(n))) for n in arities]
    if load_certification(lang).size_bound is not None:
        bound = load_certification(lang).size_bound
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
def test_dense_source_stays_under_the_catalog_ceiling() -> None:
    """Check the catalog text ceiling on dense nine-input tables."""
    for lang in LANGUAGES.values():
        if load_certification(lang).benchmark_tables:
            assert_proved_resource_cap(lang.name)
    biggest = max(
        (len(esolangs.generate(name, dense(9)).source), name)
        for name in esolangs.list_languages()
        if LANGUAGES[name].backend is not None
        and not load_certification(LANGUAGES[name]).benchmark_tables
        and esolangs.describe(name).source_kind == "text"
    )
    # language-owners: ["Boolfuck", "SLOW ACV MAMMALIAN", "thisthat"]
    # thisthat leads at 114637 characters; SLOW ACV MAMMALIAN led at 115707
    # until its modulo-255 I/O default (101931), and Boolfuck led at 194026
    # after its admission, until its native bit-cell tree replaced the
    # lowering.  The leader is not pinned: a new language may take the lead
    # without breaking the claim, which is only the ceiling.
    size, name = biggest
    assert size < 600_000, f"{name} emits {size} characters for a dense n=9 table"
