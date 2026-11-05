"""Tests for the Nandypants Boolean generator."""

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
        _check_forward()
    assert_every_row("Nandypants", table)


def _check_constants() -> None:
    from esolangs.languages.nandypants.interpreter import _Machine
    from esolangs.languages.nandypants.proof_formulas import workspace
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            commands = 8 * n + 11 + 2 * int(bit)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Nandypants", bit * (1 << n), **options)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Nandypants", list(map(int, f"{row:0{n}b}"))
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
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    peak = max(peak, written.bits)
                    assert written.bits == workspace(n, program)
                    assert machine.state.remaining == 0
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Nandypants", f"{v:08b}")) for v in range(256))
        == 25214
    )


def _check_forward() -> None:
    from esolangs.languages.nandypants.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO

    jumped = False
    for table in ("1101001101101101", "00110110", "00011110"):
        n = len(table).bit_length() - 1
        program = esolangs.generate("Nandypants", table)
        for row in range(len(table)):
            io = ScriptedIO(f"{row:0{n}b}" + "7")
            machine = _Machine(program, io)
            steps = 0
            while not machine.halted:
                before = machine.ip
                if machine.program.tokens[before] == "\\":
                    assert io.reads == n
                    assert machine.state.remaining == 0
                machine.step()
                assert machine.ip > before
                jumped |= machine.ip != before + 1
                steps += 1
                assert steps <= 12 * n + 18
            assert io.getvalue() == table[row]
            assert io.input_char() == ord("7")
    assert jumped
