"""Tests for the Freestajlo Boolean generator."""

import pytest

import esolangs
from esolangs.generation.wrap import balance_score

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Freestajlo", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Freestajlo", bits)
        got = esolangs.run("Freestajlo", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Freestajlo", got) == table[row], (table, row)


def test_an_ignored_input_is_read_and_dropped() -> None:
    """Input 1 is ignored: ``;#`` reads it, and the literal halves."""
    assert esolangs.generate("Freestajlo", "00110011") == '"01";#;;#&.'


def test_a_constant_needs_no_index() -> None:
    assert esolangs.generate("Freestajlo", "1111") == "'1;#;#."


def test_packed_words_start_at_code_35() -> None:
    """The packed literal's zero word is ``#`` and its decode subtracts 35."""
    program = esolangs.generate("Freestajlo", "11000100100111100001000100111100")
    assert program == r'"FG*E_#";2*;+2*;+2*;+2*;+$6%\6/1+&35-\2\^/2%:'


def test_balance_of_n8_cuts_the_literal() -> None:
    """The literal is cut into strings; uncut it held the width at 47+:
    (side, length, width)."""
    table = "".join("1" if (r * r * 7 + r) % 5 < 2 else "0" for r in range(256))
    program = str(esolangs.generate("Freestajlo", table, balance=True))
    assert balance_score(program) == (16, 113, 16)
