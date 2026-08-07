"""Unit tests for the Minifuck interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.tape_based.minifuck import run


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code)
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
