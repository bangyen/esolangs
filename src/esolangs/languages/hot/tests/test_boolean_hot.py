"""Tests for the Hot Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Hot", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Hot", bits)
        got = esolangs.run("Hot", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Hot", got) == table[row], (table, row)


def test_the_bits_are_one_unseparated_string() -> None:
    assert esolangs.encode_inputs("Hot", [1, 0]) == "10"


def test_an_ignored_input_folds_its_subtree() -> None:
    """Inputs 0 and 1 are ignored, so their pairs are ``K`` of one half."""
    folded = len(esolangs.generate("Hot", "0110" * 4))
    assert folded < len(esolangs.generate("Hot", "0110100110010110"))


@pytest.mark.parametrize("n", [1, 3, 4, 6, 7, 8, 12])
def test_constants_read_first_and_leave_the_next_record(n) -> None:
    from esolangs.languages.hot.interpreter import _Machine

    rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
    for bit in "01":
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Hot", bit * (1 << n), **options)
            if not options:
                assert len(program) == 4 * n + 3
            for row in rows:
                io = ReadFirstIO(format(row, f"0{n}b") + "Q", expected=n)
                machine = _Machine(program, io)
                steps = 0
                while not machine.halted and steps <= 4 * n + 3:
                    machine.step()
                    steps += 1
                assert machine.halted
                assert steps == 4 * n + 3
                assert machine.pending is None
                assert io.getvalue() == bit
                assert io.reads == n
                assert io.input_char() == ord("Q")


def test_three_input_corpus_size() -> None:
    _check_majority()
    assert (
        sum(len(esolangs.generate("Hot", format(value, "08b"))) for value in range(256))
        == 98234
    )


def _check_majority() -> None:
    from esolangs.languages.hot.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    for n, size in ((2, 253), (3, 353), (7, 1313), (8, 1999)):
        table = "".join(str(int(2 * row.bit_count() > n)) for row in range(1 << n))
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Hot", table, **options)
            if not options:
                assert len(program) == size
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}" + "Q")
                machine = _Machine(program, io)
                while not machine.halted:
                    machine.step()
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert io.past_end == 0
                assert machine.pending is None
                assert io.input_char() == ord("Q")
