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
        """A skipped [ with no closing ] halts cleanly."""
        assert run_and_capture(">[") == ""

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
