"""Boolfuck stays within its execution clause."""

import pytest


@pytest.mark.parametrize("table", ["01101001", "00000000"])
def test_program_stays_within_the_command_bound(table) -> None:
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.languages.boolfuck.generator import _command_bound, boolfuck

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
