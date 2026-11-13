"""Tests for the Codesick Boolean generator."""

import pytest

import esolangs
from esolangs.languages.codesick.generator import codesick
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_every_row,
    constant_programs,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        from esolangs.languages.codesick.tests.ablations import ablate

        program = esolangs.generate("Codesick", table).source
        assert program == ablate(table, "default")
        assert_every_row("Codesick", table, program=program)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    from esolangs.languages.codesick.interpreter import _load

    instructions, _ = _load(codesick("0110100110010110"))
    assert sum(p[2] == ("in",) and p[3] != "" for p in instructions) == 7


@pytest.mark.parametrize("table", ["01", "0011", "00001111", "0110"])
def test_only_a_constant_table_spends_the_missing_test(table: str) -> None:
    _check_constants()
    # Constants resolve input during loading, before their single output.
    assert not codesick(table).startswith('codesick in "" *')
    assert codesick("0" * len(table)) == "codesick out 0 in * *;"


def _check_constants() -> None:
    assert_analysis_complement("Codesick", "decision_layers")
    from esolangs.languages.codesick.interpreter import run

    for n, bit, _options, program in constant_programs("Codesick", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(row, expected=1)
            assert_constant_output(run, program, io, bit, 1)
            assert io.position() == n
