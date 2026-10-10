"""Executed tests for the thisthat boolean generator."""

import random
from collections import deque
from itertools import pairwise, permutations, product
from math import comb

import pytest

import esolangs
from esolangs.interpreters.grid_based.thisthat import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.thisthat import _Builder, _deque_plan, _tree, thisthat
from tests.generator_support import evaluate_generated, run_lines, verify_generated
from tests.witness_tables import parity, witnesses


def _run(table: str, row: int) -> tuple[str, int]:
    return run_lines(run, thisthat(table), f"{row:0{len(table).bit_length() - 1}b}")


@pytest.mark.medium
def test_source_growth_is_linear_in_the_table() -> None:
    """Parity exercises both inline trees and shared residual DAGs."""
    sizes = [len(thisthat(parity(n))) for n in range(1, 13)]
    assert all(right <= 3 * left for left, right in pairwise(sizes[3:]))
    assert max(size / (1 << n) for n, size in enumerate(sizes, 1)) < 300


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
    assert len(thisthat("0" * 8)) == 49  # 1,169 before


def test_only_dependent_levels_are_tested() -> None:
    """A level whose halves agree is popped onto the column stack, not tested."""

    def tests(table: str) -> int:
        program = _tree(table)
        return sum(map(program.count, "◐◑◒"))

    assert tests("00001111") == 1  # the first input alone
    assert tests("01010101") == 1  # the last input alone
    assert tests("00010011") == 4  # the full tree has 7
    # The second input is tested under x0 = 0 and popped under x0 = 1.
    assert tests("00010101") == 4  # 7 unpruned
    assert "⬒" in _tree("00010101").split("\n", 1)[1]
    for table in ("00110011", "00010101", "01011010"):
        for row, expected in enumerate(table):
            assert _run(table, row) == (expected, 3)


@pytest.mark.medium
def test_pruning_never_grows_a_table() -> None:
    """No table through three inputs is larger than its unpruned tree."""
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            size = len(thisthat(table))
            assert size <= len(_tree(table, prune=False))
    tables = [f"{value:08b}" for value in range(256)]
    assert sum(len(thisthat(table)) for table in tables) == 158_308
    assert sum(len(_tree(table, prune=False)) for table in tables) == 199_936


def test_deque_plan_pops_exactly_the_orders_a_deque_can() -> None:
    """Every order a push-then-pop deque yields is planned, and nothing else."""
    for n in range(1, 7):
        reachable = set()
        for pushes in product((False, True), repeat=n):
            row: deque[int] = deque()
            for i, head in enumerate(pushes):
                (row.appendleft if head else row.append)(i)
            for pops in product((False, True), repeat=n):
                left = deque(row)
                reachable.add(
                    tuple(left.popleft() if head else left.pop() for head in pops)
                )
        assert len(reachable) == comb(2 * n - 2, n - 1)
        for order in permutations(range(n)):
            plan = _deque_plan(order)
            assert (plan is not None) == (order in reachable), order
            if plan is None:
                continue
            head_push, head_pop = plan
            row = deque()
            for i, head in enumerate(head_push):
                (row.appendleft if head else row.append)(i)
            popped = tuple(row.popleft() if head else row.pop() for head in head_pop)
            assert popped == order


@pytest.mark.medium
def test_tables_through_six_inputs_execute() -> None:
    """Samples at four to six inputs execute."""
    rng = random.Random(6)
    for n in (4, 5, 6):
        for _ in range(12):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            assert verify_generated("thisthat", table), table


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
        program = esolangs.generate("thisthat", table, width=width)
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
def test_narrow_strip_executes_every_small_table() -> None:
    """Each narrow branch consumes the same input deque and prints once."""
    for n in range(1, 4):
        for table in witnesses(n):
            source = esolangs.generate("thisthat", table, width=1)
            assert max(map(len, source.splitlines())) <= 9
            for row, expected in enumerate(table):
                io = ScriptedIO("".join(f"{bit}" for bit in f"{row:0{n}b}"))
                run(source.splitlines(), io)
                assert (io.getvalue(), io.reads) == (expected, n)
    assert max(map(len, thisthat("0110", 1).splitlines())) == 1
    assert len(thisthat("0110", 1)) == 17
    assert sum(len(thisthat(format(v, "04b"), 1)) for v in range(16)) == 1028


@pytest.mark.parametrize("width", [1, 3, 4, 5, 7, 9, 10, 19, 20, 40])
def test_strip_preserves_fitting_layouts_and_public_answers(width: int) -> None:
    from esolangs.tools.thisthat import _rotate_tree

    for table in ("00", "11", "01", "10", "0110", "0001", "10010110"):
        plain = thisthat(table)
        old = plain
        if max(map(len, plain.splitlines())) > width and len(plain.splitlines()) < max(
            map(len, plain.splitlines())
        ):
            old = _rotate_tree(plain)
        source = esolangs.generate("thisthat", table, width=width)
        if max(map(len, old.splitlines())) <= width:
            assert source == old
        assert evaluate_generated("thisthat", table, width=width) == table


@pytest.mark.parametrize("n", [4, 6, 8])
def test_larger_narrow_layout_retains_linear_area_construction(n: int) -> None:
    from esolangs.tools.thisthat import _rotate_tree

    rng = random.Random(946 + n)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    raw = thisthat(table)
    expected = (
        _rotate_tree(raw)
        if len(raw.splitlines()) < max(map(len, raw.splitlines()))
        else raw
    )
    source = esolangs.generate("thisthat", table, width=1)
    assert source == expected
    for row in {0, (1 << n) - 1, *(rng.randrange(1 << n) for _ in range(4))}:
        io = ScriptedIO("".join(f"{bit}" for bit in f"{row:0{n}b}"))
        run(source.splitlines(), io)
        assert (io.getvalue(), io.reads) == (table[row], n)


def test_narrow_strip_counts_kept_inputs() -> None:
    table = "01101001" * 2  # four inputs, the first ignored
    source = esolangs.generate("thisthat", table, width=1)
    assert max(map(len, source.splitlines())) <= 9
    assert verify_generated("thisthat", table, width=1)


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("thisthat", "0110", width=1)
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.medium
def test_shared_residual_buses_execute_within_ledger() -> None:
    from esolangs.tools.thisthat._shared import shared_tree
    from tests.generator_support import assert_shared_program

    a, b = "0001011101101001" * 4, "0110100100010111" * 4
    table = a + b + b + a
    plain = _tree(table)
    program = thisthat(table)

    def area(source):
        return len(source.splitlines()) * max(map(len, source.splitlines()))

    assert (area(plain), area(program)) == (12995, 5831)
    shared = shared_tree(table)
    assert shared is not None
    assert shared[1] == 335
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


@pytest.mark.medium
def test_shared_dag_rasters_and_rotations_execute_small_tables() -> None:
    from esolangs.tools.thisthat import _rotate_tree
    from esolangs.tools.thisthat._shared import shared_tree

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


@pytest.mark.medium
def test_shared_area_envelope_admits_more_than_old_node_cap() -> None:
    from esolangs.tools.helpers import subtree_ids
    from esolangs.tools.thisthat._shared import shared_tree

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


@pytest.mark.medium
def test_shared_unequal_bus_banks_execute_all_rows() -> None:
    rng = random.Random(15)
    parts = ["".join(rng.choice("01") for _ in range(16)) * 4 for _ in range(3)]
    table = "".join(parts[i] for i in (0, 1, 2, 0, 2, 1, 0, 2))
    source = thisthat(table)
    area = len(source.splitlines()) * max(map(len, source.splitlines()))
    assert area == 13455 < 14283  # Preceding equal-bank emitted area.
    for row, expected in enumerate(table):
        io = ScriptedIO(f"{row:09b}")
        run(source.splitlines(), io)
        assert (io.getvalue(), io.reads) == (expected, 9)
