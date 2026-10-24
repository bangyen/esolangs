"""Execution tests for the B-tapemark boolean generator."""

from itertools import product

import pytest

import esolangs
from esolangs.generation.helpers import essential_inputs
from esolangs.generation.wrap import balance_score
from esolangs.languages import generators as tools
from esolangs.languages.b_tapemark.generator import _Builder
from esolangs.languages.b_tapemark.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import assert_an_ignored_input_costs
from tests.support.witness_tables import witnesses


def execute(program: str, bits: str) -> tuple[str, int]:
    """Run ``program`` with one input line per bit."""
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io)
    return io.getvalue(), io.reads


@pytest.mark.medium
@pytest.mark.parametrize(
    "ones", [(0, 15, 31), pytest.param(range(32), marks=pytest.mark.slow)]
)
def test_every_one_hot_table_is_addressed(ones: tuple[int, ...] | range) -> None:
    """One row answering ``1`` pins the walk's arrival on that row alone."""
    for one in ones:
        table = "".join("1" if i == one else "0" for i in range(32))
        program = tools.b_tapemark(table)
        for bits in map("".join, product("01", repeat=5)):
            assert execute(program, bits) == (table[int(bits, 2)], 5)


def test_measured_sizes() -> None:
    assert [len(tools.b_tapemark("0" * (2**n))) for n in range(1, 5)] == [
        5,
        7,
        9,
        11,
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


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_each_input_and_prints_a_literal(n, bit) -> None:
    import esolangs
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.b_tapemark.generator import _b_tapemark_program
    from esolangs.languages.b_tapemark.interpreter import _Machine

    table = bit * (1 << n)
    default = tools.b_tapemark(table)
    assert default == ">" + "-|" * n + bit + "!"
    assert len(default) == 2 * n + 3
    assert len(default) < len(_b_tapemark_program(table))
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("B-tapemark", table, **options)
        for row in range(1 << n):
            bits = format(row, f"0{n}b")
            assert execute(program, bits) == (bit, n)
        if options.get("balance"):
            legacy = _b_tapemark_program(table)
            old = min(
                legacy,
                _b_tapemark_program(table, max(map(len, legacy.splitlines()))),
                _b_tapemark_program(table, 1),
                key=balance_score,
            )
            assert balance_score(program) <= balance_score(old)
    for program, expected in (
        (default, 2 * n + 3),
        (tools.b_tapemark(table, 1), 2 * n + 4),
    ):
        io = ScriptedIO("1" * n + "0")
        machine = _Machine(program, io)
        for _ in range(expected):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.position() == n


@pytest.mark.medium
@pytest.mark.parametrize("used", [(i,) for i in range(8)] + [(0, 7), (0, 3, 7)])
def test_narrow_short_projected_table_keeps_ignored_selectors_out(used) -> None:
    import esolangs
    from esolangs.languages.b_tapemark.generator import _b_tapemark_program

    n = 8
    base = {1: "01", 2: "0110", 3: "01001110"}[len(used)]
    table = "".join(
        base[int("".join(str((row >> (n - 1 - i)) & 1) for i in used), 2)]
        for row in range(1 << n)
    )
    for width in (1, 8, 40):
        program = esolangs.generate("B-tapemark", table, width=width)
        legacy = _b_tapemark_program(table, width, keep_full_narrow=True)
        assert len(program) <= len(legacy)
        if width <= 8:
            assert len(program) < len(legacy)
        for row, bit in enumerate(table):
            assert execute(program, format(row, f"0{n}b")) == (bit, n)


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
def test_narrow_drops_ignored_inputs_but_reads_them() -> None:
    """Inputs 1 and 3 are ignored: smaller than the full table, all five read."""
    n = 5
    base = "01101001"
    table = "".join(
        base[((row >> 4) & 1) << 2 | ((row >> 2) & 1) << 1 | (row & 1)]
        for row in range(1 << n)
    )
    program = tools.b_tapemark(table, 12)
    parity = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    assert len(program) < 0.7 * len(tools.b_tapemark(parity, 12))
    for row, expected in enumerate(table):
        assert execute(program, format(row, f"0{n}b")) == (expected, n)


@pytest.mark.medium
def test_narrow_weighted_arms_and_fitting_layouts() -> None:
    from esolangs.languages.b_tapemark.generator import _b_tapemark_narrow, _Builder

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
    sizes = [
        len(
            _b_tapemark_narrow(
                "01" * (1 << (n - 1)), n, [1 << (n - 1 - i) for i in range(n)]
            )
        )
        for n in (7, 8, 9)
    ]
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


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """Its stage, crossing no ``|``."""
    assert_an_ignored_input_costs("B-tapemark", 5, 58)


def test_sparse_tapemark_columns_do_not_scan_the_coordinate_span() -> None:
    builder = _Builder()
    assert builder.render() == ""
    builder.put(0, 0, "x")
    builder.put(10**9, 1, "y")
    assert builder.render() == "x\n y"
    assert builder.render(reflect=True) == " y\nx"


@pytest.mark.parametrize(
    ("table", "length"), [("01", 100), ("10", 100), ("0011", 172), ("0101", 172)]
)
def test_the_narrow_staircase_is_exactly_sized(table: str, length: int) -> None:
    """Row spacing and the zero pad before a short projected table, to the cell."""
    assert len(esolangs.generate("B-tapemark", table, width=8)) == length


def test_wide_reflection_turns_the_beam_right_after_the_copy() -> None:
    """The turn sits at 3 * size + 1: reflected, ``<`` follows the last copy."""
    program = esolangs.generate("B-tapemark", "01", width=40)
    assert len(program) == 106
    assert next(row for row in program.splitlines() if "<" in row) == "   /|1*|0*<"


def test_balance_of_a_three_ones_n8_table_is_exact() -> None:
    """The reduced copy length (17/20 of the closed form) stays in the folds tried."""
    table = "".join("1" if i in (13, 107, 141) else "0" for i in range(256))
    program = str(esolangs.generate("B-tapemark", table, balance=True))
    assert balance_score(program) == (170, 3297, 148)


@pytest.mark.parametrize(("copy", "run"), [(1, 1), (5, 3), (16, 40)])
def test_folded_copy_and_runs_keep_the_walk(copy: int, run: int) -> None:
    from esolangs.languages.b_tapemark.generator import _b_tapemark_folded
    from esolangs.runtime._evaluate import _evaluate

    # The second input is ignored, so its stage crosses no run.
    table = "".join(
        str((i >> 4) ^ (i & 1) ^ (i >> 1) & (i >> 2) & 1) for i in range(32)
    )
    program = _b_tapemark_folded(table, copy, run)
    assert _evaluate("B-tapemark", program, inputs=5) == table
    # A positive control: flipping one copied digit flips some answer.
    mutant = program.replace("|0*", "|1*", 1)
    assert _evaluate("B-tapemark", mutant, inputs=5) != table


def test_the_default_is_the_least_by_area_of_the_strip_and_closed_forms() -> None:
    """The strip wins a tie; each layout the default takes runs and is no larger."""
    import random

    from esolangs.generation.helpers import grid_area
    from esolangs.languages.b_tapemark.generator import (
        _b_tapemark_program,
        _closed_forms,
    )
    from esolangs.runtime._evaluate import _evaluate

    rng = random.Random(11)
    for bits in (2, 4, 6, 7):
        table = "".join(rng.choice("01") for _ in range(1 << bits))
        strip, chosen = _b_tapemark_program(table), tools.b_tapemark(table)
        layouts = [strip, *_closed_forms(table)]
        assert grid_area(chosen) == min(map(grid_area, layouts))
        assert chosen == strip or grid_area(chosen) < grid_area(strip)
        assert _evaluate("B-tapemark", chosen, inputs=bits) == table
    assert tools.b_tapemark("0" * 16) == ">" + "-|" * 4 + "0!"


def test_balance_folds_a_random_table() -> None:
    import esolangs
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.b_tapemark.generator import _b_tapemark_program

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(64))
    balanced = esolangs.generate("B-tapemark", table, balance=True)
    # 202 columns unfolded; the stages' seven rows apiece floor the height.
    assert (
        balance_score(balanced)[0] < 130 < balance_score(_b_tapemark_program(table))[0]
    )


@pytest.mark.parametrize("depth", range(4, 10))
def test_fold_widths_match_the_swept_optimum(depth: int) -> None:
    """The closed-form copy length is within 3% of every copy and run swept."""
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.b_tapemark.generator import _b_tapemark_folded, _balance

    table = "".join(str((value * 73 + value // 3) & 1) for value in range(1 << depth))
    copies = {round(2 ** (step / 4)) for step in range(4 * depth + 1)}
    swept = min(
        balance_score(_b_tapemark_folded(table, copy, run))[0]
        for copy in copies
        for run in {max(1, 3 * copy - 12), len(table)}
    )
    got = balance_score(_balance(table, tools.b_tapemark(table)))[0]
    assert got <= 1.03 * swept
