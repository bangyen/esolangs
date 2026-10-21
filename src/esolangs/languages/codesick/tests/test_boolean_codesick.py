"""Tests for the Codesick Boolean generator."""

import pytest

import esolangs
from esolangs.languages.codesick.generator import codesick

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Codesick", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Codesick", bits)
        got = esolangs.run("Codesick", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Codesick", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert codesick("0110100110010110").count(" codesick in #") == 7


@pytest.mark.parametrize("table", ["01", "0011", "00001111", "0110"])
def test_only_a_constant_table_spends_the_missing_test(table: str) -> None:
    # Root ids 0 and 1 are the constants; any other root reads through its node.
    assert not codesick(table).startswith('codesick in "" *')
    assert codesick("0" * len(table)).startswith('codesick in "" *')
