"""Tests for the Codesick Boolean generator."""

import pytest

import esolangs
from esolangs.languages.codesick.generator import codesick
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    from esolangs.languages.codesick.tests.ablations import ablate

    n = len(table).bit_length() - 1
    program = esolangs.generate("Codesick", table)
    assert program == ablate(table, "default")
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Codesick", bits)
        got = esolangs.run("Codesick", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Codesick", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    from esolangs.languages.codesick.interpreter import _load

    instructions, _ = _load(codesick("0110100110010110"))
    assert sum(p[2] == ("in",) and p[3] != "" for p in instructions) == 7


@pytest.mark.parametrize("table", ["01", "0011", "00001111", "0110"])
def test_only_a_constant_table_spends_the_missing_test(table: str) -> None:
    _check_constants()
    # Constants resolve input during loading, before their single output.
    assert not codesick(table).startswith('codesick in "" *')
    assert codesick("0" * len(table)) == "codesick out 0 in * *;"


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.codesick.interpreter import run

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Codesick", bit * (1 << n), **options)
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(row, expected=1)
                    assert_constant_output(run, program, io, bit, 1)
                    assert io.position() == n
