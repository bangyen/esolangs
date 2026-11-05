"""Tests for the Qrain Boolean generator."""

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
    assert_every_row("Qrain", table)


def _check_constants() -> None:
    from esolangs.languages.qrain.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Qrain", bit * (1 << n), **options).source
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Qrain", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q", expected=n)
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= n + 10 - 2 * int(bit)
                    assert steps == n + 10 - 2 * int(bit)
                    assert io.getvalue() == bit
                    length = n + 10 - 2 * int(bit)
                    control = max(
                        (length - 4).bit_length() + 2, length.bit_length() + 1
                    )
                    assert (
                        written.bits
                        == control + 8 * n + 7 - int(bit) - (n == 1) + n.bit_length()
                    )
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Qrain", f"{v:08b}").source) for v in range(256))
        == 34181
    )
