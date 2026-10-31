"""Tests for the SendStuff Boolean generator."""

import pytest

import esolangs
from esolangs.languages.sendstuff.generator import sendstuff

#: Every one- and two-input table; a diagram's sharing bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("SendStuff", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("SendStuff", bits)
        got = esolangs.run("SendStuff", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("SendStuff", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert sendstuff("0110100110010110").count("!y ") == 7
