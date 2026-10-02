"""Narrow Minifuck layouts preserve fresh walks and atomic input setters."""

import random

import pytest

import esolangs
from esolangs.tools.helpers import TEMPLATE_CHAR, mark_runs
from esolangs.tools.minifuck import _solve, minifuck, minifuck_setters
from esolangs.tools.minifuck.sim import PAIR
from esolangs.tools.wrap import wrap_program


@pytest.mark.parametrize("inputs", [1, 2, 3])
@pytest.mark.medium
def test_every_small_minifuck_table_executes_at_the_new_floor(inputs: int) -> None:
    for value in range(1 << (1 << inputs)):
        table = format(value, f"0{1 << inputs}b")
        assert minifuck(table) == _solve(table)
        template = esolangs.generate("Minifuck", table, 1)
        assert max(map(len, template.splitlines())) <= 4
        assert template.count(template.char) == sum(
            len(pair[0]) for pair in minifuck_setters(template, inputs)
        )
        for row, expected in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{inputs}b")]
            source = esolangs.instantiate(
                "Minifuck", template, bits, 1, truth_table=table
            )
            assert esolangs.run("Minifuck", source) == expected


@pytest.mark.parametrize("width", [1, 3, 4, 11, 40, 80])
@pytest.mark.parametrize("plain", [False, True])
def test_minifuck_layout_and_post_fill_wrapper_preserve_provenance(
    width: int, *, plain: bool
) -> None:
    table = "0110"
    template = esolangs.generate("Minifuck", table, width)
    if plain:
        template = str(template)
    for row, expected in enumerate(table):
        bits = [row >> 1, row & 1]
        source = esolangs.instantiate("Minifuck", template, bits, 1, truth_table=table)
        assert esolangs.run("Minifuck", source) == expected
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("Minifuck", template, [0, 0], 1, truth_table="0001")


@pytest.mark.parametrize("inputs", [4, 5, 6, 8])
@pytest.mark.parametrize("width", [1, 4, 11])
def test_minifuck_larger_narrow_layouts_execute_sampled_rows(
    inputs: int, width: int
) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    template = esolangs.generate("Minifuck", table, width)
    assert max(map(len, template.splitlines())) <= max(width, 4)
    for row in [0, 1, len(table) // 2, len(table) - 2, len(table) - 1]:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        source = esolangs.instantiate(
            "Minifuck", str(template), bits, 1, truth_table=table
        )
        assert esolangs.run("Minifuck", source) == table[row]


def test_minifuck_xor_floor_and_rendered_size_tradeoff() -> None:
    table = "0110"
    natural = mark_runs(minifuck(table), TEMPLATE_CHAR, (PAIR,) * 2)
    assert max(map(len, wrap_program(natural, "minifuck", 1).splitlines())) == 33
    assert max(map(len, esolangs.generate("Minifuck", table, 1).splitlines())) == 1


@pytest.mark.parametrize("inputs", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("complement", [0, 1])
def test_minifuck_one_column_parity_every_row(inputs: int, complement: int) -> None:
    table = "".join(
        str((row.bit_count() & 1) ^ complement) for row in range(1 << inputs)
    )
    template = esolangs.generate("Minifuck", table, 1)
    assert max(map(len, template.splitlines())) == 1
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        program = esolangs.instantiate("Minifuck", template, bits, 1, truth_table=table)
        assert max(map(len, program.splitlines())) == 1
        assert esolangs.run("Minifuck", program) == expected


def test_minifuck_parity_provenance_retains_skip_absorbing_linefeeds() -> None:
    template = str(esolangs.generate("Minifuck", "0110", 1))
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate(
            "Minifuck", template.replace("[\n[", "[[", 1), [0, 1], truth_table="0110"
        )
