"""Unit tests for the Suffolk interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.tape_based.suffolk import run


def run_and_capture(code: str, limit: int = 1) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, limit)
    return buffer.getvalue()


class TestSuffolk:
    def test_count_and_output(self) -> None:
        """66 increments of the counter then a print yields 'A'."""
        assert run_and_capture("!" * 66 + "<.") == "A"

    def test_other_value(self) -> None:
        assert run_and_capture("!" * 70 + "<.") == "E"

    def test_output_requires_accumulator(self) -> None:
        """A . with no accumulated value prints nothing."""
        assert run_and_capture("!.") == ""

    def test_no_halt_without_instruction(self) -> None:
        """Programs without a halt run until the loop limit is reached."""
        assert run_and_capture("!!!!") == ""

    def test_move_right(self) -> None:
        """> moves the pointer to a new tape cell."""
        assert run_and_capture("!!!!!!!!>!><<<<<<<<<.!") == "@"

    def test_input(self) -> None:
        """, reads input into the accumulator."""
        buffer = io.StringIO()
        with patch("builtins.input", return_value="B"), redirect_stdout(buffer):
            run(",.", 1)
        assert buffer.getvalue() == "A"
