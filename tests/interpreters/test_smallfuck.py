"""Smallfuck fixed-tape semantics."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.smallfuck import _Machine, run


def _run(source: str) -> str:
    io = ScriptedIO("")
    run(source, io)
    return io.getvalue()


def test_flip_move_loop_and_final_tape() -> None:
    machine = _Machine("*>*[*]", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.memory == [1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize("source", ["<*", ">>"])
def test_crossing_a_tape_end_halts(source: str) -> None:
    assert _run(source) == "0"


def test_noncommands_are_ignored_but_take_tape_cells() -> None:
    machine = _Machine("*x", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.memory == [1, 0]


def test_halted_step_dumps_once() -> None:
    io = ScriptedIO("")
    machine = _Machine(">>*", io)
    machine.step()
    machine.step()
    machine.step()
    machine.step()
    assert io.getvalue() == "1"


def test_machine_exposes_pointer_and_tape() -> None:
    machine = _Machine(">*", ScriptedIO(""))
    machine.step()
    machine.step()
    assert (machine.ptr, machine.tape) == (1, (0, 1))


@pytest.mark.parametrize("source", ["[", "]"])
def test_unbalanced_loops_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _run(source)
