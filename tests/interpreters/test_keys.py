"""Unit tests for the Keys interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.other.keys import run


def run_and_capture(code) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code)
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
