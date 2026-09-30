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


def _run(table: str, row: int) -> tuple[str, int]:
    n = len(table).bit_length() - 1
    bits = f"{row:0{n}b}"
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    run(thisthat(table).splitlines(), io)
    return io.getvalue(), io.reads


@pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
def test_every_table_through_three_inputs(n: int) -> None:
    width = 1 << n
    for value in range(1 << width):
        table = f"{value:0{width}b}"
        for row, expected in enumerate(table):
            output, reads = _run(table, row)
            assert output == expected, (table, row)
            assert reads == n, (table, row)


def _parity(n: int) -> str:
    return "".join(str(row.bit_count() & 1) for row in range(1 << n))


@pytest.mark.medium
def test_source_growth_is_linear_in_the_table() -> None:
    """Parity keeps every node, so it is the full tree's growth.

    From four inputs, where the tree outgrows the loader row above it; to
    twelve, where linearity.py reads the same trend (thirteen took 4.6s of
    the medium band's 5s once four candidates were built).
    """
    sizes = [len(thisthat(_parity(n))) for n in range(1, 13)]
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
            io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (table[0], n)
    assert len(thisthat("0" * 8)) == 79  # 1,169 before


def test_only_dependent_levels_are_tested() -> None:
    """A level whose halves agree is popped onto the column stack, not tested."""

    def tests(table: str, *, reorder: bool = False) -> int:
        program = _tree(table, reorder=reorder)
        return sum(map(program.count, "◐◑◒"))

    assert tests("00001111") == 1  # the first input alone
    assert tests("01010101") == 1  # the last input alone
    assert tests("00010011") == 4  # the full tree has 7
    assert tests("00010011", reorder=True) == 3  # testing x1 first
    # The second input is tested under x0 = 0 and popped under x0 = 1.
    assert tests("00010101") == 4  # 7 unpruned
    assert "⬒" in _tree("00010101", reorder=False).split("\n", 1)[1]
    for table in ("00110011", "00010101", "01011010"):
        for row, expected in enumerate(table):
            assert _run(table, row) == (expected, 3)


@pytest.mark.medium
def test_pruning_never_grows_a_table() -> None:
    """No table through three inputs is larger than its unpruned tree.

    ``prune=False`` is the previous tree under the tighter loader: the 256
    three-input tables were 299,264 characters, are 199,936 unpruned,
    159,628 with ignored inputs projected and agreeing levels skipped,
    147,836 with the greedy test order where the row can pop it, and
    130,860 with the root's arms swapped where that is shorter.
    """
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            size = len(thisthat(table))
            assert size <= len(_tree(table, reorder=False))
            assert size <= len(_tree(table, prune=False))
    tables = [f"{value:08b}" for value in range(256)]
    assert sum(len(thisthat(table)) for table in tables) == 130_860
    assert sum("◐" in thisthat(table) for table in tables) == 100
    assert sum(len(_tree(table, reorder=False)) for table in tables) == 159_628
    assert sum(len(_tree(table, prune=False)) for table in tables) == 199_936


def test_deque_plan_pops_exactly_the_orders_a_deque_can() -> None:
    """Every order a push-then-pop deque yields is planned, and nothing else.

    Pushing inputs in order to either end and then popping either end
    yields ``C(2n - 2, n - 1)`` orders: all six at three inputs.
    """
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
def test_reordered_tables_through_six_inputs_execute() -> None:
    """Samples at four to six inputs, some in a reordered test order."""
    rng = random.Random(6)
    reordered = 0
    for n in (4, 5, 6):
        for _ in range(12):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            program = thisthat(table)
            reordered += program != _tree(table, reorder=False)
            assert esolangs.verify("thisthat", table), table
    assert reordered


def test_layout_collisions_abort() -> None:
    builder = _Builder()
    builder.node((0, 0), "▣")
    with pytest.raises(ValueError, match="layout collision"):
        builder.node((0, 0), "◇")
    builder.connect([(1, 0), (2, 0)], "single")
    with pytest.raises(ValueError, match="wire collision"):
        builder.connect([(1, 0), (2, 0)], "double")


@pytest.mark.parametrize("width", [1, 10, 20, 40, 80])
def test_rotated_layout_keeps_ports_and_bistack_axes(width: int) -> None:
    """Rotation changes physical directions while input deque order stays fixed."""
    for n in (1, 3, 5):
        table = _parity(n)
        plain = thisthat(table)
        program = esolangs.generate("thisthat", table, width)
        floor = min(max(map(len, plain.splitlines())), len(plain.splitlines()))
        assert max(map(len, program.splitlines())) <= max(width, floor)
        for row, expected in enumerate(table):
            bits = f"{row:0{n}b}"
            io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (expected, n)


def test_rotated_rendered_area_remains_linear() -> None:
    sizes = [len(thisthat(_parity(n), 1)) for n in (5, 7, 9)]
    assert sizes[-1] / (1 << 9) < 300
    assert sizes[2] / sizes[1] < 5
