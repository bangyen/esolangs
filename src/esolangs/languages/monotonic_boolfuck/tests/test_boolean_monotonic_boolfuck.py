"""Tests for the Monotonic Boolfuck Boolean generator."""

import esolangs
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_native_rows, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        from esolangs.languages.monotonic_boolfuck.interpreter import run

        program = esolangs.generate("Monotonic Boolfuck", table).source
        assert_native_rows("Monotonic Boolfuck", table, program, run, sentinel="Q")


def _check_constants() -> None:
    assert_analysis_complement("Monotonic Boolfuck", "subtree_ids")
    from esolangs.languages.monotonic_boolfuck.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            commands = 20 if n == 1 else 14 * n + 9 + 2 * int(bit)
            length = 20 if n == 1 else 3 * n + 19 + 2 * int(bit)
            bound = (
                13 + (length - 1).bit_length() + n.bit_length()
                if n == 1
                else 12
                + (length - 1).bit_length()
                + 2 * n.bit_length()
                + sum(i.bit_length() for i in range(1, n))
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Monotonic Boolfuck", bit * (1 << n), **options
                ).source
                assert len("".join(program.split())) == length
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert (steps, written.bits) == (commands, bound)
                    assert io.getvalue() == bit
                    assert (machine.state.remaining, io.past_end) == (0, 0)
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("Monotonic Boolfuck") == 36526
