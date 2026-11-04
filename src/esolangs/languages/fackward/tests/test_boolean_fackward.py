"""Tests for the Fackward Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.fackward.interpreter import run

    n = len(table).bit_length() - 1

    program = esolangs.generate("Fackward", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Fackward", bits)
        io = ReadFirstIO(stdin + "Q", expected=n)
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_char() == ord("Q")
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Fackward", got) == table[row], (table, row)


def _check_constants() -> None:
    import esolangs
    from esolangs.languages.fackward.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Fackward", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 7 * n + 6
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Fackward", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 2000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    if not options:
                        assert steps == 8 * n + 4
