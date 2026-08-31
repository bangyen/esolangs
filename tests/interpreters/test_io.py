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


def test_io_print_char_writes_and_tracks_the_line() -> None:
    """A printed character leaves the cursor mid-line, so a prompt breaks first."""
    io_obj = ScriptedIO("v")
    io_obj.print_char("a")
    assert io_obj.getvalue() == "a"
    with patch.object(ScriptedIO, "_read", autospec=True) as read:
        read.return_value = "v"
        io_obj.input_str()
    assert read.call_args.args[1].startswith("\n")


def test_io_print_char_of_a_newline_ends_the_line() -> None:
    """A newline character leaves the cursor at a line start, so no break."""
    io_obj = ScriptedIO("v")
    io_obj.print_char("\n")
    assert io_obj.getvalue() == "\n"
    with patch.object(ScriptedIO, "_read", autospec=True) as read:
        read.return_value = "v"
        io_obj.input_str()
    assert not read.call_args.args[1].startswith("\n")


def test_io_print_char_of_the_empty_string_leaves_the_flag() -> None:
    """Writing nothing cannot move the cursor, so the pending break survives."""
    io_obj = ScriptedIO("v")
    io_obj.print_char("\n")
    io_obj.print_char("")
    with patch.object(ScriptedIO, "_read", autospec=True) as read:
        read.return_value = "v"
        io_obj.input_str()
    assert not read.call_args.args[1].startswith("\n")


def test_io_print_num_writes_decimal_and_tracks_the_line() -> None:
    """``print_num`` writes the decimal form and leaves the cursor mid-line."""
    io_obj = ScriptedIO("v")
    io_obj.print_num(255)
    assert io_obj.getvalue() == "255"
    with patch.object(ScriptedIO, "_read", autospec=True) as read:
        read.return_value = "v"
        io_obj.input_str()
    assert read.call_args.args[1].startswith("\n")


def test_base_io_reports_no_input_cursor() -> None:
    """An interactive source has no cursor to report."""
    io_obj = IO()
    assert io_obj.position() == 0
    with patch("builtins.input", return_value="x"):
        io_obj.input_str()
    assert io_obj.position() == 0


def test_scripted_io_position_counts_lines_consumed() -> None:
    """``ScriptedIO`` reports how many input lines it has handed out."""
    io_obj = ScriptedIO("a\nb")
    assert io_obj.position() == 0
    io_obj.input_str()
    assert io_obj.position() == 1
    io_obj.input_str()
    assert io_obj.position() == 2
