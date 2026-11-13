"""Tests for the Balik Boolean generator."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs.exceptions import InputExhaustedError
from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_native_rows,
    constant_programs,
    evaluate_generated,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
            _check_projection()
        program = esolangs.generate("Balik", table).source
        if table == "10":
            assert len(program.splitlines()) == 3
        from esolangs.languages.balik.interpreter import run

        assert_native_rows(
            "Balik", table, program, run, token=True, count_whitespace=True
        )


def _check_constants() -> None:
    from esolangs.languages.balik.interpreter import run

    assert three_input_corpus_size("Balik") == 44929
    for n, bit, _options, program in constant_programs("Balik", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row + "7", expected=n)
            assert_constant_output(run, program, io, bit, n)
            assert io.input_char() == ord("7")


def _check_projection() -> None:
    """Projection leaves preserve the tested cell used by every merge."""
    from esolangs.generation.helpers import constant_span_test, read_at
    from esolangs.languages.balik import generator

    assert generator.constant_span_test is constant_span_test
    assert generator.read_at is read_at
    with patch.object(
        generator, "constant_span_test", return_value=lambda *_: True
    ) as corrupted:
        assert evaluate_generated("Balik", "0011") == "0000"
        assert corrupted.called
    with patch.object(
        generator,
        "read_at",
        side_effect=lambda table, used, n: read_at(
            table.translate(str.maketrans("01", "10")), used, n
        ),
    ) as corrupted:
        assert evaluate_generated("Balik", "0011") == "1100"
        assert corrupted.called

    from esolangs.languages.balik.generator import balik
    from esolangs.languages.balik.interpreter import _Machine, run
    from esolangs.languages.balik.tests.formulas import execution_witness
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("Balik")["execution"].formula
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
