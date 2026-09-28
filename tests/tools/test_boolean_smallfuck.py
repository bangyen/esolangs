"""Executed tests for the Smallfuck banded-result tree."""

from itertools import pairwise

import pytest

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
    assert len(PAIR[0]) == len(PAIR[1]) == 6
    for n in range(1, 8):
        template = smallfuck("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 6 * n


def test_source_growth_is_linear() -> None:
    # The slack covers a band boundary crossing a level as n grows.
    sizes = [len(smallfuck("0110" * (1 << (n - 2)))) for n in range(2, 13)]
    assert all(right <= 2 * left + 64 for left, right in pairwise(sizes))


def test_levels_test_inputs_in_the_shorter_order() -> None:
    """Only the tested bit moves; over three inputs no template grows.

    ``10101010`` depends on input 2 alone: split on it first it is one
    node, and the total over every three-input table falls 12.5%.
    """
    assert len(smallfuck("10101010")) < len(_smallfuck_ordered("10101010", (0, 1, 2)))
    old = new = 0
    for value in range(256):
        table = f"{value:08b}"
        before, after = len(_smallfuck_ordered(table, (0, 1, 2))), len(smallfuck(table))
        assert after <= before, table
        old, new = old + before, new + after
    assert (old, new) == (24431, 21366)


def test_constant_arms_and_banded_results_shrink_the_tree() -> None:
    """Pin the three-input total: 57,894 characters before, 21,366 after.

    A constant lower arm drops the flag (AND is two nested bit loops), a
    band of three levels shares one result cell instead of transferring
    at every level, and the moves among the closing brackets go.
    """
    assert smallfuck("0001") == TEMPLATE_CHAR * 12 + "<<<<<<[*>>>[*<*>]]"
    assert smallfuck("0110").endswith("<<<]>[*>>[*<*>]]")
    assert sum(len(smallfuck(f"{value:08b}")) for value in range(256)) == 21366
