"""Tests for the Sonata Boolean generator."""

import pytest

import esolangs
from esolangs import run
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    program = esolangs.generate("Sonata", table).source
    if n != 2:
        assert "0_I->%0_I" not in program
        # An exact-length setup still leaves a wrong-length binary input unanswered.
        invalid = "0" * (n + 1)
        assert run("Sonata", program, stdin=invalid).output == invalid
    elif len(set(table)) == 2:
        assert "0_I->%0_I" in program
    assert_every_row("Sonata", table, program=program)


def test_pair_table_prints_its_answer() -> None:
    """Seven essential bits store a char per row pair (all four symbols)."""
    table = "".join(f"{(r * 2654435761) >> 7 & 1}" for r in range(128))
    program = esolangs.generate("Sonata", table).source
    assert "@#b_T0->=1" in program
    assert_every_row("Sonata", table, program=program)


def _check_constants() -> None:
    assert_analysis_complement("Sonata", "symmetric_weights", "0110")
    assert_analysis_complement("Sonata", "read_at", "0010")
    from esolangs.languages.sonata.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Sonata", bit * (1 << n), **options).source
                assert len(program) == (16 if n == 2 else 2 * n + 5)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ScriptedIO(f"{row:0{n}b}")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    for _ in range(2):
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                    assert machine.halted
                    assert io.getvalue() == "=" + bit
                    assert written.bits == 8 * max(n, 2) + 2
                invalid = "0" * (n + 1)
                assert run("Sonata", program, stdin=invalid).output == invalid
    total_chars = total_steps = 0
    for value in range(256):
        table = f"{value:08b}"
        program = esolangs.generate("Sonata", table).source
        total_chars += len(program)
        for row in range(8):
            io = ScriptedIO(f"{row:03b}")
            machine = _Machine(program, io)
            while not machine.halted:
                machine.step()
                total_steps += 1
            assert io.getvalue() == "=" + table[row]
    assert (total_chars, total_steps) == (24980, 18080)
