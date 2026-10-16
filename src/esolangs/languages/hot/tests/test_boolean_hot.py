"""Tests for the Hot Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Hot", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Hot", bits)
        got = esolangs.run("Hot", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Hot", got) == table[row], (table, row)


def test_the_bits_are_one_unseparated_string() -> None:
    assert esolangs.encode_inputs("Hot", [1, 0]) == "10"


def test_an_ignored_input_folds_its_subtree() -> None:
    """Inputs 0 and 1 are ignored, so their pairs are ``K`` of one half."""
    folded = len(esolangs.generate("Hot", "0110" * 4))
    assert folded < len(esolangs.generate("Hot", "0110100110010110"))
