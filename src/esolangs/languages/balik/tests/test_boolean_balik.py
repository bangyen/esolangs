"""Tests for the Balik Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output, assert_native_rows
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_projection()
    program = esolangs.generate("Balik", table).source
    if table == "10":
        assert len(program.splitlines()) == 3
    from esolangs.languages.balik.interpreter import run

    assert_native_rows("Balik", table, program, run, token=True, count_whitespace=True)


def _check_constants() -> None:
    from esolangs.languages.balik.interpreter import run

    assert (
        sum(len(esolangs.generate("Balik", f"{k:08b}").source) for k in range(256))
        == 44929
    )
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Balik", bit * (1 << n), **options).source
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(row + "7", expected=n)
                    assert_constant_output(run, program, io, bit, n)
                    assert io.input_char() == ord("7")


def _check_projection() -> None:
    """Projection leaves preserve the tested cell used by every merge."""
    from esolangs.exceptions import InputExhaustedError
    from esolangs.languages.balik.generator import balik
    from esolangs.languages.balik.interpreter import _Machine, run
    from esolangs.languages.balik.proof_formulas import execution
    from esolangs.languages.balik.tests.formulas import execution_witness
    from esolangs.runtime.io import ScriptedIO

    for table in ("00001111", "00110011", "01010101", "01101001"):
        for row in range(8):
            io = ScriptedIO(f"{row:03b}" + "2")
            run(balik(table), io)
            assert io.getvalue() == table[row]
            assert io.reads == 3
            assert io.past_end == 0
            assert io.input_char() == ord("2")
        with pytest.raises(InputExhaustedError):
            run(balik(table), ScriptedIO("01"))
    for n in (1, 2, 3, 4, 5):
        code = balik(execution_witness(n))
        machine = _Machine(code, ScriptedIO("1" * n))
        commands = 0
        while not machine.halted:
            machine.step()
            commands += 1
        assert commands == execution(n, code)
