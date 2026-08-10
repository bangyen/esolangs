"""Unit tests for the Clockwise interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.clockwise import run


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestClockwise:
    def test_output_character(self) -> None:
        """Pushing bits 1000001 outputs 'A'."""
        code = ["+;S;S;S;S;S;+;R", "R             R"]
        assert run_and_capture(code) == "A"

    def test_truth_machine_zero(self) -> None:
        """Truth-machine with input 0 halts after outputting '0'."""
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run_and_capture([])

    def test_unclosed_ring_rejected(self) -> None:
        """A pointer that walks off the ring is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="not closed"):
            run_and_capture(["+;S"])
