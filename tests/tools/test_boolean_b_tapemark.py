"""Execution tests for the B-tapemark boolean generator."""

from itertools import product

import pytest

from esolangs import tools
from esolangs.interpreters.grid_based.b_tapemark import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.helpers import essential_inputs
from tests.witness_tables import witnesses


def execute(program: str, bits: str) -> tuple[str, int]:
    """Run ``program`` with one input line per bit."""
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io)
    return io.getvalue(), io.reads


@pytest.mark.medium
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
    """Every entry costs the same three cells, whichever digit it holds.

    An ignored input's stage crosses no ``|`` and the table is copied at the
    rest, so the essential count, not the entries, sets the size.
    """
    sizes: dict[int, set[int]] = {}
    for bits in product("01", repeat=8):
        table = "".join(bits)
        count = len(essential_inputs(table, 3))
        sizes.setdefault(count, set()).add(len(tools.b_tapemark(table)))
    assert all(len(group) == 1 for group in sizes.values()), sizes


def test_render_has_no_blank_axis() -> None:
    """Straight corridors do not retain wholly empty rows or columns."""
    rows = tools.b_tapemark("01101001").splitlines()
    width = max(map(len, rows))
    grid = [row.ljust(width) for row in rows]
    assert all(row.strip() for row in grid)
    assert all(any(row[col] != " " for row in grid) for col in range(width))


@pytest.mark.medium
def test_narrow_staircase_executes_every_small_table_in_input_order() -> None:
    import esolangs

    assert (
        max(map(len, esolangs.generate("B-tapemark", "0110", width=1).splitlines()))
        == 9
    )
    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate("B-tapemark", table, width=1)
            for row, expected in enumerate(table):
                assert execute(program, format(row, f"0{n}b")) == (expected, n)


@pytest.mark.medium
def test_narrow_weighted_arms_and_fitting_layouts() -> None:
    from esolangs.tools.b_tapemark import _b_tapemark_narrow, _Builder

    for n in range(4, 7):
        table = "".join(
            str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n)
        )
        original = tools.b_tapemark(table, 10000)
        natural = max(map(len, original.splitlines()))
        assert tools.b_tapemark(table, natural) == original
        for width in (1, 9, 19, 80):
            program = tools.b_tapemark(table, width)
            assert max(map(len, program.splitlines())) <= max(
                width, len(table) // 2 + 7
            )
            for row, expected in enumerate(table):
                assert execute(program, format(row, f"0{n}b")) == (expected, n)
    sizes = [len(_b_tapemark_narrow("01" * (1 << (n - 1)), n)) for n in (7, 8, 9)]
    assert sizes[2] < 2.1 * sizes[1] < 4.41 * sizes[0]
    # Sparse standalone layouts exercise coordinate compression on either axis.
    horizontal, vertical = _Builder(), _Builder()
    horizontal.put(0, 0, ">")
    horizontal.put(100, 0, "!")
    vertical.put(0, 0, "v")
    vertical.put(0, 100, "!")
    assert execute(horizontal.render(), "") == ("", 0)
    assert execute(vertical.render(), "") == ("", 0)
    assert _Builder().render() == ""
    with pytest.raises(AssertionError, match="layout collision"):
        horizontal.put(0, 0, "v")
