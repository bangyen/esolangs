"""Tests for the Interprogck8 Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


def _answer(program: str, n: int, row: int) -> str:
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    stdin = esolangs.encode_inputs("Interprogck8", bits)
    got = esolangs.run("Interprogck8", program, stdin=stdin, timeout=30)
    return esolangs.read_answer("Interprogck8", got)


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Interprogck8", table)
    for row in range(len(table)):
        assert _answer(program, n, row) == table[row], (table, row)


@pytest.mark.medium
@pytest.mark.parametrize("hot", [1, 1071414])
def test_a_deep_path_keeps_its_lanes_apart(hot: int) -> None:
    """A one-hot table keeps an ancestor's lane in the air at every depth.

    Lanes along a path advance 4 a 0 step and 2 a 1 step mod 82, so two
    collide only some 21 levels apart: a read that ignored the air built
    these two at ``n = 22`` into a flight hitting another lane's stop.
    """
    n = 22
    table = "0" * hot + "1" + "0" * ((1 << n) - hot - 1)
    program = esolangs.generate("Interprogck8", table)
    for row in (hot, hot ^ 1, hot ^ (1 << (n - 1)), 0):
        assert _answer(program, n, row) == table[row], row
