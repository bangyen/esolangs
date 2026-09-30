"""Executed tests for the Underload promise-tree generator."""

from itertools import pairwise

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.underload import run
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.underload import PAIR, _plain, underload
from tests.tools.boolean_runners import five_input_sample


def _run(table: str, row: int, width: int | None = None) -> str:
    n = len(table).bit_length() - 1
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    program = fill_runs(underload(table, width), TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    run(program, io)
    return io.getvalue()


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 3, 7, 8, 13, 40, 80])
def test_wrapped_templates_execute_every_three_input_table(width: int) -> None:
    for value in range(256):
        table = f"{value:08b}"
        template = underload(table, width)
        assert max(map(len, template.split("\n"))) <= max(5, width)
        assert template.replace("\n", "") == underload(table)
        assert "".join(_run(table, row, width) for row in range(8)) == table


@pytest.mark.medium
def test_wrapped_public_templates_preserve_input_slots() -> None:
    table = "0110100110010110"
    for width in (1, 7, 13, 40):
        template = esolangs.generate("Underload", table, width)
        for row in range(16):
            bits = [int(bit) for bit in f"{row:04b}"]
            io = ScriptedIO("")
            run(template.fill(bits), io)
            assert io.getvalue() == table[row]


@pytest.mark.parametrize("n", range(1, 4))
def test_first_eight_tables_through_three_inputs(n: int) -> None:
    """The remaining 248 tables killed no additional mutant."""
    width = 1 << n
    for value in range(min(8, 1 << width)):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 5
    for n in range(1, 8):
        template = underload("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 5 * n


def test_source_growth_is_linear() -> None:
    sizes = [len(underload("01" * (1 << (n - 1)))) for n in range(1, 13)]
    assert all(right <= 2 * left for left, right in pairwise(sizes))


@pytest.mark.medium
def test_repeated_subtrees_are_carried_and_no_table_grows() -> None:
    """The reduced, carrying tree cuts both totals and lengthens no table.

    A repeated subtree is pushed once and run by ``^`` where it recurs, a
    node whose halves agree is ``!`` and the half, and one ``S`` prints the
    leaf's bit.  19,496 characters over the 256 three-input tables fall to
    16,314 (16.3%), and 56,565 over the seeded five-input sample to 42,756
    (24.4%).
    """
    assert underload("01101001")[15:] == (
        "((((0))~((1))~^)~(~(^)~(!((1))~((0))~^)~^)~(~(!((1))~((0))~^)~(^)~^)~^)^S"
    )
    three = [format(value, "08b") for value in range(256)]
    for tables, before, after in (
        (three, 19496, 16314),
        (five_input_sample(), 56565, 42756),
    ):
        plain = [len(_plain(table)) for table in tables]
        shared = [len(underload(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for table in five_input_sample()[::10]:
        assert "".join(_run(table, row) for row in range(32)) == table
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert esolangs.verify("Underload", table), table
