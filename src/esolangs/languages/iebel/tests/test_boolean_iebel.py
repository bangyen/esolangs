"""Tests for the IEBEL Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    assert_every_row("IEBEL", table)


def _check_constants() -> None:
    from esolangs.languages.iebel.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            commands = n + (1 if n <= 7 else 2)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("IEBEL", bit * (1 << n), **options).source
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "IEBEL", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= commands
                    assert steps == commands
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    peak = max(peak, written.bits)
                    assert written.bits == 266 + commands.bit_length() + n.bit_length()
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("IEBEL", f"{v:08b}").source) for v in range(256))
        == 26774
    )
