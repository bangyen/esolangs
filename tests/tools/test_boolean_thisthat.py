"""Executed tests for the thisthat boolean generator."""

from itertools import pairwise

import pytest

from esolangs.interpreters.grid_based.thisthat import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.thisthat import _Builder, thisthat


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


@pytest.mark.medium
def test_source_growth_is_linear_in_the_table() -> None:
    sizes = [len(thisthat("01" * (1 << (n - 1)))) for n in range(1, 15)]
    assert all(right <= 3 * left for left, right in pairwise(sizes[1:]))
    assert max(size / (1 << n) for n, size in enumerate(sizes, 1)) < 300


def test_layout_collisions_abort() -> None:
    builder = _Builder()
    builder.node((0, 0), "▣")
    with pytest.raises(ValueError, match="layout collision"):
        builder.node((0, 0), "◇")
    builder.connect([(1, 0), (2, 0)], "single")
    with pytest.raises(ValueError, match="wire collision"):
        builder.connect([(1, 0), (2, 0)], "double")
