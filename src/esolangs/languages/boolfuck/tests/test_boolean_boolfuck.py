"""Boolfuck stays within its execution clause."""

import pytest


@pytest.mark.parametrize("table", ["01101001", "00000000"])
def test_program_stays_within_the_command_bound(table) -> None:
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.languages.boolfuck.generator import _command_bound, boolfuck

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
    import esolangs
    from esolangs.languages.boolfuck.interpreter import _Machine
    from esolangs.languages.boolfuck.proof_formulas import workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            commands = (14 * n + 11 if n >= 3 else 8 * n + 10) + 2 * int(bit)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Boolfuck", bit * (1 << n), **options)
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
                    assert written.bits == workspace(n, program)
                    assert machine.state.remaining == 0
                    assert io.past_end == 0
                    assert io.getvalue() == bit
                    assert io.input_char() == ord("Q")
    assert (
        sum(len(esolangs.generate("Boolfuck", f"{v:08b}")) for v in range(256)) == 33305
    )
