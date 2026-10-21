"""Tests for the Stisp Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_results_in_its_answer(table: str) -> None:
    n = len(table).bit_length() - 1
    template = esolangs.generate("Stisp", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        program = esolangs.instantiate("Stisp", template, bits)
        got = esolangs.run("Stisp", program, timeout=5)
        assert esolangs.read_answer("Stisp", got) == table[row], (table, row)


def test_the_and_template_is_the_documented_one() -> None:
    assert esolangs.generate("Stisp", "0001") == (
        "3->s[0]=0;3->s[1]=2;2->s[0]=0;2->s[1]=1;c->s[x]=c;3->s[$]->s[$]"
    )


def test_an_ignored_input_is_one_equation_over_a_variable() -> None:
    assert esolangs.generate("Stisp", "0101") == (
        "3->s[x]=2;2->s[0]=0;2->s[1]=1;c->s[x]=c;3->s[$]->s[$]"
    )
