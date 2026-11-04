"""Tests for the lol waht i cant edit talk pages Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import run

    n = len(table).bit_length() - 1

    program = esolangs.generate("lol waht i cant edit talk pages", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("lol waht i cant edit talk pages", bits)
        io = ReadFirstIO(stdin + "Q", expected=n)
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_token() == "Q"
        # The answer as the contract reads it, not the raw output.
        assert (
            esolangs.read_answer("lol waht i cant edit talk pages", got) == table[row]
        ), (table, row)


@pytest.mark.medium
def test_constant_audit_reads_before_output_and_leaves_sentinel() -> None:
    from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "lol waht i cant edit talk pages", bit * (1 << n), **options
                )
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
    assert (
        sum(
            len(esolangs.generate("lol waht i cant edit talk pages", format(v, "08b")))
            for v in range(256)
        )
        == 110463
    )
