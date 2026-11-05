"""Tests for the CARP Boolean generator."""

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
    assert_every_row("CARP", table)


def _check_constants() -> None:
    from esolangs.languages.carp.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 15):
        for bit in "01":
            commands = n + 1 + int(bit)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("CARP", bit * (1 << n), **options).source
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "CARP", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n", expected=n)
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
                    bound = (
                        15
                        + max(2, (n + int(bit)).bit_length())
                        + (2 * n - 1).bit_length()
                    )
                    assert written.bits <= bound
                    assert io.input_num() == 7
                assert peak == bound
    assert (
        sum(len(esolangs.generate("CARP", f"{v:08b}").source) for v in range(256))
        == 77033
    )
