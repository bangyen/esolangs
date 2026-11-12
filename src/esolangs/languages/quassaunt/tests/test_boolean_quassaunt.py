"""Tests for the Quassaunt Boolean generator."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs.languages.quassaunt import generator
from esolangs.languages.quassaunt.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_every_row,
    assert_saved_rows,
    evaluate_generated,
    measure_run,
)

#: Every one- and two-input table; a diagram's sharing bugs show here first.
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert_every_row("Quassaunt", table)


def test_equal_subtables_share_one_node() -> None:
    from esolangs.generation.helpers import short_name

    assert_analysis_complement("Quassaunt", "subtree_ids")
    assert generator.short_name is short_name
    with patch.object(
        generator,
        "short_name",
        side_effect=lambda index, alphabet: short_name(min(index, 3), alphabet),
    ) as aliased:
        assert evaluate_generated("Quassaunt", "0011") == "0000"
        assert aliased.called
    # Parity: one node per (level, parity), not one per row prefix.
    assert generator.quassaunt("0110100110010110").count("%%Ifdisjoint") == 8
    _check_store_loop()


def test_balance_cuts_only_compact_programs() -> None:
    """A compact table's balanced form is narrower than its longest word."""
    language = esolangs.Language("Quassaunt")
    for witness in construction_boundaries(language.name)["compact_balance_word_cut"]:
        table = witness.table()
        default = language.generate(table).source
        with patch.object(generator, "_cut", wraps=generator._cut) as cut:
            balanced = language.generate(table, balance=True)
        if witness.rule == "parity":
            assert cut.called
            assert max(map(len, balanced.source.splitlines())) < max(
                map(len, default.split())
            )
        else:
            assert not cut.called
            assert balanced.source.split() == default.split()
        assert_saved_rows(language, balanced, table, (0, 1, len(table) - 1))


@pytest.mark.parametrize("n", range(1, 13))
@pytest.mark.parametrize("bit", "01")
def test_constants_read_every_input(n: int, bit: str) -> None:
    program = generator.quassaunt(bit * (1 << n))
    if n == 8:
        assert len(program) == 116
    for stdin in ("0" * n, "1" * n, ("01" * n)[:n]):
        io = ScriptedIO(stdin + "Q")
        run(program, io)
        assert io.getvalue() == bit
        assert io.input_char() == ord("Q")


def _check_store_loop() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("Quassaunt")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    table = "00110110"
    baseline_steps = {}
    for options in ({}, {"width": 1}, {"balance": True}):
        program = esolangs.generate("Quassaunt", table, **options).source
        for row in (0, 1, 7):
            io = ReadFirstIO(f"{row:03b}Q", expected=3)
            machine = _Machine(program, io)
            steps, measured = measure_run(machine)
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_char() == ord("Q")
            assert not machine.globals["##Errormessage"]
            assert machine.globals["[_x]"] == frozenset({""})
            assert steps <= execution(3, program)
            assert measured.bits == workspace(3, program)
            if not options:
                baseline_steps[row] = steps
            else:
                assert steps == baseline_steps[row] + 2 * program.split().count(
                    "%%Concatenate"
                )
    assert sum(len(generator.quassaunt(f"{v:08b}")) for v in range(256)) == 272196
