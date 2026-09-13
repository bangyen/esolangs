"""Execution tests for the B-tapemark boolean generator."""

from itertools import product

import pytest

from esolangs import tools
from esolangs.interpreters.grid_based.b_tapemark import run
from esolangs.interpreters.io import ScriptedIO


def execute(program: str, bits: str) -> tuple[str, int]:
    """Run ``program`` with one input line per bit."""
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    run(program, io)
    return io.getvalue(), io.reads


@pytest.mark.parametrize("table", ["00", "01", "10", "11"])
def test_every_one_input_table(table: str) -> None:
    program = tools.b_tapemark(table)
    for bits in ("0", "1"):
        assert execute(program, bits) == (table[int(bits, 2)], 1)


def test_every_two_input_table() -> None:
    for table_bits in product("01", repeat=4):
        table = "".join(table_bits)
        program = tools.b_tapemark(table)
        for bits in map("".join, product("01", repeat=2)):
            assert execute(program, bits) == (table[int(bits, 2)], 2)


@pytest.mark.parametrize("table", ["00000001", "01101001", "11110000"])
def test_three_input_tables(table: str) -> None:
    program = tools.b_tapemark(table)
    for bits in map("".join, product("01", repeat=3)):
        assert execute(program, bits) == (table[int(bits, 2)], 3)


def test_measured_sizes() -> None:
    assert [len(tools.b_tapemark("0" * (2**n))) for n in range(1, 5)] == [
        72,
        356,
        1204,
        3460,
    ]


def test_render_has_no_blank_axis() -> None:
    """Straight corridors do not retain wholly empty rows or columns."""
    rows = tools.b_tapemark("01101001").splitlines()
    width = max(map(len, rows))
    grid = [row.ljust(width) for row in rows]
    assert all(row.strip() for row in grid)
    assert all(any(row[col] != " " for row in grid) for col in range(width))
