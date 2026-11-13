"""Tests for the Caballo Boolean generator."""

import esolangs
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, constant_programs
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        assert_every_row("Caballo", table)


def _check_constants() -> None:
    assert_analysis_complement("Caballo", "subtree_ids")
    from esolangs.languages.caballo.interpreter import run

    for n, bit, _options, program in constant_programs("Caballo", range(1, 13)):
        assert program.replace("\n", "") == "p" * n + ("i" if bit == "1" else "")
        for bits in ([0] * n, [1] * n):
            stdin = esolangs.encode_inputs("Caballo", bits)
            io = ReadFirstIO(stdin, expected=1)
            run(program, io)
            assert esolangs.read_answer("Caballo", io.getvalue()) == bit
            assert io.reads == 1
            assert io.position() == len(stdin)
            assert io.past_end == 0

    assert (
        sum(len(esolangs.generate("Caballo", f"{v:08b}").source) for v in range(256))
        == 10072
    )
