"""Tests for the Between Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Between", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Between", bits)
        got = esolangs.run("Between", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Between", got) == table[row], (table, row)


def test_ignored_inputs_are_read_but_never_tested() -> None:
    """An ignored input reads into the scratch variable; no line tests it."""
    program = esolangs.generate("Between", "00110011")  # depends on input 1 only
    assert program.count("]i.") == 3
    assert program.count("f([") == 1


def test_constant_table_reads_every_input() -> None:
    program = esolangs.generate("Between", "1111")
    assert program.count("]i.") == 2
    assert "f(" not in program


def test_equal_subtables_are_one_block() -> None:
    """A repeated subtable is placed once and branched to."""
    once = esolangs.generate("Between", "01100110")
    assert once.count("p.") == 2
