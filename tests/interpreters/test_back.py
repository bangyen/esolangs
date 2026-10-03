"""Unit tests for the Back interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.back import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBack:
    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashed on.

        The message is matched whole, and with its casing: ``match="empty"``
        is a substring search, so the wording could drift to anything still
        containing the word and no test would say so.
        """

        message = "Back program cannot be empty"
        with raises_message(ValueError, message):
            run_and_capture(["\n"])
        with raises_message(ValueError, message):
            run_and_capture(["   ", "\t"])


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.back import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["-*"]
    halting_program: ClassVar[list[str]] = ["-*"]
    looping_program: ClassVar[list[str]] = ["-"]
