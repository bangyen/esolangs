"""Unit tests for the Minifuck interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.minifuck import run


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestMinifuck:
    def test_cat_program(self) -> None:
        """The canonical cat program echoes its input."""
        assert run_and_capture("<[<.[<.", inputs=["A"]) == "A"
        assert run_and_capture("<[<.[<.", inputs=["B"]) == "B"

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

    def test_comment_characters_ignored(self) -> None:
        """Non-command characters are ignored."""
        assert run_and_capture("abc", inputs=["A"]) == ""


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".", ScriptedIO())
        assert (machine.ind, machine.ptr) == (0, 0)
        machine.step()  # . advances, flips the second cell, prints the byte
        assert machine.io.getvalue() == "@"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert hash(_Machine(".", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # the tape never rewinds, so every Minifuck program halts
        assert run_until_halt_or_cycle(_Machine(".", ScriptedIO())) is True
