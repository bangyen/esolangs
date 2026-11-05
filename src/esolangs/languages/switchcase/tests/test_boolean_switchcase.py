"""Tests for the SwitchCase Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert_every_row("SwitchCase", table)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    from esolangs.languages.switchcase.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            commands = n + 6 + int(bit)
            workspace = 25 + (n + 1).bit_length() + n.bit_length()
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("SwitchCase", bit * (1 << n), **options)
                if not options:
                    assert len(program) == n + 15 + 2 * int(bit)
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "SwitchCase", list(map(int, f"{row:0{n}b}"))
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
        sum(len(esolangs.generate("SwitchCase", format(v, "08b"))) for v in range(256))
        == 31572
    )

    _check_shared_residuals()


def _check_shared_residuals() -> None:
    """Every small table preserves IO; parity reaches the command bound."""
    from esolangs.languages.switchcase.interpreter import _Machine
    from esolangs.languages.switchcase.proof_formulas import execution, workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    summed = 0
    for value in range(256):
        table = f"{value:08b}"
        program = esolangs.generate("SwitchCase", table)
        for row in range(8):
            io = ScriptedIO(f"{row:03b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(machine.snapshot())
                steps += 1
                if io.getvalue():
                    assert io.reads == 3
            summed += steps
            assert io.getvalue() == table[row]
            assert io.input_char() == ord("Q")
            assert steps <= execution(3, program)
            assert written.bits <= workspace(3, program)
    assert summed == 48400
    for n in range(1, 9):
        table = "".join(str(row.bit_count() % 2) for row in range(1 << n))
        program = esolangs.generate("SwitchCase", table)
        # Every parity path has n tests; a one prints after the increment.
        io = ScriptedIO(f"{1:0{n}b}")
        machine = _Machine(program, io)
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        assert steps == execution(n, program)
        # Buffer cases, two residuals per lower depth, root, two leaves, end.
        assert len(machine.cases) == 3 * n + 3
