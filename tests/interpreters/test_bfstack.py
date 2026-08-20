"""Unit tests for the BFStack interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.bfstack import run


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBFStack:
    def test_push_and_output(self) -> None:
        assert run_and_capture(">+.") == "\x01"

    def test_increment_twice(self) -> None:
        assert run_and_capture(">++.") == "\x02"

    def test_pop(self) -> None:
        """< pops the top of the stack."""
        assert run_and_capture(">+>+<.") == "\x01"

    def test_input(self) -> None:
        """, pushes ASCII input onto the stack."""
        assert run_and_capture(">,.", inputs=["Z"]) == "Z"

    def test_loop(self) -> None:
        """A loop that zeroes its cell executes exactly once."""
        assert run_and_capture(">+[>+<-]>+.") == "\x01"

    def test_loop_skipped_when_zero(self) -> None:
        """[ jumps past its matching ] when the top is zero."""
        assert run_and_capture(">[>]") == ""

    def test_loop_skip_nested(self) -> None:
        """A skipped loop with nested [ brackets counts both."""
        assert run_and_capture(">[[-]]") == ""

    def test_loop_skip_unmatched(self) -> None:
        """A skipped [ with no closing ] is a malformed program."""
        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture(">[")

    def test_output_on_empty_stack_raises(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture(".")

    def test_loop_on_empty_stack_raises(self) -> None:
        """[ on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("[")

    def test_unmatched_closing_bracket_raises(self) -> None:
        """] with no matching [ is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture(">]")


class TestStepMachine:
    def test_step_tracks_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+.", ScriptedIO())
        assert (machine.ind, machine.stk) == (0, [])
        machine.step()  # > pushes 0
        assert machine.stk == [0]
        machine.step()  # + increments the top
        assert machine.stk == [1]
        machine.step()  # . prints it
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 3

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">,", ScriptedIO("A\nB"))
        before = machine.snapshot()
        machine.step()  # > pushes 0
        machine.step()  # , reads the first input byte
        assert machine.snapshot() != before
        assert machine.io.position() == 1

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(">+.", ScriptedIO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        """A [ loop whose top never zeroes spins forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(">+[]", ScriptedIO())) is False
