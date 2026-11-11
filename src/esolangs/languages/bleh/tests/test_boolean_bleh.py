"""Tests for the Bleh Boolean generator."""

import pytest

import esolangs
from esolangs import run
from esolangs.exceptions import HaltError
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, measure_run

#: Nonconstant one- and two-input tables; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


def test_every_row_prints_its_answer() -> None:
    assert_analysis_complement("Bleh", "decision_layers")
    for table in [*TABLES, "00010111", "01101001", "11101000"]:
        from esolangs.languages.bleh.tests.ablations import ablate

        program = esolangs.generate("Bleh", table).source
        assert program == ablate(table, "default")
        assert_every_row("Bleh", table, program=program)


@pytest.mark.medium
def test_constants_read_first_within_bounds_and_keep_a_sentinel() -> None:
    from esolangs.languages.bleh.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Bleh")["workspace"].formula

    for n in (*range(1, 13), 19, 20, 21):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Bleh", bit * (1 << n), **options).source
                if not options:
                    if n == 8:
                        assert len(program) == 97
                    assert program.count("a::next()") == 1
                    assert program.count("2()") == n
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "Bleh", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    steps, written = measure_run(machine, limit=12 * n + 6)
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert steps == 11 * n + row.bit_count() + 6
                    assert written.bits <= workspace(n, program)
                    assert io.reads == n
                    assert not io.past_end
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Bleh", format(v, "08b")).source) for v in range(256))
        == 49108
    )

    from esolangs.languages.bleh.tests.oracle_checks import check_accounting_bleh

    check_accounting_bleh()


def test_skipped_reads_reject_eof() -> None:
    for table, stdin in (("00", ""), ("0011", "0"), ("0101", ""), ("01", "")):
        with pytest.raises(HaltError, match="no branch"):
            run("Bleh", esolangs.generate("Bleh", table).source, stdin=stdin)


def test_entrypoint_name_is_escaped_without_widening(monkeypatch) -> None:
    from esolangs.generation import decision
    from esolangs.languages.bleh import generator

    ids = decision.subtree_ids

    def reserved_id(truth_table: str) -> list[list[int]]:
        return [
            [1831090 if node == 2 else node for node in level]
            for level in ids(truth_table)
        ]

    assert generator._name(1831090, 0) == "mai0"
    monkeypatch.setattr(decision, "subtree_ids", reserved_id)
    for table in ["01", "10", "0110", "0011"]:
        program = generator.bleh(table)
        n = len(table).bit_length() - 1
        for row in range(len(table)):
            assert run("Bleh", program, stdin=f"{row:0{n}b}").output == table[row]
