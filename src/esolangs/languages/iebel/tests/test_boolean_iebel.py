"""Tests for the IEBEL Boolean generator."""

import pytest

import esolangs
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_every_row,
    assert_saved_rows,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    assert_every_row("IEBEL", table)


def _check_constants() -> None:
    assert_analysis_complement("IEBEL", "decision_layers")
    from esolangs.languages.iebel.interpreter import _Machine

    language = esolangs.Language("IEBEL")
    witnesses = construction_boundaries(language.name)[
        "constant_read_initialization_cutoff"
    ]
    for witness in witnesses:
        n, table = witness.arity, witness.table()
        artifact = language.generate(table)
        assert artifact.source.splitlines()[0] == ("0 49 -3" if n == 7 else "0 0 -3")
        assert_saved_rows(
            language, artifact, table, (0, 1, len(table) // 2, len(table) - 1)
        )

    for n in range(1, 13):
        for bit in "01":
            commands = n + (1 if n <= 7 else 2)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("IEBEL", bit * (1 << n), **options).source
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "IEBEL", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert steps == commands
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    peak = max(peak, written.bits)
                    assert written.bits == 266 + commands.bit_length() + n.bit_length()
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("IEBEL") == 26774
