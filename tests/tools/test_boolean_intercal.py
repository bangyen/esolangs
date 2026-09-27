"""Executed tests for the INTERCAL Shannon-expression generator."""

from itertools import pairwise

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.intercal import run
from esolangs.tools.helpers import fill_runs
from esolangs.tools.intercal import PAIR, TEMPLATE_CHAR, intercal


def _run(table: str, row: int) -> str:
    n = len(table).bit_length() - 1
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    program = fill_runs(intercal(table), TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    run(program, io)
    output = io.getvalue()
    assert output in {"\n", "I\n"}
    return "1" if output == "I\n" else "0"


@pytest.mark.parametrize("n", range(1, 4))
def test_every_table_through_three_inputs(n: int) -> None:
    width = 1 << n
    for value in range(1 << width):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 2
    for n in range(1, 8):
        template = intercal("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 2 * n


def test_source_growth_is_linear() -> None:
    sizes = [len(intercal("0110" * (1 << (n - 2)))) for n in range(2, 11)]
    assert all(right <= 2 * left + 500 for left, right in pairwise(sizes))
