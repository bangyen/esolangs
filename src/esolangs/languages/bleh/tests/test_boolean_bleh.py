"""Tests for the Bleh Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import measure_run

#: Nonconstant one- and two-input tables; a diagram's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(1, 2**2**n - 1)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    from esolangs.languages.bleh.tests.ablations import ablate

    n = len(table).bit_length() - 1
    program = esolangs.generate("Bleh", table)
    assert program == ablate(table, "default")
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Bleh", bits)
        got = esolangs.run("Bleh", program, stdin=stdin, timeout=5)
        assert esolangs.read_answer("Bleh", got) == table[row], (table, row)


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
                        assert len(program) == 77
                    assert program.count("a::next()") == 1
                    assert program.count("2()") == n
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    stdin = esolangs.encode_inputs(
                        "Bleh", list(map(int, format(row, f"0{n}b")))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    steps, written = measure_run(machine, limit=5 * n + 6)
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert steps == 5 * n + 6
                    assert written.bits <= workspace(n, program)
                    assert io.reads == n
                    assert not io.past_end
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Bleh", format(v, "08b"))) for v in range(256))
        == 43988
    )
