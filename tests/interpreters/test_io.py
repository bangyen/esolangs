"""Tests for the shared interpreter I/O helpers."""

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO, ScriptedIO


def test_input_num() -> None:
    """Parse one whitespace-delimited integer."""
    with patch("builtins.input", return_value="42"):
        assert IO().input_num() == 42


def test_input_char() -> None:
    """Return the next Unicode character code."""
    with patch("builtins.input", return_value="X"):
        assert IO().input_char() == ord("X")


def test_input_char_on_an_empty_line() -> None:
    """Interactive input supplies the newline that ended an empty line."""
    with patch("builtins.input", return_value=""):
        assert IO().input_char() == 10


def test_interactive_character_reads_preserve_the_complete_line() -> None:
    for text, expected in [("", [10]), ("a", [97, 10]), ("xyz", [120, 121, 122, 10])]:
        source = IO()
        with patch("builtins.input", return_value=text) as reader:
            assert [source.input_char() for _ in expected] == expected
            assert reader.call_count == 1


def test_input_char_empty_line_is_not_end_of_input() -> None:
    """A supplied newline is a character; only exhaustion raises EOFError."""
    import pytest

    io_obj = ScriptedIO("\n")
    assert io_obj.input_char() == 10
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


def test_scripted_io_position_counts_characters_consumed() -> None:
    """The cursor counts characters consumed, including line separators."""
    io_obj = ScriptedIO("a\nb")
    assert io_obj.position() == 0
    io_obj.input_str()
    assert io_obj.position() == 2
    io_obj.input_str()
    assert io_obj.position() == 3


def test_character_number_and_line_reads_share_one_cursor() -> None:
    source = ScriptedIO("ab 42\ntail\n")
    assert source.input_char() == ord("a")
    assert source.input_char() == ord("b")
    assert source.input_num() == 42
    assert source.input_char() == 10
    assert source.input_str() == "tail"
    assert source.position() == 11


def test_character_read_does_not_discard_line_remainder() -> None:
    source = ScriptedIO("hello\nworld")
    assert source.input_char() == ord("h")
    assert source.input_str() == "ello"
    assert source.input_char() == ord("w")
    assert source.input_str() == "orld"


def test_interactive_character_reads_preserve_remaining_text() -> None:
    source = IO()
    with patch("builtins.input", side_effect=["ab", "cd"]):
        assert source.input_char() == ord("a")
        assert source.input_str() == "b"
        assert source.input_char() == ord("c")
        assert source.input_char() == ord("d")
        assert source.input_char() == 10


def test_integer_tokens_preserve_delimiters_and_support_signs() -> None:
    source = ScriptedIO("  -42 +7")
    assert source.input_num() == -42
    assert source.input_char() == ord(" ")
    assert source.input_num() == 7
    import pytest

    with pytest.raises(EOFError):
        source.input_num()


def test_bit_reads_ignore_whitespace_but_reject_other_characters() -> None:
    import pytest

    source = ScriptedIO(" \n01x")
    assert source.input_bit() == 0
    assert source.input_bit() == 1
    with pytest.raises(ValueError, match="input must be a bit"):
        source.input_bit()


def test_all_reads_preserve_newlines_and_remaining_characters() -> None:
    source = ScriptedIO("ab\ncd\n")
    assert source.input_char() == ord("a")
    assert source.input_all() == "b\ncd\n"
    assert source.input_all() == ""
    assert source.position() == 6


def test_interactive_all_reads_end_at_eof() -> None:
    with patch("builtins.input", side_effect=["ab", "", EOFError]):
        assert IO().input_all() == "ab\n\n"


def test_interactive_integer_tokens_share_buffered_characters() -> None:
    source = IO()
    with patch("builtins.input", side_effect=[" 42 -7", "tail"]):
        assert source.input_num() == 42
        assert source.input_char() == ord(" ")
        assert source.input_num() == -7
        assert source.input_str() == ""
        assert source.input_str() == "tail"


def test_mixed_read_exhaustion_reports_character_offset() -> None:
    import pickle

    import pytest

    from esolangs.exceptions import InputExhaustedError

    source = ScriptedIO("ab\r\nc")
    assert source.input_char() == ord("a")
    assert source.input_str() == "b"
    assert source.input_str() == "c"
    with pytest.raises(InputExhaustedError) as error:
        source.input_str()
    copied = pickle.loads(pickle.dumps(error.value))
    assert (copied.reads, copied.supplied, copied.unit) == (5, 5, "character")
    assert source.past_end == 1


@pytest.mark.parametrize("separator", ["\r", "\v", "\f", "\x85", "\u2028", "\u2029"])
def test_line_exhaustion_counts_only_actual_line_delimiters(separator: str) -> None:
    from esolangs.exceptions import InputExhaustedError

    source = ScriptedIO(f"a{separator}b\nend")
    assert source.supplied == 2
    assert source.input_str() == f"a{separator}b"
    assert source.input_str() == "end"
    with pytest.raises(InputExhaustedError) as error:
        source.input_str()
    assert (error.value.reads, error.value.supplied, error.value.unit) == (2, 2, "line")
