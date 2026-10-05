"""Shared Jaune machine contracts."""

import pytest

from esolangs.interpreters.tape_based.jaune import run
from tests.interpreters.contract import SnapshotContract
from tests.interpreters.runner import run_program


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract):
    machine = staticmethod(_machine)
    stepping_program = "6+5+^."


def test_bare_operator_hint_puts_the_number_first() -> None:
    """The count precedes its command (``9:``), whatever the hint said."""
    with pytest.raises(ValueError, match="requires a number") as caught:
        run_program(run, ":")
    assert any(
        "immediately before the command" in note for note in caught.value.__notes__
    )
