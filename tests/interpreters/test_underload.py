"""Underload stack and program-splicing semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.underload import _Machine, run


def _run(source: str) -> str:
    io = ScriptedIO("")
    run(source, io)
    return io.getvalue()


def test_push_output_and_nested_elements() -> None:
    assert _run("(Hello, world!)S") == "Hello, world!"
    assert _run("((x))S") == "(x)"


def test_stack_commands() -> None:
    assert _run("(a)(b)~SS") == "ab"
    assert _run("(a):SS") == "aa"
    assert _run("(a)(b)*S") == "ab"
    assert _run("(a)aS") == "(a)"
    assert _run("(discard)!()S") == ""


def test_evaluation_splices_the_program_next() -> None:
    assert _run("((yes)S)^((no)S)^") == "yesno"


def test_infinite_loop_has_a_repeating_machine_state_shape() -> None:
    machine = _Machine("(:^):^", ScriptedIO(""))
    for _ in range(12):
        machine.step()
    assert not machine.halted
    assert machine.stack


def test_halted_step_is_a_noop() -> None:
    machine = _Machine("", ScriptedIO(""))
    before = machine.snapshot()
    machine.step()
    assert machine.snapshot() == before


@pytest.mark.parametrize("source", ["!", "~", "*", "^", "S", ")", "(", "x"])
def test_invalid_programs_and_underflow_are_errors(source: str) -> None:
    with pytest.raises(HaltError):
        _run(source)
