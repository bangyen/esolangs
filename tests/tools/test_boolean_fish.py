"""Executed tests for the Fish boolean generator."""

from itertools import pairwise

import pytest

from esolangs.interpreters.grid_based.fish import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.fish import fish


def _run(table: str, row: int, width: int | None = None) -> tuple[str, int]:
    n = len(table).bit_length() - 1
    bits = f"{row:0{n}b}"
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    run(fish(table, width).splitlines(), io)
    return io.getvalue(), io.reads


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 3, 4, 5, 7, 13, 40, 80])
def test_folded_lookup_executes_every_three_input_table(width: int) -> None:
    for value in range(256):
        table = f"{value:08b}"
        program = fish(table, width)
        assert max(map(len, program.split("\n"))) <= max(3, width)
        for row, expected in enumerate(table):
            assert _run(table, row, width) == (expected, 3)


@pytest.mark.parametrize("n", range(1, 4))
def test_every_table_through_three_inputs(n: int) -> None:
    """Execute all 276 non-nullary tables through Fish itself."""
    width = 1 << n
    for value in range(1 << width):
        table = f"{value:0{width}b}"
        for row, expected in enumerate(table):
            output, reads = _run(table, row)
            assert output == expected, (table, row)
            assert reads == n, (table, row)


def test_source_growth_is_linear_in_the_table() -> None:
    sizes = [len(fish("01" * (1 << (n - 1)))) for n in range(1, 13)]
    assert all(right <= 2 * left for left, right in pairwise(sizes))
