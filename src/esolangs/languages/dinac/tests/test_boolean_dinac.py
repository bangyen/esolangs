"""Tests for the DINAC Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("DINAC", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("DINAC", bits)
        got = esolangs.run("DINAC", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("DINAC", got) == table[row], (table, row)


@pytest.mark.parametrize("table", ["1" * 32, "0" * 32, "01101001" * 4])
def test_larger_and_constant_tables(table: str) -> None:
    n = len(table).bit_length() - 1
    program = esolangs.generate("DINAC", table)
    for row in range(0, len(table), 3):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("DINAC", bits)
        got = esolangs.run("DINAC", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("DINAC", got) == table[row], (table, row)


@pytest.mark.parametrize("n", [3, 6, 11])
def test_size_is_linear_in_the_table(n: int) -> None:
    """The densest table stays within the stated bound, names included."""
    assert len(esolangs.generate("DINAC", "1" * 2**n)) <= 51 * 2**n + 18 * n + 120
