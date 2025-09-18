"""
Unit tests for Huf interpreter.

Tests cover all Huf commands, code segment extraction, and example programs.
Huf is a register-based esoteric language that processes code segments enclosed
in #...#@ patterns and uses two registers: num (accumulator) and mul (multiplier).
"""

import io
from contextlib import redirect_stdout

import pytest

from src.esolangs.interpreters.register_based.huf import run


class TestHufCodeExtraction:
    """Test Huf's code segment extraction mechanism."""

    def test_extract_single_segment(self) -> None:
        """Test extraction of a single code segment."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++>@")
        assert f.getvalue() == "\x03"  # 3 increments = ASCII 3

    def test_extract_multiple_segments(self) -> None:
        """Test extraction of multiple code segments."""
        with redirect_stdout(io.StringIO()) as f:
            run("#++>@#+>@")
        assert f.getvalue() == "\x02\x01"  # First segment: 2, Second segment: 1

    def test_ignore_text_outside_segments(self) -> None:
        """Test that text outside #...#@ segments is ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("Hello #++>@ World")
        assert f.getvalue() == "\x02"  # Only the segment content is processed

    def test_empty_segments_ignored(self) -> None:
        """Test that empty segments are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("##@#++>@")
        assert f.getvalue() == "\x02"  # Only non-empty segment is processed

    def test_nested_segments_not_supported(self) -> None:
        """Test that nested #...#@ patterns are not supported."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+#+>@#@")
        # The regex #[^#@]+@ will match the first complete segment only
        assert (
            f.getvalue() == "\x01"
        )  # Only first segment: +, +, > (but only 2 + commands)


class TestHufBasicCommands:
    """Test basic Huf command functionality."""

    def test_reset_command(self) -> None:
        """Test # command resets both registers."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++#+++>@")
        assert f.getvalue() == "\x03"  # Reset clears previous increments

    def test_increment_command(self) -> None:
        """Test + command increments num when mul is 0."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+>@")
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("#+++>@")
        assert f.getvalue() == "\x03"

    def test_output_command(self) -> None:
        """Test > command outputs character and resets num."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++>+++>@")
        assert f.getvalue() == "\x03\x03"  # Two separate outputs

    def test_multiplication_mode_start(self) -> None:
        """Test | command starts multiplication mode."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+|+!>@")
        # num=1, mul=2, ! multiplies num by (2-1) = 1*1 = 1
        assert f.getvalue() == "\x01"

    def test_multiplication_command(self) -> None:
        """Test ! command multiplies num by (mul - 1)."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|++!>@")
        # num=3, mul=1+2=3, num *= (3-1) = 3*2 = 6
        assert f.getvalue() == "\x06"


class TestHufMathematicalOperations:
    """Test Huf's mathematical capabilities."""

    def test_simple_addition(self) -> None:
        """Test simple addition using + commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++++>@")
        assert f.getvalue() == "\x05"

    def test_multiplication_by_zero(self) -> None:
        """Test multiplication by zero (mul = 1)."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|!>@")
        # num=2, mul=1, num *= (1-1) = 2*0 = 0
        assert f.getvalue() == "\x00"

    def test_multiplication_by_one(self) -> None:
        """Test multiplication by one (mul = 2)."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|+!>@")
        # num=3, mul=2, num *= (2-1) = 3*1 = 3
        assert f.getvalue() == "\x03"

    def test_multiplication_by_two(self) -> None:
        """Test multiplication by two (mul = 3)."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|++!>@")
        # num=3, mul=3, num *= (3-1) = 3*2 = 6
        assert f.getvalue() == "\x06"

    def test_complex_calculation(self) -> None:
        """Test a more complex calculation."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|+++!+++>@")
        # num=3, mul=4, num *= (4-1) = 3*3 = 9, then +3 = 12
        assert f.getvalue() == "\x0c"


class TestHufCharacterOutput:
    """Test Huf's character output functionality."""

    def test_ascii_character_output(self) -> None:
        """Test output of various ASCII characters."""
        # Test 'A' (ASCII 65)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 65 + ">@")
        assert f.getvalue() == "A"

        # Test 'H' (ASCII 72)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 72 + ">@")
        assert f.getvalue() == "H"

        # Test newline (ASCII 10)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 10 + ">@")
        assert f.getvalue() == "\n"

    def test_null_character_output(self) -> None:
        """Test output of null character (ASCII 0)."""
        with redirect_stdout(io.StringIO()) as f:
            run("#>@")
        assert f.getvalue() == "\x00"

    def test_high_ascii_values(self) -> None:
        """Test output of high ASCII values."""
        # Test DEL (ASCII 127)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 127 + ">@")
        assert f.getvalue() == "\x7f"

    def test_multiple_character_output(self) -> None:
        """Test output of multiple characters."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++>++++>+++++>@")
        assert f.getvalue() == "\x03\x04\x05"


class TestHufEdgeCases:
    """Test Huf edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("")
        assert f.getvalue() == ""

    def test_no_valid_segments(self) -> None:
        """Test program with no valid #...#@ segments."""
        with redirect_stdout(io.StringIO()) as f:
            run("Hello World! No segments here.")
        assert f.getvalue() == ""

    def test_incomplete_segments(self) -> None:
        """Test program with incomplete segments."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++")  # Missing @
        assert f.getvalue() == ""

        with redirect_stdout(io.StringIO()) as f:
            run("+++@")  # Missing #
        assert f.getvalue() == ""

    def test_whitespace_in_segments(self) -> None:
        """Test that whitespace in segments is processed as commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("# + + + > @")
        # Whitespace characters are processed but don't match any commands
        assert f.getvalue() == "\x03"  # Only the + commands are processed

    def test_unknown_commands_ignored(self) -> None:
        """Test that unknown commands are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+xyz+>@")
        assert f.getvalue() == "\x02"  # Only + commands are processed

    def test_register_overflow_behavior(self) -> None:
        """Test behavior with large register values."""
        # Test with a large number of increments
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 300 + ">@")
        # Python's chr() function accepts values up to 0x10FFFF
        assert f.getvalue() == chr(300)


class TestHufMultiplicationMode:
    """Test Huf's multiplication mode in detail."""

    def test_multiplication_mode_activation(self) -> None:
        """Test that | activates multiplication mode."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+|+!>@")
        # num=1, mul=2, ! multiplies by (2-1)=1
        assert f.getvalue() == "\x01"

    def test_multiplication_mode_deactivation(self) -> None:
        """Test that ! deactivates multiplication mode."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|++!++>@")
        # num=3, mul=3, num *= (3-1) = 3*2 = 6, then +2 = 8
        assert f.getvalue() == "\x08"

    def test_multiple_multiplication_cycles(self) -> None:
        """Test multiple multiplication cycles."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|+!+++|++!>@")
        # First cycle: num=3, mul=2, num *= (2-1) = 3*1 = 3
        # Second cycle: num=6, mul=3, num *= (3-1) = 6*2 = 12
        assert f.getvalue() == "\x0c"

    def test_multiplication_without_increment(self) -> None:
        """Test multiplication without prior increments."""
        with redirect_stdout(io.StringIO()) as f:
            run("#|++!>@")
        # num=0, mul=3, num *= (3-1) = 0*2 = 0
        assert f.getvalue() == "\x00"


class TestHufHelloWorld:
    """Test Hello World program construction in Huf."""

    def test_hello_world_letters(self) -> None:
        """Test generating individual letters of 'Hello'."""
        # Generate 'H' (ASCII 72)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 72 + ">@")
        assert f.getvalue() == "H"

        # Generate 'e' (ASCII 101)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 101 + ">@")
        assert f.getvalue() == "e"

        # Generate 'l' (ASCII 108)
        with redirect_stdout(io.StringIO()) as f:
            run("#" + "+" * 108 + ">@")
        assert f.getvalue() == "l"

    def test_hello_world_using_multiplication(self) -> None:
        """Test generating characters using multiplication."""
        # Generate 'A' (ASCII 65) using multiplication
        # 65 = 5 * 13, so we can use: 5 increments, mul=14, multiply by 13
        with redirect_stdout(io.StringIO()) as f:
            run("#+++++|+++++++++++++!>@")
        # num=5, mul=14, num *= (14-1) = 5*13 = 65
        assert f.getvalue() == "A"

    def test_hello_world_complete(self) -> None:
        """Test a complete Hello World program."""
        # Generate "Hi" using multiple segments
        hello_code = "#" + "+" * 72 + ">@" + "#" + "+" * 105 + ">@"  # H  # i

        with redirect_stdout(io.StringIO()) as f:
            run(hello_code)
        assert f.getvalue() == "Hi"


class TestHufIntegration:
    """Integration tests for Huf interpreter."""

    def test_complex_program_structure(self) -> None:
        """Test a complex program with multiple operations."""
        complex_code = (
            "#+++|++!+++>@"  # First segment: complex calculation
            + "#++++>@"  # Second segment: simple increment
            + "#|+++!>@"  # Third segment: multiplication
        )

        with redirect_stdout(io.StringIO()) as f:
            run(complex_code)
        # First: 3*2 + 3 = 9, Second: 4, Third: 0*2 = 0
        assert f.getvalue() == "\x09\x04\x00"

    def test_program_with_mixed_content(self) -> None:
        """Test program with mixed valid and invalid content."""
        mixed_code = (
            "Some text before\n"
            "#+++>@\n"
            "More text in between\n"
            "#++++>@\n"
            "Final text after"
        )

        with redirect_stdout(io.StringIO()) as f:
            run(mixed_code)
        assert f.getvalue() == "\x03\x04"

    def test_register_state_persistence(self) -> None:
        """Test that register state persists within segments but resets between segments."""
        with redirect_stdout(io.StringIO()) as f:
            run("#+++|+!+++>@")  # Single segment: state persists
        assert f.getvalue() == "\x06"  # 3*1 + 3 = 6

        with redirect_stdout(io.StringIO()) as f:
            run("#+++|+!@#+++>@")  # Two segments: state resets
        assert f.getvalue() == "\x03"  # Only second segment: 3


if __name__ == "__main__":
    pytest.main([__file__])
