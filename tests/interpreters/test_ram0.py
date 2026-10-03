"""RAM0's shared VM contracts."""

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.ram0 import _Machine
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)


def _machine(code: object) -> object:
    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    machine = staticmethod(_machine)
    stepping_program = "A"
    halting_program = "ZA"
    looping_program = "Z1"
    state_views = ("ind", "z", "n", "ip", "memory")
    viewing_program = "A N S"
