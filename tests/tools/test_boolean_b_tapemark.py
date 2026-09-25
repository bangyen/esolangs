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


def test_every_one_hot_table_is_addressed() -> None:
    """One row answering ``1`` pins the walk's arrival on that row alone."""
    for one in range(32):
        table = "".join("1" if i == one else "0" for i in range(32))
        program = tools.b_tapemark(table)
        for bits in map("".join, product("01", repeat=5)):
            assert execute(program, bits) == (table[int(bits, 2)], 5)


def test_measured_sizes() -> None:
    assert [len(tools.b_tapemark("0" * (2**n))) for n in range(1, 5)] == [
        106,
        221,
        364,
        545,
    ]


def test_dense_scaling_is_linear() -> None:
    """The copy is one line and the walk's runs sum to the table."""
    sizes = [len(tools.b_tapemark("01101001" * (2 ** (n - 3)))) for n in (7, 8)]
    assert sizes[1] < 2.1 * sizes[0]


def test_size_does_not_depend_on_the_table() -> None:
    """Every entry costs the same three cells, whichever digit it holds."""
    sizes = {len(tools.b_tapemark("".join(t))) for t in product("01", repeat=8)}
    assert len(sizes) == 1


def test_render_has_no_blank_axis() -> None:
    """Straight corridors do not retain wholly empty rows or columns."""
    rows = tools.b_tapemark("01101001").splitlines()
    width = max(map(len, rows))
    grid = [row.ljust(width) for row in rows]
    assert all(row.strip() for row in grid)
    assert all(any(row[col] != " " for row in grid) for col in range(width))
