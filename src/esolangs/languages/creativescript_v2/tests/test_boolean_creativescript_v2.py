"""Tests for the CreativeScript v2 Boolean generator."""

import esolangs
from scripts.benchmark import WrittenState
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_every_row, constant_programs
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        assert_every_row("CreativeScript v2", table)


def _check_constants() -> None:
    from esolangs.languages.creativescript_v2.interpreter import _Machine

    for n, bit, options, program in constant_programs(
        "CreativeScript v2", range(1, 13)
    ):
        if not options:
            assert len(program) == 6 * n + 6
        peak = 0
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs(
                "CreativeScript v2", list(map(int, f"{row:0{n}b}"))
            )
            io = ReadFirstIO(stdin + "\n7\n", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, n + 1, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_num() == 7
            assert steps == n + 1
            assert written.bits <= 1 + (n + 1).bit_length() + (2 * n - 1).bit_length()
            peak = max(peak, written.bits)
        assert peak == 1 + (n + 1).bit_length() + (2 * n - 1).bit_length()
