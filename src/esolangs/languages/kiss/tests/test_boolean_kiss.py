"""Tests for the Kiss Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_every_row, constant_programs
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str, monkeypatch) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    assert_every_row("Kiss", table)
    if table == "0011":
        from esolangs.languages.kiss import generator

        canonical = generator.subtree_ids

        def wrong_children(table):
            ids = canonical(table)
            ids[1][1] = ids[1][0]
            return ids

        with monkeypatch.context() as patch:
            patch.setattr(generator, "subtree_ids", wrong_children)
            with pytest.raises(AssertionError):
                assert_every_row("Kiss", table)


def _check_constants() -> None:
    from esolangs.languages.kiss.interpreter import _Machine

    for n, bit, options, program in constant_programs("Kiss", range(1, 13)):
        if not options:
            assert len(program) == 9 * n
        peak_steps = 0
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("Kiss", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "7", expected=n)
            machine = _Machine(program, io)
            steps = count_steps(machine, 999)
            assert io.getvalue().strip() == bit
            assert io.past_end == 0
            assert io.input_char() == ord("7")
            if not options:
                assert steps <= 4 * n - 1
                peak_steps = max(peak_steps, steps)
        if not options:
            assert peak_steps == 4 * n - 1
