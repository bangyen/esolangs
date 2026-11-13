"""Tests for the Object disoriented Boolean generator."""

from itertools import islice

import pytest

import esolangs
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_native_rows,
    constant_programs,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.medium
def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_native_constants()
            assert_analysis_complement("Object disoriented", "subtree_ids")
        from esolangs.languages.object_disoriented.interpreter import run

        program = esolangs.generate("Object disoriented", table).source
        assert_native_rows(
            "Object disoriented", table, program, run, sentinel="Q", token=True
        )

        from .workspace_checks import check_accounting_object_disoriented

        check_accounting_object_disoriented(table)


def _check_native_constants() -> None:
    from esolangs.languages.object_disoriented.interpreter import _Machine

    for n, bit, _options, program in constant_programs(
        "Object disoriented", range(1, 13)
    ):
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs(
                "Object disoriented", list(map(int, f"{row:0{n}b}"))
            )
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 16 * n + 28, written=written)
            assert steps == 16 * n + 28
            assert written.bits == 48 + 2 * n.bit_length()
            assert io.getvalue() == bit
            assert io.input_char() == ord("Q")

    from esolangs.languages.object_disoriented.generator import _NAME_CHARS, _names

    base = len(_NAME_CHARS)
    rank = sum(
        _NAME_CHARS.index(char) * base ** (3 - i) for i, char in enumerate("main")
    )
    before = sum(base**size for size in (1, 2, 3)) + rank - 1
    assert list(islice(_names(), before, before + 2)) == ["maim", "maio"]

    assert three_input_corpus_size("Object disoriented") == 48562
