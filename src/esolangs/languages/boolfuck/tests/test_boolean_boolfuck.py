"""Boolfuck stays within its execution clause."""

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_saved_rows,
    constant_programs,
    three_input_corpus_size,
)


@pytest.mark.parametrize("table", ["01101001", "00000000"])
def test_program_stays_within_the_command_bound(table) -> None:
    from esolangs.languages.boolfuck.generator import _command_bound, boolfuck

    if table == "01101001":
        _check_zero_guard()
    if table == "00000000":
        _check_constants()
    program, bound = boolfuck(table), _command_bound(3)
    for row, expected in enumerate(table):
        machine = make_vm("Boolfuck", program, stdin=f"{row:03b}")
        commands = 0
        while not machine.halted and commands <= bound:
            machine.step()
            commands += 1
        assert machine.halted
        assert commands <= bound
        assert esolangs.read_answer("Boolfuck", machine.output) == expected


def _check_constants() -> None:
    from esolangs.languages.boolfuck.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Boolfuck")["workspace"].formula

    language = esolangs.Language("Boolfuck")
    for witness in construction_boundaries(language.name)[
        "constant_batched_read_cutoff"
    ]:
        table = witness.table()
        artifact = language.generate(table)
        assert ("[,,,,,,,,>]" in artifact.source) == (witness.arity == 3)
        assert_saved_rows(language, artifact, table, range(len(table)))

    for n, bit, _options, program in constant_programs("Boolfuck", range(1, 13)):
        commands = (14 * n + 11 if n >= 3 else 8 * n + 10) + 2 * int(bit)
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                command = machine.code[machine.state.pc]
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += int(command in "><+[],;")
                assert steps <= commands
            assert (steps, io.getvalue()) == (commands, bit)
            assert written.bits == workspace(n, program)
            assert (machine.state.remaining, io.past_end) == (0, 0)
            assert io.input_char() == ord("Q")
    assert three_input_corpus_size("Boolfuck") == 30652


def _check_zero_guard() -> None:
    from esolangs.languages.boolfuck.generator import _boolfuck_tree, _command_bound
    from esolangs.languages.boolfuck.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Boolfuck")["workspace"].formula

    fixtures = (
        "00000001",
        "01101011",
        "".join("00110110"[(r >> 1) & 7] for r in range(32)),
    )
    dead_input_survived = False
    for table in fixtures:
        n = len(table).bit_length() - 1
        program = _boolfuck_tree(table)
        for row, expected in enumerate(table):
            io = ScriptedIO(f"{row:0{n}b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            commands = prints = 0
            while not machine.halted:
                prints += machine.code[machine.state.pc] == ";"
                machine.step()
                written.sample(machine.workspace_snapshot())
                commands += 1
                assert commands <= _command_bound(n)
            assert (io.getvalue(), prints) == (expected, 8)
            assert (io.reads, machine.state.remaining, io.past_end) == (n, 0, 0)
            assert io.input_char() == ord("Q")
            assert written.bits <= workspace(n, program)
            assert 1 not in machine.ones
            if table == "00000001" and row == 1:
                dead_input_survived = 4 in machine.ones
    assert dead_input_survived
