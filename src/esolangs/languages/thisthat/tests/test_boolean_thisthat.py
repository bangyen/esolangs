"""Executed tests for the thisthat boolean generator."""

import random
from itertools import pairwise
from unittest.mock import patch

import pytest

import esolangs
from esolangs.generation.wrap import balance_score
from esolangs.languages.thisthat.generator import _Builder, _tree, thisthat
from esolangs.languages.thisthat.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_saved_rows,
    assert_shared_program,
    constant_programs,
    evaluate_generated,
    run_lines,
    three_input_corpus_size,
    verify_generated,
)
from tests.support.witness_tables import parity, witnesses


def _run(table: str, row: int) -> tuple[str, int]:
    return run_lines(run, thisthat(table), f"{row:0{len(table).bit_length() - 1}b}")


@pytest.mark.medium
def test_source_growth_is_linear_in_the_table() -> None:
    """Parity exercises both inline trees and shared residual DAGs."""
    _check_constants()
    sizes = [len(thisthat(parity(n))) for n in range(1, 13)]
    assert all(right <= 3 * left for left, right in pairwise(sizes[3:]))
    assert max(size / (1 << n) for n, size in enumerate(sizes, 1)) < 300

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(0)


def _pops(program: str) -> int:
    return program.count("◧")


def test_constants_test_nothing() -> None:
    """The positive control: a constant reads its inputs and prints."""
    for table in ("0" * 8, "1" * 8, "0" * 64):
        program = thisthat(table)
        assert _pops(program) == 0
        n = len(table).bit_length() - 1
        for row in range(0, 1 << n, 1 if n <= 3 else 9):
            bits = f"{row:0{n}b}"
            io = ScriptedIO("".join(f"{bit}" for bit in bits))
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (table[0], n)
    assert len(thisthat("0" * 8)) == 11  # 49 before the direct chain


def test_every_kept_level_is_tested_at_every_node(monkeypatch) -> None:
    """Only the loader's drop skips a test; agreeing halves are tested too."""

    def tests(table: str) -> int:
        program = _tree(table)
        return _pops(program)

    assert tests("00001111") == 1  # the first input alone
    assert tests("01010101") == 1  # the last input alone
    assert tests("00010011") == 4  # constant spans fold to leaves
    # The second input is tested under both values of the first.
    assert tests("00010101") == 6
    assert "⬒" not in _tree("00010101")
    _check_literal_leaf_outputs()
    for table in ("00110011", "00010101", "01011010"):
        for row, expected in enumerate(table):
            assert _run(table, row) == (expected, 3)

    from esolangs.generation.helpers import essential_inputs, read_at
    from esolangs.languages.thisthat import generator

    assert generator.essential_inputs is essential_inputs
    assert generator.read_at is read_at
    for query, damaged_query, expected in (
        ("essential_inputs", lambda _table, _n: [], "00000000"),
        (
            "read_at",
            lambda table, used, n: read_at(table, used, n).translate(
                str.maketrans("01", "10")
            ),
            "11101110",
        ),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(generator, query, damaged_query)
            source = _tree("00010001")
        for row, answer in enumerate(expected):
            io = ScriptedIO(f"{row:03b}\nQ")
            run(source.splitlines(), io)
            assert (io.getvalue(), io.reads, io.input_token()) == (answer, 3, "Q")


def _check_literal_leaf_outputs() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("thisthat")["execution"].formula
    for table in ("01", "10", "01010101", "10101010", "11110000"):
        n = len(table).bit_length() - 1
        source = thisthat(table)
        assert "◧" in source
        for row, expected in enumerate(table):
            stream = ScriptedIO(format(row, f"0{n}b") + "\nQ")
            machine = _Machine(source.splitlines(), stream)
            cycles = 0
            while not machine.halted:
                machine.step()
                cycles += 1
                assert len(machine.pointers) <= 1
                assert all(
                    p.channel != "data" or p.value in (0, 1) for p in machine.pointers
                )
            assert stream.getvalue() == expected
            assert stream.reads == n
            assert stream.input_char() == 10
            assert stream.input_char() == ord("Q")
            assert cycles <= execution(n, source)


@pytest.mark.medium
def test_pruning_never_grows_a_table() -> None:
    """No table through three inputs is larger than its unpruned tree."""
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            size = len(thisthat(table))
            assert size <= len(_tree(table, prune=False))
    tables = [f"{value:08b}" for value in range(256)]
    assert sum(len(thisthat(table)) for table in tables) == 47_482
    assert sum(len(_tree(table, prune=False)) for table in tables) == 188_416

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(1)


@pytest.mark.medium
def test_tables_through_six_inputs_execute() -> None:
    """Samples at four to six inputs execute."""
    rng = random.Random(6)
    for n in (4, 5, 6):
        for _ in range(12):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            assert verify_generated("thisthat", table), table

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(2)


def test_layout_collisions_abort() -> None:
    builder = _Builder()
    builder.node((0, 0), "▣")
    with pytest.raises(ValueError, match="layout collision"):
        builder.node((0, 0), "◇")
    builder.connect([(1, 0), (2, 0)], "single")
    with pytest.raises(ValueError, match="wire collision"):
        builder.connect([(1, 0), (2, 0)], "double")


@pytest.mark.parametrize("width", [1, 10, 20, 80])
def test_rotated_layout_keeps_ports_and_bistack_axes(width: int) -> None:
    """Rotation changes physical directions while input deque order stays fixed."""
    for n in (1, 3, 5):
        table = parity(n)
        plain = thisthat(table)
        program = esolangs.generate("thisthat", table, width=width).source
        floor = min(max(map(len, plain.splitlines())), len(plain.splitlines()))
        assert max(map(len, program.splitlines())) <= max(width, floor)
        for row, expected in enumerate(table):
            bits = f"{row:0{n}b}"
            io = ScriptedIO("".join(f"{bit}" for bit in bits))
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (expected, n)


def test_rotated_rendered_area_remains_linear() -> None:
    sizes = [len(thisthat(parity(n), 1)) for n in (5, 7, 9)]
    assert sizes[-1] / (1 << 9) < 300
    assert sizes[2] / sizes[1] < 5


@pytest.mark.medium
def test_narrow_strip_executes_every_small_table(monkeypatch) -> None:
    """Each narrow branch consumes the same input deque and prints once."""
    for n in range(1, 4):
        for table in witnesses(n):
            source = esolangs.generate("thisthat", table, width=1).source
            assert max(map(len, source.splitlines())) <= 9
            for row, expected in enumerate(table):
                io = ScriptedIO("".join(f"{bit}" for bit in f"{row:0{n}b}"))
                run(source.splitlines(), io)
                assert (io.getvalue(), io.reads) == (expected, n)
    assert max(map(len, thisthat("0110", 1).splitlines())) == 1
    assert len(thisthat("0110", 1)) == 17
    assert sum(len(thisthat(format(v, "04b"), 1)) for v in range(16)) == 764

    from esolangs.generation.helpers import subtree_ids
    from esolangs.languages.thisthat import generator

    assert generator.subtree_ids is subtree_ids
    monkeypatch.setattr(
        generator,
        "subtree_ids",
        lambda table: [[0] * len(layer) for layer in subtree_ids(table)],
    )
    damaged = generator._strip_tree("0001")
    for row in range(4):
        io = ScriptedIO(f"{row:02b}\nQ")
        run(damaged.splitlines(), io)
        assert (io.getvalue(), io.reads, io.input_token()) == ("0", 2, "Q")

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(3)


@pytest.mark.parametrize("width", [1, 3, 4, 5, 7, 9, 10, 19, 20, 40])
def test_strip_preserves_fitting_layouts_and_public_answers(width: int) -> None:
    from esolangs.languages.thisthat.generator import _rotate_tree

    for table in ("00", "11", "01", "10", "0110", "0001", "10010110"):
        plain = thisthat(table)
        old = plain
        if max(map(len, plain.splitlines())) > width and len(plain.splitlines()) < max(
            map(len, plain.splitlines())
        ):
            old = _rotate_tree(plain)
        source = esolangs.generate("thisthat", table, width=width).source
        if max(map(len, old.splitlines())) <= width:
            assert source == old
        assert evaluate_generated("thisthat", table, width=width) == table


@pytest.mark.parametrize("n", [4, 6, 8])
def test_larger_narrow_layout_retains_linear_area_construction(n: int) -> None:
    from esolangs.languages.thisthat.generator import _rotate_tree

    rng = random.Random(946 + n)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    raw = thisthat(table)
    expected = (
        _rotate_tree(raw)
        if len(raw.splitlines()) < max(map(len, raw.splitlines()))
        else raw
    )
    source = esolangs.generate("thisthat", table, width=1).source
    assert source == expected
    for row in {0, (1 << n) - 1, *(rng.randrange(1 << n) for _ in range(4))}:
        io = ScriptedIO("".join(f"{bit}" for bit in f"{row:0{n}b}"))
        run(source.splitlines(), io)
        assert (io.getvalue(), io.reads) == (table[row], n)


def test_narrow_strip_counts_kept_inputs() -> None:
    from esolangs.languages.thisthat import generator as boolean

    language = esolangs.Language("thisthat")
    witnesses = construction_boundaries(language.name)[
        "narrow_strip_essential_arity_cutoff"
    ]
    for witness in witnesses:
        n, table = witness.arity, witness.table()
        with patch.object(boolean, "_strip_tree", wraps=boolean._strip_tree) as strip:
            artifact = language.generate(table, width=1)
        assert strip.call_count == int(n == 3)
        assert_saved_rows(language, artifact, table, range(len(table)))

    for witness in construction_boundaries(language.name)["tiny_stream_arity_cutoff"]:
        table = witness.table()
        with patch.object(
            boolean, "_stream_tree", wraps=boolean._stream_tree
        ) as stream:
            artifact = language.generate(table, width=1)
        assert stream.call_count == int(witness.arity == 2)
        assert_saved_rows(language, artifact, table, range(len(table)))

    table = "01101001" * 2  # four inputs, the first ignored
    source = esolangs.generate("thisthat", table, width=1).source
    assert max(map(len, source.splitlines())) <= 9
    assert verify_generated("thisthat", table, width=1)


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("thisthat", "0110", width=1).source
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.medium
def test_shared_residual_buses_execute_within_ledger(monkeypatch) -> None:
    from esolangs.languages.thisthat.generator import shared_tree

    a, b = "0001011101101001" * 4, "0110100100010111" * 4
    table = a + b + b + a
    plain = _tree(table)
    program = thisthat(table)

    def area(source):
        return len(source.splitlines()) * max(map(len, source.splitlines()))

    assert (area(plain), area(program)) == (11413, 2343)
    shared = shared_tree(table)
    assert shared is not None
    assert shared[1] == 335
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:08b}")
        run(shared[0].splitlines(), io)
        assert (io.getvalue(), io.reads) == (expected, 8)
    assert_shared_program(
        "thisthat",
        table,
        plain,
        483,
        lambda _: (
            4 * 8
            + 89
            + 2 * (8).bit_length()
            + sum(max(1, c.bit_length()) for c in range(8))
        ),
        size=area,
    )

    from esolangs.languages.thisthat.generator import _coalesce, _narrow_tree

    narrow_plain = _narrow_tree(table, _coalesce(plain), 1)
    narrow = thisthat(table, 1)
    assert narrow == narrow_plain
    for row in (0, 1, 63, 64, 127, 128, 191, 192, 255):
        io = ScriptedIO(f"{row:08b}")
        run(narrow.splitlines(), io)
        assert (io.getvalue(), io.reads) == (table[row], 8)

    from esolangs.generation.decision import decision_layers
    from esolangs.languages.thisthat import generator

    rotated = generator._rotate_tree(plain)
    for source in (plain, rotated):
        for row in (0, 85, 255):
            io = ScriptedIO(f"{row:08b}")
            run(source.splitlines(), io)
            assert io.getvalue() == table[row]
    with monkeypatch.context() as packed:
        packed.setattr(generator, "_coalesce", lambda source: source)
        packed.setattr(generator, "_admit_shared", lambda *_args: True)
        layouts = iter((plain, rotated))
        calls = []

        def narrow(_table, source, _width):
            calls.append(source)
            return next(layouts)

        packed.setattr(generator, "_narrow_tree", narrow)
        # A packed-area tie retains the plain candidate; both drawings execute.
        packed.setattr(generator, "grid_area", lambda _source: 1)
        width = max(map(len, (plain + "\n" + rotated).splitlines()))
        assert generator._diagram(table, width) == plain
        assert len(calls) == 2

    assert generator.decision_layers is decision_layers
    monkeypatch.setattr(
        generator,
        "decision_layers",
        lambda table: decision_layers(table.translate(str.maketrans("01", "10"))),
    )
    damaged = shared_tree(table)
    assert damaged is not None
    for row in (0, 1, 85, 255):
        io = ScriptedIO(f"{row:08b}\nQ")
        run(damaged[0].splitlines(), io)
        assert (io.getvalue(), io.reads, io.input_token()) == (
            str(1 - int(table[row])),
            8,
            "Q",
        )

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(4)


@pytest.mark.medium
def test_shared_dag_rasters_and_rotations_execute_small_tables() -> None:
    from esolangs.languages.thisthat.generator import _rotate_tree, shared_tree

    exercised = 0
    for table in witnesses(3):
        built = shared_tree(table)
        if built is None:
            continue
        exercised += 1
        program, _ = built
        for source in (program, _rotate_tree(program)):
            for row, expected in enumerate(table):
                io = ScriptedIO(f"{row:03b}")
                run(source.splitlines(), io)
                assert (io.getvalue(), io.reads) == (expected, 3)
    assert exercised > 0

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(5)


@pytest.mark.medium
def test_shared_area_envelope_admits_more_than_old_node_cap() -> None:
    from esolangs.generation.helpers import subtree_ids
    from esolangs.languages.thisthat.generator import shared_tree

    rng = random.Random(15)
    table = "".join(rng.choice("01") for _ in range(64))
    ids = subtree_ids(table)
    nodes = sum(len(set(level) - {0, 1}) for level in ids) + 2
    assert nodes == 25  # The preceding six-input node cap was 16.
    built = shared_tree(table)
    assert built is not None
    source, _ = built
    assert len(source.splitlines()) * max(map(len, source.splitlines())) == 12139
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:06b}")
        run(source.splitlines(), io)
        assert (io.getvalue(), io.reads) == (expected, 6)

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(6)


@pytest.mark.medium
def test_shared_unequal_bus_banks_execute_all_rows() -> None:
    rng = random.Random(15)
    parts = ["".join(rng.choice("01") for _ in range(16)) * 4 for _ in range(3)]
    table = "".join(parts[i] for i in (0, 1, 2, 0, 2, 1, 0, 2))
    from esolangs.languages.thisthat.generator import _coalesce, shared_tree

    shared = shared_tree(table)
    assert shared is not None
    source = _coalesce(shared[0])
    area = len(source.splitlines()) * max(map(len, source.splitlines()))
    assert area == 13065 < 14283  # Preceding equal-bank emitted area.
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:09b}")
        run(source.splitlines(), io)
        assert (io.getvalue(), io.reads) == (expected, 9)

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(7)


@pytest.mark.medium
def test_balance_matches_the_old_one_column_narrowing_search() -> None:
    """The named widths score as well as walking ``width - 1`` three times."""
    from esolangs.generation.helpers import grid_width
    from esolangs.languages.thisthat.generator import _balance, _narrow_tree

    def searched(table: str, default: str) -> str:
        candidates = [default, _tree(table)]
        for base, shared in ((default, True), (candidates[1], False)):
            previous = base
            for _ in range(3):
                width = max(1, grid_width(previous) - 1)
                previous = (
                    thisthat(table, width)
                    if shared
                    else _narrow_tree(table, base, width)
                )
                candidates.append(previous)
        candidates.append(thisthat(table, 1))
        return min(candidates, key=balance_score)

    rng = random.Random(7)
    tables = [format(v, f"0{1 << n}b") for n in (1, 2, 3) for v in range(1 << (1 << n))]
    tables += [format(rng.getrandbits(1 << n), f"0{1 << n}b") for n in (4, 5, 6, 7)]
    for table in tables:
        default = thisthat(table)
        assert balance_score(_balance(table, default)) <= balance_score(
            searched(table, default)
        ), table
    # Positive control: the search does beat default and inline somewhere.
    assert balance_score(searched("0110", thisthat("0110"))) < balance_score(
        _tree("0110")
    )

    from .workspace_checks import check_accounting_thisthat

    check_accounting_thisthat(8)


def test_a_dag_over_the_cycle_bound_is_refused() -> None:
    """An over-bound DAG stays inadmissible after literal leaves shrink the tree."""
    from esolangs.languages.thisthat.generator import _admit_shared, shared_tree

    table = "0000111011101111"
    source = esolangs.generate("thisthat", table).source
    assert len(source) == 395
    shared = shared_tree(table)
    assert shared is not None
    assert shared[1] > 32 * 2**2 - 29
    assert not _admit_shared(_tree(table), shared[0], shared[1], 4)
    assert evaluate_generated("thisthat", table) == table


@pytest.mark.parametrize(
    ("n", "side"), [(6, 69), pytest.param(8, 138, marks=pytest.mark.medium)]
)
def test_balance_races_the_flat_tree(n: int, side: int) -> None:
    """Contracted flat trees retain their balanced size pins."""
    table = format(random.Random(n).getrandbits(1 << n), f"0{1 << n}b")
    balanced = esolangs.generate("thisthat", table, balance=True).source
    assert balance_score(balanced)[0] == side
    assert _evaluate("thisthat", balanced, 60, inputs=n, max_rows=None) == table


def test_coalescing_preserves_the_single_pointer_schedule() -> None:
    """Ordinary diagrams cannot race when transit legs contract."""
    from esolangs.generation.helpers import grid_area
    from esolangs.languages.thisthat.generator import _coalesce

    for table in witnesses(3):
        raw = _tree(table)
        program = _coalesce(raw)
        assert grid_area(program) <= grid_area(raw)
        for row, expected in enumerate(table):
            io = ScriptedIO(f"{row:03b}")
            machine = _Machine(program.splitlines(), io)
            for _ in range(1000):
                if machine.halted:
                    break
                assert len(machine.pointers) == 1
                assert machine.cursor == 0
                machine.step()
            assert machine.halted
            assert (io.getvalue(), io.reads) == (expected, 3)
    native = "▣\n│\n◇\n║\n▦\n║\n◇\n│\n▣"
    assert _coalesce(native) == native


def _check_constants() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("thisthat")["workspace"].formula
    for n, bit, options, program in constant_programs("thisthat", range(1, 13)):
        if not options or "width" in options:
            assert (
                len(program.splitlines()) * max(map(len, program.splitlines()))
                == 2 * n + 5
            )
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            io = ReadFirstIO(f"{row:0{n}b}" + "1", expected=n)
            machine = _Machine(program.splitlines(), io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 2 * n + 5, written=written)
            assert steps == 2 * n + 5
            assert written.bits <= workspace(n, program)
            assert io.getvalue() == bit
            assert io.reads == n
            assert io.input_char() == ord("1")
    assert three_input_corpus_size("thisthat") == 47482
