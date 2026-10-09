"""Tests for the Deadfish interpreter."""

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.register_based.deadfish import _Machine, run
from tests.interpreters.contract import SnapshotContract, StateViewContract
from tests.interpreters.runner import run_program

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
        for program in ("", "i", _HELLO, "iissso", "h", "xyz"):
            machine = _Machine(program, ScriptedIO())
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps <= len(program), program


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "iso"
    state_views = ("ip", "memory", "ind", "value")
    viewing_program = "iso"
