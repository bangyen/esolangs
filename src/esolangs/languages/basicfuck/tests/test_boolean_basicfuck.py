"""Tests for the Basicfuck Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize(
    "table",
    [
        *TABLES,
        "00010111",
        "01101001",
        "11101000",
        # Shared blocks: parity and a repeated-block table, both flag-dispatched.
        "0110100110010110",
        "1011010001001011",
        "01101001" * 4,
    ],
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Basicfuck", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Basicfuck", bits)
        got = esolangs.run("Basicfuck", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Basicfuck", got) == table[row], (table, row)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    from esolangs.languages.basicfuck.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            commands = n + 2
            workspace = 12 + (n + 2).bit_length() + n.bit_length()
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Basicfuck", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 8 * n + 48
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Basicfuck", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "Q")
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps <= commands
                    assert steps == commands
                    assert written.bits == workspace
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Basicfuck", format(v, "08b"))) for v in range(256))
        == 39327
    )
