"""Tests for the Chicken Boolean generator."""

import pytest

from esolangs import compat
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    program = compat.generate("Chicken", table)
    # Missing characters are false; arithmetic coercion would produce NaN.
    for prefix in ("", "0", "1"):
        row = int(prefix.ljust(n, "0"), 2)
        assert compat.run("Chicken", program, stdin=prefix, timeout=5) == table[row]
    assert_every_row("Chicken", table, program=program)


def _check_constants() -> None:
    from esolangs.languages.chicken.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.position() == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = compat.generate("Chicken", bit * (1 << n), **options)
                assert program == ("chicken chicken\n\nchicken" if bit == "1" else "\n")
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= 1 + int(bit)
                    assert steps == 1 + int(bit)
                    assert io.getvalue() == bit
                    assert written.bits == 8 * n + 4 + 4 * int(bit)
                    assert io.past_end == 0
    assert (
        sum(len(compat.generate("Chicken", f"{v:08b}")) for v in range(256)) == 305139
    )
