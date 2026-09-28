"""Executed tests for the Smallfuck local-result tree."""

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
def test_every_table_through_three_inputs(n: int) -> None:
    width = 1 << n
    for value in range(1 << width):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 6
    for n in range(1, 8):
        template = smallfuck("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 6 * n


def test_source_growth_is_linear() -> None:
    sizes = [len(smallfuck("0110" * (1 << (n - 2)))) for n in range(2, 13)]
    assert all(right <= 2 * left + 40 for left, right in pairwise(sizes))


def test_levels_test_inputs_in_the_shorter_order() -> None:
    """Only the tested bit moves; over three inputs no template grows.

    ``10101010`` depends on input 2 alone: split on it first it is one
    node, and the total over every three-input table falls 11.8%.
    """
    assert len(smallfuck("10101010")) < len(_smallfuck_ordered("10101010", (0, 1, 2)))
    old = new = 0
    for value in range(256):
        table = f"{value:08b}"
        before, after = len(_smallfuck_ordered(table, (0, 1, 2))), len(smallfuck(table))
        assert after <= before, table
        old, new = old + before, new + after
    assert (old, new) == (65654, 57894)
