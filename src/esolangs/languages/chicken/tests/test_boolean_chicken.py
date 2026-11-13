"""Tests for the Chicken Boolean generator."""

import esolangs
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import count_steps
from tests.support.execution import run_observed as run
from tests.support.generator_support import assert_every_row, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        n = len(table).bit_length() - 1
        program = esolangs.generate("Chicken", table).source
        # Missing characters are false; arithmetic coercion would produce NaN.
        for prefix in ("", "0", "1"):
            row = int(prefix.ljust(n, "0"), 2)
            assert run("Chicken", program, stdin=prefix, timeout=5).output == table[row]
        assert_every_row("Chicken", table, program=program)


def _check_constants() -> None:
    assert_analysis_complement("Chicken", "read_at")
    from esolangs.languages.chicken.interpreter import _Machine

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.position() == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Chicken", bit * (1 << n), **options).source
                assert program == ("chicken chicken\n\nchicken" if bit == "1" else "\n")
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, 1 + int(bit), written=written)
                    assert steps == 1 + int(bit)
                    assert io.getvalue() == bit
                    assert written.bits == 8 * n + 5 + 4 * int(bit)
                    assert io.past_end == 0
    assert three_input_corpus_size("Chicken") == 305139
