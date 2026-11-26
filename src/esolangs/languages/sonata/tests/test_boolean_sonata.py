"""Tests for the Sonata Boolean generator."""

import pytest

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
            assert run("Sonata", program, stdin=invalid).unwrap().output == invalid
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
        restored = language.from_json(language.to_json(artifact))
        prepared = language.prepare(restored)
        for row in range(len(table)):
            result = prepared.evaluate(row_bits(row, n))
            assert result.answer == table[row]
            assert result.observation.input_position == n


def _check_constants() -> None:
    assert_analysis_complement("Sonata", "symmetric_outputs", "0110")
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
        assert run("Sonata", program, stdin=invalid).unwrap().output == invalid
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


def test_projection_mask_avoids_the_unicode_name_boundary() -> None:
    from esolangs.languages.sonata.generator import _MASK_FROM, _masked_program
    from esolangs.languages.sonata.interpreter import prepare_machine

    n = _MASK_FROM
    source = _masked_program(n, [0, n - 1], "0110")
    plan = prepare_machine(source.encode("utf-8").decode("utf-8"), {})
    middle = "01" * (n // 2 - 1) + "1"
    assert len(middle) == n - 2
    for first in "01":
        for last in "01":
            io = ScriptedIO(first + middle + last)
            plan.run(io)
            assert io.getvalue() == f"={int(first != last)}"
    for malformed in (middle, "00" + middle + "0"):
        io = ScriptedIO(malformed)
        plan.run(io)
        assert not io.getvalue().startswith("=")


def test_public_generator_switches_to_masks(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs import Language
    from esolangs.languages.sonata import generator

    monkeypatch.setattr(generator, "_MASK_FROM", 3)
    language = Language("Sonata")
    for table in ("00000000", "01100110", "01101001"):
        source = language.generate(table).source
        for row, answer in enumerate(table):
            assert (
                language.run(source, stdin=f"{row:03b}").unwrap().output == f"={answer}"
            )
