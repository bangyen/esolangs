"""Tests for the Quassaunt Boolean generator."""

import random

import pytest

import esolangs
from esolangs.languages.quassaunt.generator import quassaunt

#: Every one- and two-input table; a diagram's sharing bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Quassaunt", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Quassaunt", bits)
        got = esolangs.run("Quassaunt", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("Quassaunt", got) == table[row], (table, row)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert quassaunt("0110100110010110").count("%%Ifpropersubset") == 7


def test_balance_cuts_only_compact_programs() -> None:
    """A compact table's balanced form is narrower than its longest word."""
    from esolangs.languages.quassaunt.generator import _balance

    parity = "0110100110010110"
    default = quassaunt(parity)
    balanced = _balance(parity, default)
    assert max(map(len, balanced.splitlines())) < max(map(len, default.split()))
    wide = format(random.Random(8).getrandbits(256), "0256b")
    assert _balance(wide, quassaunt(wide)).split() == quassaunt(wide).split()
