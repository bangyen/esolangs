"""Tests for the Chicken Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    n = len(table).bit_length() - 1
    program = esolangs.generate("Chicken", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Chicken", bits)
        got = esolangs.run("Chicken", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Chicken", got) == table[row], (table, row)


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
                program = esolangs.generate("Chicken", bit * (1 << n), **options)
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
        sum(len(esolangs.generate("Chicken", f"{v:08b}")) for v in range(256)) == 305139
    )
