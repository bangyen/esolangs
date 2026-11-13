"""Tests for the lol waht i cant edit talk pages Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_native_rows,
    constant_programs,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer(monkeypatch) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import run

    for table in (*TABLES, "00010111", "01101001", "11101000"):
        program = esolangs.generate("lol waht i cant edit talk pages", table).source
        assert_native_rows(
            "lol waht i cant edit talk pages",
            table,
            program,
            run,
            sentinel="Q",
            token=True,
        )
    from esolangs.generation import decision

    canonical = decision.fold_subtables

    def wrong_branches(table, terminals, branch):
        return canonical(table, terminals, lambda zero, one: branch(one, zero))

    with monkeypatch.context() as patch:
        patch.setattr(decision, "fold_subtables", wrong_branches)
        mutant = esolangs.generate("lol waht i cant edit talk pages", "0011").source
        with pytest.raises(AssertionError):
            assert_native_rows(
                "lol waht i cant edit talk pages",
                "0011",
                mutant,
                run,
                sentinel="Q",
                token=True,
            )


@pytest.mark.medium
def test_constant_audit_reads_before_output_and_leaves_sentinel() -> None:
    from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import _Machine

    for n, bit, options, program in constant_programs(
        "lol waht i cant edit talk pages", range(1, 13)
    ):
        if not options:
            assert len(program) == 28 * n + 23
        rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
        for row in rows:
            stdin = esolangs.encode_inputs(
                "lol waht i cant edit talk pages",
                list(map(int, format(row, f"0{n}b"))),
            )
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine(program, io)
            steps = 0
            while not machine.halted and steps < 4 * n + 10:
                machine.step()
                steps += 1
            assert machine.halted
            assert io.getvalue() == bit
            assert steps == n + 2
            assert io.input_token() == "Q"
    assert three_input_corpus_size("lol waht i cant edit talk pages") == 110463
