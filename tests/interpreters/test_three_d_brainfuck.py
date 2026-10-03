"""Unit tests for the 3D Brainfuck interpreter."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine
from tests.interpreters.contract import CycleContract, SnapshotContract


def _machine(code: object) -> object:

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+."
    halting_program = "+."
    looping_program = "+[]"
