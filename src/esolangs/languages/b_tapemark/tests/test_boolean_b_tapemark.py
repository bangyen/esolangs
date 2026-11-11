"""Execution tests for the B-tapemark boolean generator."""

import random
from itertools import product
from unittest.mock import patch

import pytest

import esolangs
from esolangs.generation.helpers import essential_inputs, grid_area
from esolangs.generation.wrap import balance_score
from esolangs.languages.b_tapemark import generator as tools
from esolangs.languages.b_tapemark.generator import (
    _b_tapemark_folded,
    _b_tapemark_narrow,
    _b_tapemark_program,
    _balance,
    _Builder,
    _closed_forms,
)
from esolangs.languages.b_tapemark.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_constant_roots,
    assert_saved_rows,
)
from tests.support.witness_tables import witnesses


def execute(program: str, bits: str, swap_marker: str = "new") -> tuple[str, int]:
    """Run ``program`` with one input line per bit."""
    io = ScriptedIO("".join(f"{bit}" for bit in bits))
    run(program, io, swap_marker=swap_marker)
    return io.getvalue(), io.reads


def test_each_dialect_answers_its_own_programs() -> None:
    """A dialect's generated programs run under that dialect's semantics."""
    assert_analysis_complement("B-tapemark", "input_weights")
    tables = [table for n in (1, 2, 3) for table in witnesses(n)]
    tables += ["01101001", "0110100110010110"]
    for swap_marker in ("new", "old"):
        settings = esolangs.Language("B-tapemark").settings(swap_marker=swap_marker)
        for table in tables:
            n = len(table).bit_length() - 1
            program = str(
                esolangs.generate("B-tapemark", table, settings=settings).source
            )
            for row, expected in enumerate(table):
                assert execute(program, format(row, f"0{n}b"), swap_marker) == (
                    expected,
                    n,
                )


def test_a_default_program_is_not_claimed_under_the_old_dialect() -> None:
    """The readings are not interchangeable: ``0110`` hangs under ``old``."""
    machine = _Machine(tools.b_tapemark("0110"), ScriptedIO("00"), swap_marker="old")
    for _ in range(5000):
        if machine.halted:
            break
        machine.step()
    assert not machine.halted


def test_swap_marker_must_be_a_registered_value() -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.Language("B-tapemark").settings(swap_marker="sideways")
    with pytest.raises(ValueError, match="swap_marker"):
        tools.b_tapemark("01", swap_marker="sideways")


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
        4,
        6,
        8,
        10,
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
    if n == 1 and bit == "0":
        assert_constant_roots("B-tapemark", run)
    table = bit * (1 << n)
    default = tools.b_tapemark(table)
    assert default == ">" + "-|" * (n - 1) + "-" + bit + "!"
    assert len(default) == 2 * n + 2
    assert len(default) < len(_b_tapemark_program(table))
    for options in ({}, {"width": 1}, {"width": 8}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("B-tapemark", table, **options).source
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
        (default, 2 * n + 2),
        (tools.b_tapemark(table, 1), 2 * n + 3),
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
    n = 8
    base = {1: "01", 2: "0110", 3: "01001110"}[len(used)]
    table = "".join(
        base[int("".join(str((row >> (n - 1 - i)) & 1) for i in used), 2)]
        for row in range(1 << n)
    )
    for width in (1, 8, 40):
        program = esolangs.generate("B-tapemark", table, width=width).source
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

    assert (
        max(
            map(
                len,
                esolangs.generate("B-tapemark", "0110", width=1).source.splitlines(),
            )
        )
        == 9
    )
    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate("B-tapemark", table, width=1).source
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
    # Sparse standalone layouts keep their blank rows and columns.
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
    assert_an_ignored_input_costs("B-tapemark", 5, 201)


def test_render_is_the_bounding_box() -> None:
    builder = _Builder()
    assert builder.render() == ""
    builder.put(0, 0, "x")
    builder.put(3, 2, "y")
    assert builder.render() == "x\n\n   y"
    assert builder.render(reflect=True) == "   y\n\nx"


@pytest.mark.parametrize(
    ("table", "length"), [("01", 100), ("10", 100), ("0011", 172), ("0101", 172)]
)
def test_the_narrow_staircase_is_exactly_sized(table: str, length: int) -> None:
    """Row spacing and the zero pad before a short projected table, to the cell."""
    assert len(esolangs.generate("B-tapemark", table, width=8).source) == length


def test_wide_reflection_turns_the_beam_right_after_the_copy() -> None:
    """The turn sits at 3 * size + 1: reflected, ``<`` follows the last copy."""
    program = esolangs.generate("B-tapemark", "01", width=40).source
    assert len(program) == 106
    assert next(row for row in program.splitlines() if "<" in row) == "   /|1*|0*<"


def test_balance_of_a_three_ones_n8_table_is_exact() -> None:
    """The reduced copy length (17/20 of the closed form) stays in the folds tried."""
    table = "".join("1" if i in (13, 107, 141) else "0" for i in range(256))
    program = str(esolangs.generate("B-tapemark", table, balance=True).source)
    assert balance_score(program) == (170, 3303, 142)


@pytest.mark.parametrize(("copy", "run"), [(1, 1), (5, 3), (16, 40)])
def test_folded_copy_and_runs_keep_the_walk(copy: int, run: int) -> None:
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
    rng = random.Random(11)
    language = esolangs.Language("B-tapemark")
    for witness in construction_boundaries(language.name)[
        "unbounded_closed_form_admission"
    ]:
        table = witness.table()
        for width in (None, 1):
            with patch.object(tools, "_closed_forms", wraps=_closed_forms) as forms:
                artifact = language.generate(table, width=width)
            assert forms.call_count == int(width is None)
            assert_saved_rows(language, artifact, table, range(len(table)))

    for bits in (2, 4, 6, 7):
        table = "".join(rng.choice("01") for _ in range(1 << bits))
        strip, chosen = _b_tapemark_program(table), tools.b_tapemark(table)
        layouts = [strip, *_closed_forms(table)]
        assert grid_area(chosen) == min(map(grid_area, layouts))
        assert chosen == strip or grid_area(chosen) < grid_area(strip)
        assert _evaluate("B-tapemark", chosen, inputs=bits) == table
    assert tools.b_tapemark("0" * 16) == ">" + "-|" * 3 + "-0!"


def test_balance_folds_a_random_table() -> None:
    table = "".join(str((value * 73 + value // 3) & 1) for value in range(64))
    balanced = esolangs.generate("B-tapemark", table, balance=True).source
    # 202 columns unfolded; the stages' seven rows apiece floor the height.
    assert (
        balance_score(balanced)[0] < 130 < balance_score(_b_tapemark_program(table))[0]
    )


@pytest.mark.parametrize("depth", range(4, 10))
def test_fold_widths_match_the_swept_optimum(depth: int) -> None:
    """The closed-form copy length is within 3% of every copy and run swept."""
    table = "".join(str((value * 73 + value // 3) & 1) for value in range(1 << depth))
    copies = {round(2 ** (step / 4)) for step in range(4 * depth + 1)}
    swept = min(
        balance_score(_b_tapemark_folded(table, copy, run))[0]
        for copy in copies
        for run in {max(1, 3 * copy - 12), len(table)}
    )
    got = balance_score(_balance(table, tools.b_tapemark(table)))[0]
    assert got <= 1.03 * swept


def test_area_oriented_fold_executes_every_five_input_row() -> None:
    table = "".join(str(row.bit_count() & 1) for row in range(32))
    program = tools.b_tapemark(table)
    assert grid_area(program) == 1750
    for row in range(32):
        assert execute(program, format(row, "05b")) == (table[row], 5)
