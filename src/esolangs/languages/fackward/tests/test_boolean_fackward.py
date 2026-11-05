"""Tests for the Fackward Boolean generator."""

import pytest

import esolangs
from esolangs import compat
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_native_rows
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.fackward.interpreter import run

    program = compat.generate("Fackward", table)
    assert_native_rows("Fackward", table, program, run, sentinel="Q")


def _check_constants() -> None:
    from esolangs.languages.fackward.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = compat.generate("Fackward", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 7 * n + 6
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Fackward", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 2000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    if not options:
                        assert steps == 8 * n + 4
