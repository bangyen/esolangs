"""Tests for the Sonata Boolean generator."""

import esolangs
from esolangs import run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import (
    assert_every_row,
    assert_saved_rows,
    constant_programs,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES
from tests.support.witness_tables import row_bits


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
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
    language = esolangs.Language("Sonata")
    for witness in construction_boundaries("Sonata")["doubling_to_paired_lookup"]:
        n, table = witness.arity, witness.table()
        artifact = language.generate(table)
        assert ("@#b_T0->=1" in artifact.source) == (n == 7)
        restored = language.load_program(language.dump_program(artifact))
        prepared = language.prepare(restored)
        for row in range(len(table)):
            result = prepared.evaluate(row_bits(row, n))
            assert result.bit == table[row]
            assert result.observation.input_position == n


def _check_constants() -> None:
    assert_analysis_complement("Sonata", "symmetric_weights", "0110")
    assert_analysis_complement("Sonata", "read_at", "0010")
    from esolangs.languages.sonata.interpreter import _Machine

    language = esolangs.Language("Sonata")
    for witness in construction_boundaries(language.name)["two_input_constant_guard"]:
        table = witness.table()
        artifact = language.generate(table)
        assert artifact.source.startswith("0^a->=1\n1^a") == (witness.arity == 2)
        assert_saved_rows(language, artifact, table, range(len(table)))

    for n, bit, _options, program in constant_programs("Sonata", range(1, 13)):
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
