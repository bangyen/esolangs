"""Tests for the DINAC Boolean generator."""

import pytest

import esolangs
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.execution import run_observed as execute
from tests.support.generator_support import assert_native_rows, constant_programs
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.dinac.interpreter import run

    program = esolangs.generate("DINAC", table).source
    assert_native_rows("DINAC", table, program, run, sentinel="Q")


@pytest.mark.parametrize(
    "table", ["1" * 32, "0" * 32, "01101001" * 4, "0110" * 8, "00111100" * 4]
)
def test_larger_and_constant_tables(table: str) -> None:
    n = len(table).bit_length() - 1
    program = esolangs.generate("DINAC", table).source
    for row in range(0, len(table), 3):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("DINAC", bits)
        got = execute("DINAC", program, stdin=stdin, timeout=5).output
        assert esolangs.read_answer("DINAC", got) == table[row], (table, row)


@pytest.mark.parametrize("n", [3, 6, 11])
def test_size_is_linear_in_the_table(n: int) -> None:
    """A balanced table stays within the stated bound, names included."""
    assert (
        len(esolangs.generate("DINAC", "01" * 2 ** (n - 1)).source)
        <= 40 * 2**n + 18 * n + 120
    )


def _check_constants() -> None:
    assert_analysis_complement("DINAC", "prefix_counts")
    from esolangs.languages.dinac.interpreter import _Machine

    for n, bit, options, program in constant_programs("DINAC", range(1, 13)):
        if not options:
            assert len(program) == 5 * n + 15
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("DINAC", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "7", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 1999, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_char() == ord("7")
            if not options:
                assert steps == n + 3
                assert written.bits <= 56 + (n + 2).bit_length() + n.bit_length()

    assert (
        sum(len(esolangs.generate("DINAC", f"{v:08b}").source) for v in range(256))
        == 77660
    )
