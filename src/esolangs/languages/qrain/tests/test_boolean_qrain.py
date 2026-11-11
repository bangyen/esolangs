"""Tests for the Qrain Boolean generator."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs.languages.qrain import generator
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_every_row,
    assert_saved_rows,
    constant_programs,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_shared_residual_admission()
        assert_analysis_complement("Qrain", "flag_tree_body")
    assert_every_row("Qrain", table)


def _check_shared_residual_admission() -> None:
    language = esolangs.Language("Qrain")
    records = construction_boundaries(language.name)
    for witness in records["multiple_shared_residual_admission"]:
        table = witness.table()
        with patch.object(
            generator, "flag_tree_body", wraps=generator.flag_tree_body
        ) as body:
            artifact = language.generate(table)
        assert body.call_args_list[0].kwargs["shared"] is not None
        banks = [call.kwargs["shared_blocks"] for call in body.call_args_list[1:]]
        assert [len(bank) for bank in banks] == ([2] if witness.arity == 5 else [])
        assert_saved_rows(language, artifact, table, range(len(table)))


def _check_constants() -> None:
    from esolangs.languages.qrain.interpreter import _Machine

    for n, bit, _options, program in constant_programs("Qrain", range(1, 13)):
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("Qrain", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine("".join(program.split()), io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, n + 10 - 2 * int(bit), written=written)
            assert steps == n + 10 - 2 * int(bit)
            assert io.getvalue() == bit
            length = n + 10 - 2 * int(bit)
            control = max((length - 4).bit_length() + 2, length.bit_length() + 1)
            assert (
                written.bits
                == control + 8 * n + 7 - int(bit) - (n == 1) + n.bit_length()
            )
            assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Qrain", f"{v:08b}").source) for v in range(256))
        == 34181
    )
