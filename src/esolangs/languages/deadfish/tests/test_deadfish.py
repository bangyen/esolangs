"""Tests for the Deadfish interpreter."""

from esolangs.languages.deadfish.interpreter import _Machine, run
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO, ScriptedIO
from scripts.benchmark import WrittenState
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.interpreters.runner import run_program
from tests.support.workspace_oracle import WorkspaceOracle

#: The wiki's four-line "Hello, world!", whose lines run as one program.
_HELLO = "".join(
    [
        "iiisdsiiiiiiiioiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiooiiio",
        "ddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
        "ddddddddddoddddddddddddo",
        "dddddddddddddddddddddsddoddddddddoiiioddddddoddddddddo",
        "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddo",
    ]
)


class TestDeadfish:
    def test_the_wiki_hello_world_spells_it(self) -> None:
        """Thirteen ``o``s, whose values are the string's ASCII codes."""
        printed = [int(num) for num in run_program(run, _HELLO).split()]
        assert "".join(map(chr, printed)) == "Hello, world!"

    def test_every_program_halts(self) -> None:
        """The position only ever advances, so there is no loop to detect."""
        from esolangs.languages.deadfish.tests.oracle_checks import check_raw_deadfish

        check_raw_deadfish()

        def parts(machine):
            return (machine.code, *machine.state, machine.io.progress())

        for program in ("", "i", _HELLO, "iissso", "h", "xyz", "iio"):
            machine = _Machine(program, ScriptedIO())
            steps = 0
            measured = WrittenState(machine.workspace_snapshot())
            oracle = WorkspaceOracle(machine.workspace_snapshot())
            reference = WorkspaceModel(
                "deadfish-reference-test-v1",
                ("source", "instruction", "accumulator", "stopped", "input_cursor"),
            )
            legacy = WrittenState(WorkspaceSnapshot(reference, parts(machine)))
            while not machine.halted:
                machine.step()
                captured = machine.workspace_snapshot()
                assert captured.parts == parts(machine)
                measured.sample(captured)
                oracle.sample(captured)
                assert measured.bits == oracle.bits
                legacy.sample(WorkspaceSnapshot(reference, parts(machine)))
                assert measured.bits == legacy.bits
                steps += 1
            assert steps <= len(program), program
            if program in ("h", "iio", "iissso"):
                assert measured.bits == {"h": 1, "iio": 4, "iissso": 8}[program]


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "iso"
    state_views = ("ip", "memory", "ind", "value")
    viewing_program = "iso"
