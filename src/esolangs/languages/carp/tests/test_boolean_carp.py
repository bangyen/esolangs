"""Tests for the CARP Boolean generator."""

import pytest

import esolangs
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_every_row, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES
from tests.support.witness_tables import row_bits


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        assert_analysis_complement("CARP", "decision_layers")
        _check_constants()
        _check_register_cap()
    assert_every_row("CARP", table)


def _check_constants() -> None:
    from esolangs.languages.carp.interpreter import _Machine

    for n in range(1, 15):
        for bit in "01":
            commands = n + 1 + int(bit)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("CARP", bit * (1 << n), **options).source
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "CARP", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert steps == commands
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    peak = max(peak, written.bits)
                    bound = (
                        15
                        + max(2, (n + int(bit)).bit_length())
                        + (2 * n - 1).bit_length()
                    )
                    assert written.bits <= bound
                    assert io.input_num() == 7
                assert peak == bound
    assert three_input_corpus_size("CARP") == 77033


def _check_register_cap() -> None:
    language = esolangs.Language("CARP")
    admitted, refused = construction_boundaries("CARP")["register_input_cap"]
    table = admitted.table()
    artifact = language.generate(table)
    assert all(f"INP r{i} " in artifact.source for i in range(1, admitted.arity + 1))
    prepared = language.prepare(language.load_program(language.dump_program(artifact)))
    for row in (0, 1, len(table) // 2, len(table) - 1):
        result = prepared.evaluate(row_bits(row, admitted.arity))
        assert result.bit == table[row]
        assert result.observation.input_position == 2 * admitted.arity - 1
    with pytest.raises(esolangs.GeneratorCapError, match="at most fourteen inputs"):
        language.generate(refused.table())
