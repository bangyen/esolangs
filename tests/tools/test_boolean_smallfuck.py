"""Executed tests for the Smallfuck banded-result tree."""

from itertools import pairwise

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.smallfuck import run
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.smallfuck import PAIR, _smallfuck_ordered, smallfuck


def _run(table: str, row: int) -> str:
    n = len(table).bit_length() - 1
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    program = fill_runs(smallfuck(table), TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    run(program, io)
    return io.getvalue()


@pytest.mark.parametrize("n", range(1, 4))
def test_first_eight_tables_through_three_inputs(n: int) -> None:
    """The remaining 248 tables killed no additional mutant."""
    width = 1 << n
    for value in range(min(8, 1 << width)):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 4
    for n in range(1, 8):
        template = smallfuck("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 4 * n


def test_source_growth_is_linear() -> None:
    # The slack covers a band boundary crossing a level as n grows.
    sizes = [len(smallfuck("0110" * (1 << (n - 2)))) for n in range(2, 13)]
    assert all(right <= 2 * left + 64 for left, right in pairwise(sizes))


def test_levels_test_inputs_in_the_shorter_order() -> None:
    """Only the tested bit moves; over three inputs no template grows."""
    assert len(smallfuck("10101010")) < len(_smallfuck_ordered("10101010", (0, 1, 2)))
    old = new = 0
    for value in range(256):
        table = f"{value:08b}"
        before, after = len(_smallfuck_ordered(table, (0, 1, 2))), len(smallfuck(table))
        assert after <= before, table
        old, new = old + before, new + after
    assert (old, new) == (22895, 19830)


def test_constant_arms_and_banded_results_shrink_the_tree() -> None:
    """Pin the three-input total: 57,894 characters before, 19,830 after."""
    assert smallfuck("0001") == TEMPLATE_CHAR * 8 + "<<<<<<[*>>>[*<*>]]"
    assert smallfuck("0110").endswith("<<<]>[*>>[*<*>]]")
    assert sum(len(smallfuck(f"{value:08b}")) for value in range(256)) == 19830


@pytest.mark.medium
def test_fresh_setters_lower_the_public_floor() -> None:
    for inputs in (1, 2, 3):
        for value in range(1 << (1 << inputs)):
            table = format(value, f"0{1 << inputs}b")
            template = esolangs.generate("Smallfuck", table, width=1)
            assert max(map(len, template.splitlines())) == 1
            for row, expected in enumerate(table):
                bits = [int(bit) for bit in format(row, f"0{inputs}b")]
                source = esolangs.instantiate("Smallfuck", template, bits, width=1)
                assert esolangs.run("Smallfuck", source) == expected


@pytest.mark.parametrize("tagged", [False, True])
def test_narrow_smallfuck_saved_provenance(*, tagged: bool) -> None:
    table = "0110"
    template = esolangs.generate("Smallfuck", table, width=1)
    source = template if tagged else str(template)
    for row, expected in enumerate(table):
        program = esolangs.instantiate(
            "Smallfuck", source, [row >> 1, row & 1], width=1, truth_table=table
        )
        assert max(map(len, program.splitlines())) == 1
        assert esolangs.run("Smallfuck", program) == expected
    with pytest.raises(ValueError, match="does not compute that table"):
        esolangs.instantiate("Smallfuck", source, [0, 1], truth_table="1001")


def test_narrow_smallfuck_preserves_fitting_and_large_execution() -> None:
    for n in (4, 5, 6):
        table = "0110" * (2 ** (n - 2))
        natural = smallfuck(table)
        assert smallfuck(table, 0) == natural
        assert smallfuck(table, len(natural)) == natural
        for row in (0, 1, 2, 3, 2**n - 1):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            template = esolangs.generate("Smallfuck", table, width=1)
            assert (
                esolangs.run(
                    "Smallfuck", esolangs.instantiate("Smallfuck", template, bits)
                )
                == table[row]
            )
