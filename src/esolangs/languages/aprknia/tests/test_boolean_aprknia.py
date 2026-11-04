"""Tests for the Aprknia Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_constant_output, measure_run

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_quotient_guard()
    from esolangs.languages.aprknia.interpreter import run

    n = len(table).bit_length() - 1

    program = esolangs.generate("Aprknia", table)
    assert isinstance(program, str)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Aprknia", bits)
        io = ReadFirstIO(stdin + "7", expected=n)
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_char() == ord("7")
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Aprknia", got) == table[row], (table, row)


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.aprknia.interpreter import run

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Aprknia", bit * (1 << n), **options)
                assert isinstance(program, str)
                for row in ("0" * n, "1" * n):
                    io = ReadFirstIO(row + "7", expected=n)
                    assert_constant_output(run, program, io, bit, n)
                    assert io.input_char() == ord("7")


def _check_quotient_guard() -> None:
    from esolangs.languages.aprknia.generator import aprknia
    from esolangs.languages.aprknia.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

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
