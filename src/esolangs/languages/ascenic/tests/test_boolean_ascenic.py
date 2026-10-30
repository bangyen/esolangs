"""Tests for the Ascenic Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize(
    "table",
    [*TABLES, "00010111", "01101001", "11101000", "00001111", "01010101", "00110011"],
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Ascenic", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Ascenic", bits)
        got = esolangs.run("Ascenic", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Ascenic", got) == table[row], (table, row)


def test_ignored_inputs_are_popped_not_scanned() -> None:
    """Two ignored inputs of six leave a four-row scan, not a 64-row one."""
    table = "0110" * 16
    assert len(esolangs.generate("Ascenic", table)) < 1000
