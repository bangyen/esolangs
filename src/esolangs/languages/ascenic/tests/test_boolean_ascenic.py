"""Tests for the Ascenic Boolean generator."""

from unittest.mock import patch

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_native_rows, evaluate_generated
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize(
    "table",
    [*TABLES, "00010111", "01101001", "11101000", "00001111", "01010101", "00110011"],
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    program = esolangs.generate("Ascenic", table).source
    from esolangs.languages.ascenic.interpreter import run

    assert_native_rows("Ascenic", table, program, run, sentinel="\nQ\n", token=True)


def test_ignored_inputs_are_popped_not_scanned() -> None:
    """Two ignored inputs of six leave a four-row scan, not a 64-row one."""
    from esolangs.generation.algebraic import parity_bias
    from esolangs.languages.ascenic import generator

    assert generator.parity_bias is parity_bias
    with patch.object(
        generator,
        "parity_bias",
        side_effect=lambda table: (
            None if (bias := parity_bias(table)) is None else 1 - bias
        ),
    ) as corrupted:
        assert evaluate_generated("Ascenic", "01101001") == "10010110"
        assert corrupted.called

    table = "0110" * 16
    assert len(esolangs.generate("Ascenic", table).source) < 1000


@pytest.mark.parametrize("n", [1, 3, 4, 6, 7, 8, 12])
def test_named_tables_read_first_and_leave_the_next_record(n) -> None:
    from esolangs.languages.ascenic.interpreter import run

    rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
    for bit in "01":
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Ascenic", bit * (1 << n), **options).source
            if not options:
                assert len(program) == 2 * n * n + 17 * n - 1 + 6 * int(bit)
            for row in rows:
                io = ReadFirstIO("\n".join(format(row, f"0{n}b")) + "\nQ\n", expected=n)
                run(program, io)
                assert io.getvalue() == bit
                assert io.reads == n
                assert io.input_token() == "Q"

    for invert in (False, True):
        table = "".join(str((row.bit_count() % 2) ^ invert) for row in range(1 << n))
        program = esolangs.generate("Ascenic", table).source
        for row in rows:
            io = ReadFirstIO("\n".join(format(row, f"0{n}b")) + "\nQ\n", expected=n)
            run(program, io)
            assert io.getvalue() == table[row]
            assert io.reads == n
            assert io.past_end == 0
            assert io.input_token() == "Q"


def test_three_input_corpus_size() -> None:
    assert (
        sum(
            len(esolangs.generate("Ascenic", format(value, "08b")).source)
            for value in range(256)
        )
        == 264468
    )
