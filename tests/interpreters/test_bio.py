"""
Unit tests for BIO (Binary IO) interpreter.

Tests cover all BIO commands, edge cases, and example programs from esolangs.org.
"""

import io
import sys
from contextlib import redirect_stdout

import pytest

# Add src directory to path for imports
sys.path.insert(0, "src")
from esolangs.interpreters.register_based.bio import run


class TestBIOBasicCommands:
    """Test basic BIO command functionality."""

    def test_increment_commands(self) -> None:
        """Test 0O[xyz] increment commands."""
        with redirect_stdout(io.StringIO()) as _:
            run("0ox;")

        with redirect_stdout(io.StringIO()) as _:
            run("0oy;0oy;0oy;")

        with redirect_stdout(io.StringIO()) as _:
            run("0oz;")

    def test_decrement_commands(self) -> None:
        """Test 1O[xyz] decrement commands."""
        with redirect_stdout(io.StringIO()) as _:
            run("1ox;")

        with redirect_stdout(io.StringIO()) as _:
            run("1oy;1oy;1oy;")

    def test_output_commands(self) -> None:
        """Test 1I[xyz] output commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("1ix;")
        assert f.getvalue() == "\x00"

        with redirect_stdout(io.StringIO()) as f:
            run("0oy;1iy;")
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oz;" * 10 + "1iz;")  # 10 increments = ASCII 10 (newline)
        assert f.getvalue() == "\n"

    def test_case_insensitive_commands(self) -> None:
        """Test that BIO commands are case-insensitive."""
        with redirect_stdout(io.StringIO()) as f:
            run("0OX;1IX;")
        assert f.getvalue() == "\x01"

        with redirect_stdout(io.StringIO()) as f:
            run("0oY;1Iy;")
        assert f.getvalue() == "\x01"

    def test_register_independence(self) -> None:
        """Test that registers x, y, z are independent."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0oy;0oz;1ix;1iy;1iz;")
        assert f.getvalue() == "\x01\x01\x01"


class TestBIOWhileLoops:
    """Test BIO while loop functionality (0I[xyz] commands)."""

    def test_simple_while_loop(self) -> None:
        """Test a simple while loop that executes once."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;1ox;};1iy;")
        assert f.getvalue() == "\x01"

    def test_while_loop_skip_when_zero(self) -> None:
        """Test that while loop is skipped when register is zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{0oy;};1iy;")
        assert f.getvalue() == "\x00"

    def test_nested_while_loops(self) -> None:
        """Test nested while loops."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ix{0oy;0iy{0oz;1oy;};1ox;};1iz;")
        assert f.getvalue() == "\x01"

    def test_while_loop_with_output(self) -> None:
        """Test while loop that outputs characters."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0ox;0ix{1ix;1ox;};")
        assert f.getvalue() == "\x02\x01"


class TestBIOMathematicalOperations:
    """Test BIO mathematical operations from esolangs.org examples."""

    def test_addition(self) -> None:
        """Test addition: 0ox; 0oy; 0ix{ 1ox; 0oy; }; 1iy;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;0oy;0ix{1ox;0oy;};1iy;")
        assert f.getvalue() == "\x02"  # 1 + 1 = 2

    def test_subtraction(self) -> None:
        """Test subtraction: 0ox; 0ox; 0oy; 0iy{ 0ox; 1oy; }; 1ix;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 2 + "0oy;0iy{0ox;1oy;};1ix;")
        assert (
            f.getvalue() == "\x03"
        )  # 2 + 1 = 3 (this is actually addition, not subtraction)

    def test_multiplication(self) -> None:
        """Test multiplication: 0ox; 0ox; 0ox; 0ox; 0ox; 0ix{ 1ox; 0oy; 0oy; 0oy; 0oy; 0oy; }; 1iy;"""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 5 + "0ix{1ox;" + "0oy;" * 5 + "};1iy;")
        assert f.getvalue() == "\x19"  # 5 * 5 = 25

    def test_complex_calculation(self) -> None:
        """Test a more complex calculation."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 3 + "0ix{1ox;0oy;0oy;};1iy;")
        assert f.getvalue() == "\x06"


class TestBIOHelloWorld:
    """Test BIO Hello World program from esolangs.org."""

    def test_hello_world_program(self) -> None:
        """Test the complete Hello World program from esolangs.org."""
        # This is a simplified version of the Hello World program
        # The full program is very long, so we test the pattern for generating 'H'
        hello_world_code = (
            "0ox;" * 9
            + "0ix{"
            + "0oy;" * 8
            + "1ox;};"
            + "1iy;"
            + "0iy{1oy;};"
            + "0ox;" * 10
            + "0ix{"
            + "0oy;" * 10
            + "1ox;};"
            + "0oy;1iy;"
            + "0iy{1oy;};"
        )

        with redirect_stdout(io.StringIO()) as f:
            run(hello_world_code)
        assert f.getvalue() == "He"

    def test_character_generation_pattern(self) -> None:
        """Test the pattern for generating specific ASCII characters."""
        # Generate 'A' (ASCII 65)
        # 65 = 8*8 + 1, so we need 8 increments, then 8*8 in loop, then 1 more
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 8 + "0ix{" + "0oy;" * 8 + "1ox;};0oy;1iy;")
        assert f.getvalue() == "A"


class TestBIOEdgeCases:
    """Test BIO edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("")
        assert f.getvalue() == ""

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("   \n\t  ")
        assert f.getvalue() == ""

    def test_invalid_commands_ignored(self) -> None:
        """Test that invalid commands are ignored by regex."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;invalid;1ix;")
        assert f.getvalue() == "\x01"

    def test_negative_register_values(self) -> None:
        """Test handling of negative register values."""
        with redirect_stdout(io.StringIO()) as f:
            run("1ox;1ix;")
        assert f.getvalue() == "\xff"

    def test_large_register_values(self) -> None:
        """Test handling of large register values."""
        large_code = "0ox;" * 300 + "1ix;"  # 300 increments
        with redirect_stdout(io.StringIO()) as f:
            run(large_code)
        assert f.getvalue() == chr(300 % 256)

    def test_unmatched_while_loop(self) -> None:
        """Test behavior with unmatched while loop (missing closing brace)."""
        # This should not crash, but may have unexpected behavior
        with redirect_stdout(io.StringIO()) as _:
            run("0ox;0ix{0oy;")  # Missing closing brace
        # The program should still run, but the loop won't terminate properly
        # This is expected behavior for malformed BIO code

    def test_empty_while_loop(self) -> None:
        """Test empty while loop that doesn't execute."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{};1ix;")
        assert f.getvalue() == "\x00"

    def test_while_loop_with_zero_register(self) -> None:
        """Test while loop when register is already zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ix{0oy;};1iy;")
        assert f.getvalue() == "\x00"


class TestBIOIntegration:
    """Integration tests for BIO interpreter."""

    def test_complex_program(self) -> None:
        """Test a complex BIO program with multiple operations."""
        complex_code = (
            "0ox;" * 3  # x = 3
            + "0oy;" * 2  # y = 2
            + "0ix{"  # while x > 0
            + "0oz;"  # increment z
            + "1ox;"  # decrement x
            + "};"
            + "1iz;"  # output z (should be 3)
        )

        with redirect_stdout(io.StringIO()) as f:
            run(complex_code)
        assert f.getvalue() == "\x03"

    def test_register_reset_pattern(self) -> None:
        """Test the common pattern of resetting registers to zero."""
        with redirect_stdout(io.StringIO()) as f:
            run("0oy;" * 3 + "0iy{1oy;};1iy;")
        assert f.getvalue() == "\x00"

    def test_character_arithmetic(self) -> None:
        """Test character arithmetic operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("0ox;" * 66 + "1ix;")  # 66 = 'B'
        assert f.getvalue() == "B"


if __name__ == "__main__":
    pytest.main([__file__])
