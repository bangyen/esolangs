"""Tests for the BASICER Boolean generator."""

from unittest.mock import patch

import esolangs
from esolangs.generation.decision import decision_layers
from esolangs.languages.basicer import generator
from scripts.benchmark import WrittenState
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_every_row,
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
        assert_every_row("BASICER", table)


def _check_constants() -> None:
    from esolangs.languages.basicer.interpreter import _Machine

    with patch.object(
        generator,
        "decision_layers",
        side_effect=lambda table: decision_layers(
            table.translate(str.maketrans("01", "10"))
        ),
    ) as corrupted:
        assert evaluate_generated("BASICER", "0001") == "1110"
        assert corrupted.called

    for n, bit, _options, program in constant_programs("BASICER", range(1, 13)):
        expected = [f"{i} GOTO {i + 1} {i + 1}" for i in range(1, n + 1)] + [
            f"{n + 1} PRINT {bit}"
        ]
        assert program.splitlines() == expected
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("BASICER", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "Q\n", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, n + 1, written=written)
            assert steps == n + 1
            assert io.getvalue() == bit + "\n"
            assert written.bits == (n + 1).bit_length() + (2 * n).bit_length()
            assert io.input_str() == "Q"
    assert three_input_corpus_size("BASICER") == 23222
