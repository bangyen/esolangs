"""Tests for the Basicfuck Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row

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
    assert_every_row("Basicfuck", table)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    from esolangs.languages.basicfuck.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
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
                    io = ReadFirstIO(stdin + "Q", expected=n)
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
