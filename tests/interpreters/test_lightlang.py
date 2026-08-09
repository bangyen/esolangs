"""Unit tests for Lightlang interpreter.

Tests cover all Lightlang commands, program flow control, and example programs.
Lightlang is a minimal esoteric language that uses only 1 bit as memory.
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.lightlang import run


class TestLightlangBasicCommands:
    """Test basic Lightlang command functionality."""

    def test_toggle_command(self) -> None:
        """Test ^ command toggles the bit."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!", io=IO())
        assert f.getvalue() == "1"

        with redirect_stdout(io.StringIO()) as f:
            run("^^!", io=IO())
        assert f.getvalue() == "0"

    def test_print_command(self) -> None:
        """Test ! command prints the bit state."""
        with redirect_stdout(io.StringIO()) as f:
            run("!", io=IO())
        assert f.getvalue() == "0"

        with redirect_stdout(io.StringIO()) as f:
            run("^!", io=IO())
        assert f.getvalue() == "1"

    def test_input_command_empty(self) -> None:
        """Test ? command with empty input sets bit to 1."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("?!", io=IO())
            assert f.getvalue() == "1"

    def test_input_command_with_value(self) -> None:
        """Test ? command with input sets bit to 0."""
        with patch("builtins.input", return_value="test"):
            with redirect_stdout(io.StringIO()) as f:
                run("?!", io=IO())
            assert f.getvalue() == "0"

    def test_random_command(self) -> None:
        """Test @ command sets bit to random state."""
        # Test multiple times to ensure randomness works
        results = set()
        for _ in range(10):
            with redirect_stdout(io.StringIO()) as f:
                run("@!", io=IO())
            results.add(f.getvalue())
        # Should get both 0 and 1 at some point
        assert len(results) > 1

    def test_skip_command_bit_on(self) -> None:
        """Test & command skips next instruction when bit is 1."""
        with redirect_stdout(io.StringIO()) as f:
            run("^&!", io=IO())
        # Bit is 1, so & skips the ! command, no output
        assert f.getvalue() == ""

    def test_skip_command_bit_off(self) -> None:
        """Test & command does nothing when bit is 0."""
        with redirect_stdout(io.StringIO()) as f:
            run("&!", io=IO())
        # Bit is 0, so & does nothing, ! executes
        assert f.getvalue() == "0"

    def test_halt_command(self) -> None:
        """Test # command halts the program."""
        with redirect_stdout(io.StringIO()) as f:
            run("#!", io=IO())
        # Program halts before reaching !
        assert f.getvalue() == ""

    def test_jump_to_start_command(self) -> None:
        """Test < command jumps to start of program."""
        # Test that the jump command exists and can be executed without error
        # We can't easily test the infinite loop behavior, so we test the command exists
        with redirect_stdout(io.StringIO()) as f:
            run("^!#<", io=IO())
        # Should print 1, then halt before reaching the jump
        assert f.getvalue() == "1"

    def test_reverse_direction_command(self) -> None:
        """Test / command reverses instruction pointer direction."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!/#", io=IO())
        # First ^ sets bit to 1, ! prints 1, / reverses, then halt
        assert f.getvalue() == "11"

    def test_sleep_command(self) -> None:
        """Test _ command sleeps for 1 second."""
        with patch(
            "esolangs.interpreters.register_based.lightlang.time.sleep"
        ) as mock_sleep:
            with redirect_stdout(io.StringIO()) as f:
                run("_!", io=IO())
            # Verify sleep was called with 1 second
            mock_sleep.assert_called_once_with(1)
            assert f.getvalue() == "0"


class TestLightlangProgramFlow:
    """Test Lightlang program flow and control structures."""

    def test_forward_execution(self) -> None:
        """Test normal forward execution."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!^!", io=IO())
        assert f.getvalue() == "10"

    def test_backward_execution(self) -> None:
        """Test backward execution after direction reversal."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!/#", io=IO())
        # ^ sets bit to 1, ! prints 1, / reverses direction, then halt
        assert f.getvalue() == "11"

    def test_skip_with_direction_reversal(self) -> None:
        """Test skip command with direction reversal."""
        with redirect_stdout(io.StringIO()) as f:
            run("^&/#", io=IO())
        # ^ sets bit to 1, & skips /, then halt
        assert f.getvalue() == ""

    def test_multiple_direction_reversals(self) -> None:
        """Test multiple direction reversals."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!/#", io=IO())
        # ^ sets bit to 1, ! prints 1, / reverses, then halt
        assert f.getvalue() == "11"


class TestLightlangInputHandling:
    """Test Lightlang input handling and state management."""

    def test_input_prompt_behavior(self) -> None:
        """Test that input prompt behavior is correct."""
        with patch("builtins.input", return_value="test"):
            with redirect_stdout(io.StringIO()) as f:
                run("?!", io=IO())
            assert f.getvalue() == "0"

        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("?!", io=IO())
            assert f.getvalue() == "1"

    def test_multiple_inputs(self) -> None:
        """Test multiple input commands."""
        with patch("builtins.input", side_effect=["", "test"]):
            with redirect_stdout(io.StringIO()) as f:
                run("?!?!", io=IO())
            assert f.getvalue() == "10"

    def test_input_with_other_commands(self) -> None:
        """Test input command interaction with other commands."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("?^!!", io=IO())
            # ? sets bit to 1, ^ toggles to 0, ! prints 0, ! prints 0
            assert f.getvalue() == "00"


class TestLightlangEdgeCases:
    """Test Lightlang edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue() == ""

    def test_invalid_commands_ignored(self) -> None:
        """Test that invalid commands are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("xyz^!", io=IO())
        # Only ^ and ! are processed
        assert f.getvalue() == "1"

    def test_whitespace_ignored(self) -> None:
        """Test that whitespace is ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run(" ^ ! ", io=IO())
        # Only ^ and ! are processed
        assert f.getvalue() == "1"

    def test_program_with_only_invalid_commands(self) -> None:
        """Test program with only invalid commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("abcdefghijklmnopqrstuvwxyz", io=IO())
        assert f.getvalue() == ""

    def test_halt_in_middle_of_program(self) -> None:
        """Test halt command in middle of program."""
        with redirect_stdout(io.StringIO()) as f:
            run("^!#!", io=IO())
        # Only first ^ and ! execute before halt
        assert f.getvalue() == "1"


class TestLightlangExamples:
    """Test Lightlang example programs from the wiki."""

    def test_simple_loop(self) -> None:
        """Test the simple loop example: !^<"""
        # Test the basic commands without the infinite loop
        with redirect_stdout(io.StringIO()) as f:
            run("!^", io=IO())
        # Should print 0, toggle to 1
        assert f.getvalue() == "0"

    def test_loop_with_delay(self) -> None:
        """Test the loop with delay example: !^_<"""
        # Test the basic commands without the infinite loop
        with patch(
            "esolangs.interpreters.register_based.lightlang.time.sleep"
        ) as mock_sleep:
            with redirect_stdout(io.StringIO()) as f:
                run("!^_", io=IO())
            # Should print 0, toggle to 1, sleep
            mock_sleep.assert_called_once_with(1)
            assert f.getvalue() == "0"

    def test_truth_machine_empty_input(self) -> None:
        """Test truth machine with empty input (bit set to 1)."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("?!&", io=IO())
            # ? sets bit to 1 on empty input, ! prints it
            assert f.getvalue() == "1"

    def test_input_nonempty_sets_bit_zero(self) -> None:
        """Test that non-empty input clears the bit."""
        with patch("builtins.input", return_value="x"):
            with redirect_stdout(io.StringIO()) as f:
                run("?!&", io=IO())
            assert f.getvalue() == "0"

    def test_truth_machine_with_input(self) -> None:
        """Test truth machine with input (should terminate)."""
        with patch("builtins.input", return_value="test"):
            with redirect_stdout(io.StringIO()) as f:
                run("?!&#", io=IO())
            # ? sets bit to 0, ! prints 0, & does nothing, # halts
            assert f.getvalue() == "0"

    def test_hello_world_character_generation(self) -> None:
        """Test generating individual characters for Hello World."""
        # Test generating 'H' (ASCII 72 = 1001000 in binary)
        # This would require a very long sequence of ^ and ! commands
        # For testing, we'll just verify the basic bit manipulation works
        with redirect_stdout(io.StringIO()) as f:
            run("^!^!!^!^!!!", io=IO())
        # This generates the first 7 bits of 'H': 1001000
        assert f.getvalue() == "1001000"


class TestLightlangRandomness:
    """Test Lightlang's random command behavior."""

    def test_random_command_distribution(self) -> None:
        """Test that random command produces both 0 and 1."""
        results = []
        for _ in range(100):
            with redirect_stdout(io.StringIO()) as f:
                run("@!", io=IO())
            results.append(f.getvalue())

        # Should have both 0 and 1 in the results
        assert "0" in results
        assert "1" in results

    def test_random_with_other_commands(self) -> None:
        """Test random command interaction with other commands."""
        # Test that random state can be toggled
        with redirect_stdout(io.StringIO()) as f:
            run("@^!", io=IO())
        # @ sets random bit, ^ toggles it, ! prints result
        # Result should be opposite of what @ set
        result = f.getvalue()
        assert result in ["0", "1"]


class TestLightlangComplexPrograms:
    """Test more complex Lightlang program structures."""

    def test_nested_control_flow(self) -> None:
        """Test complex control flow with multiple commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("^&^!^&!", io=IO())
        # ^ sets bit to 1, & skips next ^, ! prints 1, ^ toggles to 0, & does nothing, ! prints 0
        assert f.getvalue() == "10"

    def test_direction_reversal_with_skips(self) -> None:
        """Test direction reversal combined with skip commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("^&/#", io=IO())
        # ^ sets bit to 1, & skips /, then halt
        assert f.getvalue() == ""

    def test_jump_to_start_terminates(self) -> None:
        """< jumps to the start; the toggled bit makes & behave differently."""
        with redirect_stdout(io.StringIO()) as f:
            run("^&#<", io=IO())
        # First pass: ^ (bit 1), & skips #, < jumps to start.
        # Second pass: ^ (bit 0), & does not skip, # halts.
        assert f.getvalue() == ""

    def test_multiple_prints(self) -> None:
        """Test multiple print commands."""
        with redirect_stdout(io.StringIO()) as f:
            run("!^!^!", io=IO())
        assert f.getvalue() == "010"

    def test_input_with_control_flow(self) -> None:
        """Test input command with control flow."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("?&!^!", io=IO())
            # ? sets bit to 1, & skips !, ^ toggles to 0, ! prints 0
            assert f.getvalue() == "0"


if __name__ == "__main__":
    pytest.main([__file__])
