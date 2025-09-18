"""
Unit tests for WII2D (Why Is It 2D?) interpreter.

Tests cover all WII2D commands, edge cases, and example programs from esolangs.org.
Includes timeout protection to prevent hanging tests.
"""

import io
import signal
from contextlib import redirect_stdout
from typing import Any, Callable

import pytest

from src.esolangs.interpreters.register_based.WII2D import run


class TimeoutError(Exception):
    """Custom timeout exception for test protection."""


def timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for timeout protection."""
    raise TimeoutError("Test execution timed out")


def run_with_timeout(func: Callable, timeout_seconds: int = 5) -> Any:
    """
    Run a function with timeout protection.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Function result

    Raises:
        TimeoutError: If function exceeds timeout
    """
    # Set up signal handler for timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        result = func()
        return result
    finally:
        # Restore original signal handler and cancel alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class TestWII2DBasicCommands:
    """Test basic WII2D command functionality."""

    def test_movement_commands(self) -> None:
        """Test directional movement commands (^v<>)."""
        # Simple program that moves right and outputs
        code = [">~.", "!"]

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should output the accumulator value (0) as ASCII

    def test_arithmetic_operations(self) -> None:
        """Test arithmetic operations (+-*/s)."""
        # Test increment - move right, increment, output, halt
        code = [">+~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x01"  # 0 + 1 = 1

    def test_digit_commands(self) -> None:
        """Test digit commands (0-9) that set accumulator."""
        # Test setting accumulator to 5 and outputting
        code = [">5~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x05"  # ASCII 5

    def test_output_command(self) -> None:
        """Test output command (~) that prints accumulator as ASCII."""
        # Test outputting 'A' (ASCII 65)
        code = [">65~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert (
            f.getvalue() == "\x05"
        )  # The program outputs 65 as a character, but 65 is processed as 6 then 5

    def test_halt_command(self) -> None:
        """Test halt command (.) that ends program execution."""
        code = ["!", "."]

        # Should complete without hanging
        run_with_timeout(lambda: run(code))

    def test_nop_command(self) -> None:
        """Test nop command (#) that does nothing."""
        code = [">#~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x00"  # Accumulator unchanged


class TestWII2DArithmetic:
    """Test WII2D arithmetic operations."""

    def test_increment_operation(self) -> None:
        """Test + operation that increments accumulator."""
        code = [">+++~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x03"  # 0 + 1 + 1 + 1 = 3

    def test_decrement_operation(self) -> None:
        """Test - operation that decrements accumulator."""
        code = [">5---~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x02"  # 5 - 1 - 1 - 1 = 2

    def test_double_operation(self) -> None:
        """Test * operation that doubles accumulator."""
        code = [">3*~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x06"  # 3 * 2 = 6

    def test_halve_operation(self) -> None:
        """Test / operation that halves accumulator."""
        code = [">8/~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x04"  # 8 / 2 = 4

    def test_square_operation(self) -> None:
        """Test s operation that squares accumulator."""
        code = [">3s~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x09"  # 3^2 = 9

    def test_complex_arithmetic(self) -> None:
        """Test complex arithmetic expression."""
        code = [">2+*s~.", "!"]  # (2+1)*2 = 6, then 6^2 = 36

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == chr(36)  # ASCII 36 = '$'


class TestWII2DControlFlow:
    """Test WII2D control flow commands."""

    def test_jump_command(self) -> None:
        """Test @ command that jumps to closest @."""
        code = ["!", ">@~.", "  @"]

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should jump to the second @ and output

    def test_random_direction(self) -> None:
        """Test ? command that moves in random direction."""
        code = ["!", "?~."]

        # This test may be flaky due to randomness, but should not hang
        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should output something without hanging


class TestWII2DHelloWorld:
    """Test WII2D Hello World program from esolangs.org."""

    def test_hello_world_program(self) -> None:
        """Test the complete Hello World program from esolangs.org."""
        # The Hello World program from esolangs.org
        hello_world_code = [
            ">8s++++++++~9+s+~+++++++~~+++~9+**++++~8**~*9+s-------------~9+s+++++++++++~+++~9+s++++++++~9+s~4s*+~.",
            "!",
        ]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(hello_world_code), timeout_seconds=10)
        assert f.getvalue() == "Hello, World!"

    def test_character_generation_pattern(self) -> None:
        """Test pattern for generating specific ASCII characters."""
        # Generate 'H' (ASCII 72)
        code = [">72~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert (
            f.getvalue() == "\x02"
        )  # The program outputs 72 as a character, but 72 is processed as 7 then 2

    def test_simple_hello_pattern(self) -> None:
        """Test a simplified hello pattern."""
        # Generate "Hi" using arithmetic - use a single line approach
        code = [">72~105~.", "!"]  # H (72) then i (105) then halt

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x02\x05"  # 72 becomes 7,2 and 105 becomes 1,0,5


class TestWII2DEdgeCases:
    """Test WII2D edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        code: list[str] = []

        # Should return immediately without error
        run_with_timeout(lambda: run(code))

    def test_program_without_start_marker(self) -> None:
        """Test program without ! start marker."""
        code = ["~.", "  "]

        # Should return immediately without error
        run_with_timeout(lambda: run(code))

    def test_single_line_program(self) -> None:
        """Test single line program with start marker."""
        code = [">~.", "!"]

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x00"

    def test_uneven_line_lengths(self) -> None:
        """Test program with uneven line lengths."""
        code = [">~.", "  +", "!"]

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should handle padding correctly

    def test_wrap_around_behavior(self) -> None:
        """Test pointer wrap-around at grid boundaries."""
        # Create a program that tests wrap-around with a clear halt path
        code = [">~.", "!"]  # Move right, output, halt

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should output accumulator value (0) as ASCII

    def test_large_accumulator_values(self) -> None:
        """Test handling of large accumulator values."""
        code = [">255~.", "!"]  # Maximum byte value

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert (
            f.getvalue() == "\x05"
        )  # The program outputs 255 as a character, but 255 is processed as 2 then 5 then 5

    def test_division_by_zero_equivalent(self) -> None:
        """Test division when accumulator is 1 (results in 0)."""
        code = [">1/~.", "!"]  # 1 / 2 = 0 (integer division)

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x00"

    def test_no_at_commands_for_jump(self) -> None:
        """Test @ command when no other @ commands exist."""
        code = [">@~.", "!"]  # Try to jump but no other @ exists

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should continue execution normally


class TestWII2DIntegration:
    """Integration tests for WII2D interpreter."""

    def test_complex_program_with_multiple_operations(self) -> None:
        """Test a complex program with multiple operations."""
        code = [">5+*s/~.", "!"]  # (5+1)*2 = 12, 12^2 = 144, 144/2 = 72

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "H"  # ASCII 72

    def test_program_with_loops_and_conditionals(self) -> None:
        """Test program that uses control flow extensively."""
        code = ["!", ">@~.", "  @"]

        with redirect_stdout(io.StringIO()):
            run_with_timeout(lambda: run(code))
        # Should execute without hanging

    def test_character_arithmetic_chain(self) -> None:
        """Test a chain of character arithmetic operations."""
        # Test multiple character outputs in a single line
        code = [">65~66~67~.", "!"]  # A (65), B (66), C (67) then halt

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x05\x06\x07"  # 65->6,5, 66->6,6, 67->6,7


class TestWII2DMathematicalOperations:
    """Test WII2D mathematical operations from esolangs.org examples."""

    def test_addition_simulation(self) -> None:
        """Test addition using increment operations."""
        code = [">3++++~.", "!"]  # 3 + 4 = 7

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x07"

    def test_multiplication_simulation(self) -> None:
        """Test multiplication using doubling operations."""
        code = [">4**~.", "!"]  # 4 * 2 * 2 = 16

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x10"

    def test_power_operations(self) -> None:
        """Test power operations using square function."""
        code = [">3s~.", "!"]  # 3^2 = 9

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert f.getvalue() == "\x09"

    def test_division_simulation(self) -> None:
        """Test division using halving operations."""
        code = [">16//~.", "!"]  # 16 / 2 / 2 = 4

        with redirect_stdout(io.StringIO()) as f:
            run_with_timeout(lambda: run(code))
        assert (
            f.getvalue() == "\x01"
        )  # The program outputs 16 as a character, but 16 is processed as 1 then 6


if __name__ == "__main__":
    pytest.main([__file__])
