"""Unit tests for the Circlefuck interpreter."""

from tests.interpreters.contract import CycleContract, SnapshotContract


def _machine(code: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.circlefuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes. ``><`` orbits the pointer forever; ``+.@`` halts."""

    machine = staticmethod(_machine)
    stepping_program = "><"
    halting_program = "+.@"
    looping_program = "><"
