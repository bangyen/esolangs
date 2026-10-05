"""Every small table and named private LaserFuck construction."""

import itertools

import pytest

from esolangs.tools.helpers import permute_truth_table
from esolangs.tools.laserfuck import (
    _laserfuck_build,
    _laserfuck_raise_funnel,
    balance_laserfuck,
    laserfuck,
    layout,
)
from tests.interpreters.laserfuck_observer import check


@pytest.mark.parametrize(
    ("n", "value"), [(n, value) for n in range(1, 4) for value in range(1 << (1 << n))]
)
@pytest.mark.parametrize("heading", range(4))
def test_every_small_table(n, value, heading):
    table = format(value, f"0{1 << n}b")
    for source in {laserfuck(table, width) for width in (None, 1, 13, 100)}:
        for row, answer in enumerate(table):
            output, _ = check(source, format(row, f"0{n}b"), heading)
            assert output == answer


@pytest.mark.parametrize("table", ["0001", "1110", "10000010", "11111110"])
@pytest.mark.parametrize("heading", range(4))
@pytest.mark.medium
def test_private_permuted_layouts(table, heading):
    n = len(table).bit_length() - 1
    for perm in itertools.permutations(range(n)):
        ordered = permute_truth_table(table, perm)
        for width in (1, 20, 80):
            for vertical in (False, True):
                source = _laserfuck_raise_funnel(
                    _laserfuck_build(ordered, perm, width, vertical_tree=vertical)
                )
                for row, answer in enumerate(table):
                    output, _ = check(source, format(row, f"0{n}b"), heading)
                    assert output == answer


@pytest.mark.parametrize("table", ["00", "11", "0110", "0001", "10000010", "11111110"])
@pytest.mark.parametrize("heading", range(4))
def test_balanced_layout(table, heading):
    source = balance_laserfuck(table, laserfuck(table))
    n = len(table).bit_length() - 1
    for row, answer in enumerate(table):
        output, _ = check(source, format(row, f"0{n}b"), heading)
        assert output == answer


@pytest.mark.parametrize(
    ("ops", "answer"),
    [
        ("+" * 40 + "->++<" + "-" * 4, "35\n2"),
        ("-" * 30 + ">+++", "3"),
        ("+" * 30, "30"),
    ],
)
@pytest.mark.parametrize("width", [7, 20, 40])
def test_folded_tape_runs(ops, answer, width):
    grid = [list("  o" + " " * (width - 3)), list(" " * width)]
    row, col = layout.fold(grid, ops, 0, 3, width)
    grid[row][col] = "x"
    source = "\n".join("".join(line).rstrip() for line in grid)
    output, _ = check(source, "", 3)
    assert output == answer
