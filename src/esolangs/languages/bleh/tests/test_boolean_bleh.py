"""Tests for the Bleh Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    n = len(table).bit_length() - 1
    program = esolangs.generate("Bleh", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Bleh", bits)
        got = esolangs.run("Bleh", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("Bleh", got) == table[row], (table, row)


def test_a_constant_still_reads_every_input() -> None:
    """Each level's constant reads one input as a statement."""
    assert esolangs.generate("Bleh", "1111") == (
        '^:std::io=a;main:=o0();o0:={a::next();o1()};o1:={a::next();a::print"1"};'
    )
