"""Tests for the Balik interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.balik.interpreter import run
from esolangs.runtime.io import ScriptedIO


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _page_loop(before: str, body: str, after: str) -> str:
    """The page's ``abc[def]ghi`` diagram at depth 0."""
    return "\n".join(
        [
            before + "**" + body + "**" + after,
            "   @@   @@",
            "  *       *",
            "  ***   ***",
        ]
    )


def test_increment_wraps_at_three() -> None:
    assert _out("+.+.+.") == "120"


def test_tape_moves_and_input_adds() -> None:
    assert _out(",>,.<.", "2\n1\n") == "12"


def test_page_loop_enters_its_body_on_zero() -> None:
    # The body runs 0 -> 1, 2, 0 and leaves once the cell is 0 again.
    assert _out(_page_loop("   ", "+. ", "   ")) == "120"


def test_page_loop_skips_its_body_on_nonzero() -> None:
    assert _out(_page_loop("+  ", "+. ", ".  ")) == "1"


def test_short_lines_are_padded_not_out_of_bounds() -> None:
    # South from the ``*`` through the empty line's padding to the ``.``;
    # ragged bounds would halt on the empty line and print nothing.
    assert _out("  *\n\n  .") == "0"


def test_turns_are_clockwise() -> None:
    # East turns south onto the ``.``; anticlockwise would leave north.
    assert _out("+*\n .") == "1"


def test_leftmost_move_halts() -> None:
    with pytest.raises(HaltError):
        _out("<")


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown command"):
        _out("+x")
