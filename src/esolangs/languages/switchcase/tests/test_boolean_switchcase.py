"""Tests for the SwitchCase Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("SwitchCase", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("SwitchCase", bits)
        got = esolangs.run("SwitchCase", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("SwitchCase", got) == table[row], (table, row)


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
