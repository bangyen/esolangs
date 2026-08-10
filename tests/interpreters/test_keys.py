"""Unit tests for the Keys interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.keys import run


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestKeys:
    def test_accept_identical_keys(self) -> None:
        assert run_and_capture(["-", "-"]) == "Accept.\n"

    def test_reject_different_keys(self) -> None:
        assert run_and_capture(["-", "_"]) == "Reject.\n"

    def test_reject_non_key_characters(self) -> None:
        """Characters other than \\ / - _ are invalid."""
        assert run_and_capture(["abc", "abc"]) == "Reject.\n"

    def test_reject_forbidden_pattern(self) -> None:
        """Adjacent -_ or _- transitions are forbidden."""
        assert run_and_capture(["_-", "_-"]) == "Reject.\n"

    def test_fewer_than_two_lines_rejected(self) -> None:
        """A program with fewer than two lines is malformed."""
        with pytest.raises(ValueError, match="at least two lines"):
            run(["-"], IO())

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed."""
        with pytest.raises(ValueError, match="at least two lines"):
            run([], IO())
