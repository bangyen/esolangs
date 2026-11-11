"""Tests for the SendStuff Boolean generator."""

import pytest

import esolangs
from esolangs.languages.sendstuff.generator import sendstuff
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_every_row,
    measure_run,
    three_input_corpus_size,
)

#: Nonconstant one- and two-input tables; a diagram's sharing bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "01":
        assert_analysis_complement("SendStuff", "decision_layers")
    assert_every_row("SendStuff", table)


def test_equal_subtables_share_one_node() -> None:
    # Parity: one node per (level, parity), not one per row prefix.
    assert sendstuff("0110100110010110").count("!y ") == 7


@pytest.mark.medium
def test_constants_read_first_within_bounds_and_keep_a_sentinel() -> None:
    from esolangs.languages.sendstuff.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("SendStuff")["workspace"].formula

    for n in range(1, 13):
        for table in (
            "0" * (1 << n),
            "1" * (1 << n),
            "01" * (1 << (n - 1)),
            "10" * (1 << (n - 1)),
        ):
            identity = table[:2] == "01"
            negation = table[:2] == "10"
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("SendStuff", table, **options).source
                if not options and n == 8:
                    assert len(program) == (73 if identity else 94 if negation else 87)
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "SendStuff", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    steps, written = measure_run(machine, limit=n + 2)
                    assert machine.halted
                    assert io.getvalue() == table[row]
                    assert steps == n + (1 if identity else 3 if negation else 2)
                    assert written.bits <= workspace(n, program)
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("SendStuff") == 48361
