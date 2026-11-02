"""Tests for the Monotonic Boolfuck Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
    from esolangs.languages.monotonic_boolfuck.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    n = len(table).bit_length() - 1

    class ReadFirstIO(ScriptedIO):
        def _write(self, value: object) -> None:
            assert self.reads == n
            super()._write(value)

    program = esolangs.generate("Monotonic Boolfuck", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Monotonic Boolfuck", bits)
        io = ReadFirstIO(stdin + "Q")
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_char() == ord("Q")
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Monotonic Boolfuck", got) == table[row], (
            table,
            row,
        )


def _check_constants() -> None:
    from esolangs.languages.monotonic_boolfuck.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

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
                program = esolangs.generate(
                    "Monotonic Boolfuck", bit * (1 << n), **options
                )
                assert len("".join(program.split())) == length
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}" + "Q")
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= commands
                    assert steps == commands
                    assert written.bits == bound
                    assert io.getvalue() == bit
                    assert machine.state.remaining == 0
                    assert io.past_end == 0
                    assert io.input_char() == ord("Q")
    assert (
        sum(
            len(esolangs.generate("Monotonic Boolfuck", f"{v:08b}")) for v in range(256)
        )
        == 36526
    )
