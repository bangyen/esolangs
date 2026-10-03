"""Shared Jaune machine contracts."""

from tests.interpreters.contract import SnapshotContract


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program = "6+5+^."
