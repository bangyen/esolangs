"""Tests for the Between Boolean generator."""

import esolangs
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_every_row, constant_programs
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        assert_every_row("Between", table)


def test_ignored_inputs_are_read_but_never_tested() -> None:
    """An ignored input reads into the scratch variable; no line tests it."""
    program = esolangs.generate("Between", "00110011").source  # depends on input 1 only
    assert program.count("]i.") == 3
    assert program.count("f([") == 1


def test_constant_table_reads_every_input() -> None:
    _check_constants()
    program = esolangs.generate("Between", "1111").source
    assert program.count("]i.") == 2
    assert "f(" not in program


def test_equal_subtables_are_one_block() -> None:
    """A repeated subtable is placed once and branched to."""
    from esolangs.languages.between import generator

    assert not hasattr(generator, "_diagram")
    assert_analysis_complement("Between", "reduced_diagram")
    once = esolangs.generate("Between", "01100110").source
    assert once.count("p.") == 2


def _check_constants() -> None:
    from esolangs.languages.between.interpreter import _Machine

    for n, bit, options, program in constant_programs("Between", range(1, 13)):
        if not options:
            assert len(program) == 6 * n + 11
        peak = 0
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("Between", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "7\n", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, n + 2, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_str() == "7"
            assert steps == n + 2
            assert written.bits <= 16 + (n + 2).bit_length() + (2 * n).bit_length()
            peak = max(peak, written.bits)
        assert peak == 16 + (n + 2).bit_length() + (2 * n).bit_length()
