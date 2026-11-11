"""Tests for the SwitchCase Boolean generator."""

import pytest

import esolangs
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_every_row,
    constant_programs,
    three_input_corpus_size,
)
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        assert_analysis_complement("SwitchCase", "reduced_diagram")
    assert_every_row("SwitchCase", table)


@pytest.mark.medium
def test_constant_reads_precede_output_and_preserve_the_next_character() -> None:
    from esolangs.languages.switchcase.interpreter import _Machine

    for n, bit, options, program in constant_programs("SwitchCase", range(1, 13)):
        commands = n + 6 + int(bit)
        workspace = 25 + (n + 1).bit_length() + n.bit_length()
        if not options:
            assert len(program) == n + 15 + 2 * int(bit)
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("SwitchCase", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, commands, written=written)
            assert steps == commands
            assert written.bits == workspace
            assert io.getvalue() == bit
            assert io.input_char() == ord("Q")
    assert three_input_corpus_size("SwitchCase") == 31572

    _check_shared_residuals()


def _check_shared_residuals() -> None:
    """Every small table preserves IO; parity reaches the command bound."""
    from esolangs.languages.switchcase.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("SwitchCase")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    summed = 0
    for value in range(256):
        table = f"{value:08b}"
        program = esolangs.generate("SwitchCase", table).source
        for row in range(8):
            io = ScriptedIO(f"{row:03b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(machine.workspace_snapshot())
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
        program = esolangs.generate("SwitchCase", table).source
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
