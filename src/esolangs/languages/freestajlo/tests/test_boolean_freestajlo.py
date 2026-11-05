"""Tests for the Freestajlo Boolean generator."""

import pytest

import esolangs
from esolangs.generation.wrap import balance_score
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output, assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert_every_row("Freestajlo", table)


def test_an_ignored_input_is_read_and_dropped() -> None:
    """Input 1 is ignored: ``;#`` reads it, and the literal halves."""
    assert esolangs.generate("Freestajlo", "00110011") == '"01";#;;#&.'


def test_a_constant_needs_no_index() -> None:
    _check_constants()
    assert esolangs.generate("Freestajlo", "1111") == ";;1:"


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


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.freestajlo.interpreter import run

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Freestajlo", bit * (1 << n), **options)
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(
                        esolangs.encode_inputs("Freestajlo", [int(b) for b in row])
                        + "7\n",
                        expected=2 * n,
                    )
                    assert_constant_output(run, program, io, bit, 2 * n)
                    assert io.input_num() == 7
