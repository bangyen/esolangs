"""Shared Dimensional machine contracts."""

from tests.interpreters.contract import SnapshotContract


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.dimensional import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program = "+" * 3 + "."
