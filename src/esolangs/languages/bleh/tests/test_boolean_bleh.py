"""Tests for the Bleh Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, measure_run

#: Nonconstant one- and two-input tables; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    from esolangs.languages.bleh.tests.ablations import ablate

    program = esolangs.generate("Bleh", table)
    assert program == ablate(table, "default")
    assert_every_row("Bleh", table, program=program)


@pytest.mark.medium
def test_constants_read_first_within_bounds_and_keep_a_sentinel() -> None:
    from esolangs.languages.bleh.interpreter import _Machine
    from esolangs.languages.bleh.proof_formulas import workspace

    for n in (*range(1, 13), 19, 20, 21):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Bleh", bit * (1 << n), **options)
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
        sum(len(esolangs.generate("Bleh", format(v, "08b"))) for v in range(256))
        == 49108
    )


@pytest.mark.parametrize(
    ("table", "stdin"), [("00", ""), ("0011", "0"), ("0101", ""), ("01", "")]
)
def test_skipped_reads_reject_eof(table: str, stdin: str) -> None:
    from esolangs.exceptions import HaltError

    with pytest.raises(HaltError, match="no branch"):
        esolangs.run("Bleh", esolangs.generate("Bleh", table), stdin=stdin)


@pytest.mark.parametrize("table", ["01", "10", "0110", "0011"])
def test_entrypoint_name_is_escaped_without_widening(monkeypatch, table: str) -> None:
    from esolangs.languages.bleh import generator

    ids = generator.subtree_ids

    def reserved_id(truth_table: str) -> list[list[int]]:
        return [
            [1831090 if node == 2 else node for node in level]
            for level in ids(truth_table)
        ]

    assert generator._name(1831090, 0) == "mai0"
    monkeypatch.setattr(generator, "subtree_ids", reserved_id)
    program = generator.bleh(table)
    n = len(table).bit_length() - 1
    for row in range(len(table)):
        assert esolangs.run("Bleh", program, stdin=f"{row:0{n}b}") == table[row]
