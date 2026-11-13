"""Tests for the HQ9+ with headers Boolean generator."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import (
    assert_every_row,
    evaluate_generated,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            from esolangs.languages.hq9_with_headers import generator

            answer = (
                *generator._ANSWER[:-1],
                f"[~:: q h {generator._hex('p("0")')} {generator._hex('p("1")')}]",
            )
            with patch.object(generator, "_ANSWER", answer):
                assert evaluate_generated("HQ9+ with headers", "0011") == "1100"
        assert_every_row("HQ9+ with headers", table)


@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_output_consumes_every_input(bit: str) -> None:
    """Direct output follows all reads and leaves the next number untouched."""
    from esolangs.languages.hq9_with_headers.interpreter import _Machine

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = 2 * n

            def _write(self, value):
                if value:
                    assert self.position() == self.expected
                super()._write(value)

        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate(
                "HQ9+ with headers", bit * (1 << n), **options
            ).source
            for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                stdin = esolangs.encode_inputs(
                    "HQ9+ with headers", list(map(int, format(row, f"0{n}b")))
                )
                io = ReadFirstIO(stdin + "7\n")
                machine = _Machine(program, io)
                steps = 0
                while not machine.halted and steps < n + 3:
                    machine.step()
                    steps += 1
                assert machine.halted
                assert steps == n + 2
                assert io.getvalue() == bit
                assert io.position() == len(stdin)
                assert io.input_num() == 7
            if n == 8:
                assert len(program) == 180
    assert three_input_corpus_size("HQ9+ with headers") == 84802
