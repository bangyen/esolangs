"""Tests for the Movesum Boolean generator."""

import random

import pytest

import esolangs
from esolangs.languages.movesum.generator import movesum
from esolangs.languages.movesum.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row


def answer(program: str, row: int, n: int) -> str:
    """Run one row through the interpreter and read its last number."""
    io = ScriptedIO("".join(f"{(row >> (n - 1 - i)) & 1}\n" for i in range(n)))
    run(program, io)
    return io.getvalue()[-1]


def test_every_table_to_three_inputs_runs_every_row() -> None:
    """Exhaustive: 2 + 16 + 256 tables, every row; a missing tick would show."""
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = movesum(table)
            for row in range(1 << n):
                assert answer(program, row, n) == table[row], (table, row)

    assert sum(len(movesum(f"{v:08b}")) for v in range(256)) == 118024


def test_random_tables_to_eight_inputs_run_every_row() -> None:
    rng = random.Random(5)
    for n in range(4, 9):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        program = movesum(table)
        for row in range(1 << n):
            assert answer(program, row, n) == table[row], (n, row)


def test_the_run_halts_on_the_row_it_names() -> None:
    """Output is the prefix of answers up to the row: the walk stops there."""
    table = "01101001"
    program = movesum(table)

    io = ReadFirstIO("1\n0\n1\n9\n", expected=3)
    run(program, io)
    assert io.getvalue() == " ".join(table[:6])
    assert io.input_token() == "9"


def test_first_line_never_holds_42() -> None:
    """The page replaces a 42 with an input, so no seeded value may be one."""
    for n in range(1, 12):
        first = movesum("0" * (1 << n)).split("\n")[0]
        assert "42" not in {t for pair in first.split() for t in pair.split("=")}


def test_a_wrong_input_row_is_answered_wrongly() -> None:
    """Positive control: the answer is read from the input, not constant."""
    table = "0110"
    program = movesum(table)
    assert [answer(program, r, 2) for r in range(4)] == list(table)
    assert answer(program, 1, 2) != answer(program, 3, 2)


@pytest.mark.parametrize("table", ["00", "11", "0110", "00010111"])
def test_registry_contract_round_trip(table: str) -> None:
    assert_every_row("Movesum", table)


@pytest.mark.parametrize("n", range(1, 13))
@pytest.mark.parametrize("bit", "01")
def test_constants_read_every_input_and_leave_the_next(n: int, bit: str) -> None:
    for row in sorted({0, (1 << n) // 3, (1 << n) - 1}):
        program = esolangs.generate("Movesum", bit * (1 << n))
        if n == 8:
            assert len(program) == 179
        io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n9\n")
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.input_token() == "9"
