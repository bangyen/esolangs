"""Tests for the Aprknia Boolean generator."""

import esolangs
from esolangs.runtime.io import ScriptedIO
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_native_rows,
    constant_programs,
    measure_run,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
            _check_quotient_guard()
        from esolangs.languages.aprknia.interpreter import run

        program = esolangs.generate("Aprknia", table).source
        assert isinstance(program, str)

        assert_native_rows("Aprknia", table, program, run)


def _check_constants() -> None:
    assert_analysis_complement("Aprknia", "subtree_ids")
    from esolangs.languages.aprknia.interpreter import run

    for n, bit, _options, program in constant_programs("Aprknia", range(1, 13)):
        assert isinstance(program, str)
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row + "7", expected=n)
            assert_constant_output(run, program, io, bit, n)
            assert io.input_char() == ord("7")


def _check_quotient_guard() -> None:
    from esolangs.languages.aprknia.generator import aprknia
    from esolangs.languages.aprknia.interpreter import _Machine

    for code in range(256):
        table = f"{code:08b}"
        for row, expected in enumerate(table):
            io = ScriptedIO(f"{row:03b}" + "7")
            machine = _Machine(aprknia(table), io)
            while not machine.halted:
                machine.step()
            assert io.getvalue() == expected
            assert io.reads == 3
            assert io.input_char() == ord("7")
    for n in (1, 2, 3, 5, 16):
        table = "1" * ((1 << n) - 1) + "0"
        program = aprknia(table)
        machine = _Machine(program, ScriptedIO("1" * n))
        commands, written = measure_run(machine)
        assert isinstance(machine.io, ScriptedIO)
        assert machine.io.getvalue() == "0"
        assert commands == 18 * n + 5
        fixed = len(program).bit_length() + n.bit_length() + 13
        assert written.bits <= 34 * n + fixed
        if n == 16:
            # The inherited coefficient 32 is false: this run uses553 >540.
            assert written.bits > 32 * n + fixed
    # Three exact-zero reset sites disappear beyond the quotient guard itself.
    parity = "".join(str(row.bit_count() & 1) for row in range(16))
    assert len(aprknia(parity)) == 305
