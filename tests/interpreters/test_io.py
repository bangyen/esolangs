"""Tests for the shared interpreter I/O helpers."""

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO, ScriptedIO


def test_input_num() -> None:
    """``input_num`` parses a whole line as an integer."""
    with patch("builtins.input", return_value="42"):
        assert IO().input_num() == 42


def test_input_char() -> None:
    """``input_char`` returns the first character as a byte value."""
    with patch("builtins.input", return_value="X"):
        assert IO().input_char() == ord("X")


def test_input_char_on_an_empty_line() -> None:
    """An empty line is one ended immediately: the character is its newline."""
    with patch("builtins.input", return_value=""):
        assert IO().input_char() == ord("\n")


def test_input_char_empty_line_is_not_end_of_input() -> None:
    """A blank line still feeds a character; only exhaustion is EOF."""
    import pytest

    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == ord("\n")
    with pytest.raises(EOFError):
        io_obj.input_char()


def test_scripted_io_feeds_string_and_captures() -> None:
    """``ScriptedIO`` reads from a string and captures all output."""
    io_obj = ScriptedIO("Hello\nWorld")
    assert io_obj.input_str() == "Hello"
    assert io_obj.input_str() == "World"
    io_obj.print_str("out\n")
    io_obj.print_str("more")
    assert io_obj.getvalue() == "out\nmore"


def test_io_print_value() -> None:
    """``print_value`` writes any value like ``print(value, end="")``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        IO().print_value(json.dumps({"k": 1}))
    assert buffer.getvalue() == '{"k": 1}'
