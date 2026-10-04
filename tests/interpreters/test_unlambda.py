"""Execution tests for the Unlambda interpreter."""

import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.unlambda import (
    _advance,
    _App,
    _Machine,
    _parse,
    run,
)
from tests.interpreters.runner import run_program


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("", "cannot be empty"),
        ("`i", "missing one of its two terms"),
        ("ii", "spells a second one"),
        ("`i.", "has no character after it"),
        ("z", "not an Unlambda command"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_the_parser_is_iterative_over_a_long_chain() -> None:
    """A deep application chain must not exhaust the recursion limit."""
    depth = 5000
    term = _parse("`" * depth + "i" * (depth + 1))
    assert isinstance(term, _App)


def test_stepping_a_finished_machine_changes_nothing() -> None:
    machine = _Machine("`.Ai", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.state[3] is True
    assert _advance(machine.state) == (machine.state, None)
