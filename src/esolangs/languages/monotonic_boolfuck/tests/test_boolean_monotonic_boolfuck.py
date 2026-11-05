"""Tests for the Monotonic Boolfuck Boolean generator."""

import pytest

from esolangs import compat
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_native_rows
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.monotonic_boolfuck.interpreter import run

    program = compat.generate("Monotonic Boolfuck", table)
    assert_native_rows("Monotonic Boolfuck", table, program, run, sentinel="Q")


def _check_constants() -> None:
    from esolangs.languages.monotonic_boolfuck.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            commands = 20 if n == 1 else 14 * n + 9 + 2 * int(bit)
            length = 20 if n == 1 else 3 * n + 19 + 2 * int(bit)
            bound = (
                13 + (length - 1).bit_length() + n.bit_length()
                if n == 1
                else 12
                + (length - 1).bit_length()
                + 2 * n.bit_length()
                + sum(i.bit_length() for i in range(1, n))
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = compat.generate(
                    "Monotonic Boolfuck", bit * (1 << n), **options
                )
                assert len("".join(program.split())) == length
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= commands
                    assert (steps, written.bits) == (commands, bound)
                    assert io.getvalue() == bit
                    assert (machine.state.remaining, io.past_end) == (0, 0)
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(compat.generate("Monotonic Boolfuck", f"{v:08b}")) for v in range(256))
        == 36526
    )
