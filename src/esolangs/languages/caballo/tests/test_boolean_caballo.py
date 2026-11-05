"""Tests for the Caballo Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    assert_every_row("Caballo", table)


def _check_constants() -> None:
    from esolangs.languages.caballo.interpreter import run

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Caballo", bit * (1 << n), **options)
                assert program.replace("\n", "") == "p" * n + (
                    "i" if bit == "1" else ""
                )
                for bits in ([0] * n, [1] * n):
                    stdin = esolangs.encode_inputs("Caballo", bits)
                    io = ReadFirstIO(stdin, expected=1)
                    run(program, io)
                    assert esolangs.read_answer("Caballo", io.getvalue()) == bit
                    assert io.reads == 1
                    assert io.position() == len(stdin)
                    assert io.past_end == 0

    assert (
        sum(len(esolangs.generate("Caballo", f"{v:08b}")) for v in range(256)) == 10072
    )
