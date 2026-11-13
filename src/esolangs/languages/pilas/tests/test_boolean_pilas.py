"""Tests for the Pilas Boolean generator."""

import esolangs
from esolangs.languages.pilas.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.execution import run_observed
from tests.support.generator_support import three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        n = len(table).bit_length() - 1
        if table == "01101001":
            assert three_input_corpus_size("Pilas") == 24034

        class ReadFirstIO(ScriptedIO):
            inputs = n

            def _write(self, value):
                assert self.progress() == self.inputs
                super()._write(value)

        program = esolangs.generate("Pilas", table).source
        for row in range(len(table)):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            stdin = esolangs.encode_inputs("Pilas", bits)
            got = run_observed("Pilas", program, stdin=stdin, timeout=5).output
            io = ReadFirstIO(stdin + "7")
            run(program, io)
            assert io.getvalue() == table[row]
            assert io.progress() == n
            assert io.past_end == 0
            assert io.input_char() == ord("7")
            # The answer as the contract reads it, not the raw output.
            assert esolangs.read_answer("Pilas", got) == table[row], (table, row)


def _check_constants() -> None:
    assert_analysis_complement("Pilas", "subtree_ids")
    for n in range(1, 13):
        keep = min(
            n, max(0, (3 * n + 10 - (3 * n + 10).bit_length() - n.bit_length()) // 6)
        )

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Pilas", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 3 * n + 13 - 2 * keep + 2 * int(bit)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Pilas", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, 1999, written=written)
                    assert machine.state.stks[0] == tuple(
                        48 + value for value in list(map(int, f"{row:0{n}b}"))[:keep]
                    )
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    if not options:
                        assert steps == 4 * n - 2 * keep + 15 + 4 * int(bit)
                        assert (
                            written.bits
                            <= 6 * keep
                            + 14
                            + (3 * n + 10).bit_length()
                            + n.bit_length()
                        )
                        assert written.bits <= 3 * n + 24
