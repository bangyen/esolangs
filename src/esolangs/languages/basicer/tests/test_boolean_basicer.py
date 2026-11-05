"""Tests for the BASICER Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    assert_every_row("BASICER", table)


def _check_constants() -> None:
    from esolangs.languages.basicer.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("BASICER", bit * (1 << n), **options)
                expected = [f"{i} GOTO {i + 1} {i + 1}" for i in range(1, n + 1)] + [
                    f"{n + 1} PRINT {bit}"
                ]
                assert program.splitlines() == expected
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "BASICER", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= n + 1
                    assert steps == n + 1
                    assert io.getvalue() == bit + "\n"
                    assert written.bits == (n + 1).bit_length() + (2 * n).bit_length()
                    assert io.input_str() == "Q"
    assert (
        sum(len(esolangs.generate("BASICER", f"{v:08b}")) for v in range(256)) == 23222
    )
