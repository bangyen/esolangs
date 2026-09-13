"""Tests for the pure Nopstacle interpreter."""

import pytest

from esolangs.interpreters.grid_based.nopstacle import _advance, _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program


def _run(code: str) -> str:
    """Run Nopstacle and capture its necessarily empty output."""
    from esolangs.interpreters.grid_based.nopstacle import run

    return run_program(run, code.splitlines(), "")


class TestContract(SnapshotContract, CycleContract):
    """Shared VM and cycle-detection contracts."""

    machine = staticmethod(lambda code: _Machine(code.splitlines()))
    stepping_program = "  \n##"
    halting_program = " #\n##"
    looping_program = "  \n##"


def test_advance_is_pure() -> None:
    machine = _Machine(["  ", "##"])
    before = machine.state
    after = _advance(before, machine.grid, machine.width, machine.height)
    assert machine.state == before
    assert after != before


def test_boxed_origin_halts_on_repeated_local_state() -> None:
    machine = _Machine([" #", "##"])
    assert run_until_halt_or_cycle(machine)
    assert machine.ip == (0, 0, 2)


def test_open_lane_crosses_copies_forever() -> None:
    machine = _Machine(["  ", "##"])
    assert not run_until_halt_or_cycle(machine)
    assert not machine.halted


def test_ragged_rows_are_padded_with_spaces() -> None:
    machine = _Machine([" ", "##"])
    assert machine.grid == ("  ", "##")


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ([], "Nopstacle program must contain a cell"),
        ([""], "Nopstacle program must contain a cell"),
        (["x"], "Nopstacle cells must be spaces or '#'"),
        (["#"], "Nopstacle's top-left cell must be empty"),
    ],
)
def test_invalid_programs_are_rejected(code: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _Machine(code, ScriptedIO())


def test_run_has_no_output() -> None:
    assert _run(" #\n##") == ""
