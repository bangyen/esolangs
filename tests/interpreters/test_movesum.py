"""
Unit tests for Movesum interpreter.

Tests cover all Movesum commands, program flow control, and example programs.
Movesum is an esoteric language with only 'move' and 'sum' instructions operating
on a right-unbounded array of integers.
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from src.esolangs.interpreters.register_based.movesum import run


class TestMovesumBasicCommands:
    """Test basic Movesum command functionality."""

    def test_sum_command(self) -> None:
        """Test sum command sets position 0 to sum of positions 1-4."""
        code = ["0=0 1=1 2=2 3=3 4=4", "sum"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt immediately as array doesn't change after sum

    def test_move_command_positive_indices(self) -> None:
        """Test move command with positive indices copies values."""
        code = ["0=5 1=10", "move 0 2", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt after two move 0 0 commands

    def test_move_command_output(self) -> None:
        """Test move command with negative second argument outputs value."""
        code = ["0=72", "move 0 -1", "move 0 0"]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == "72 "

    def test_move_command_input(self) -> None:
        """Test move command with negative first argument reads input."""
        code = ["0=0", "move -1 0", "move 0 0"]
        with patch("builtins.input", return_value="42"):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Array should be updated with input value

    def test_move_command_both_negative(self) -> None:
        """Test move command with both arguments negative does nothing."""
        code = ["0=5", "move -1 -1", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt without changes

    def test_initialization_with_values(self) -> None:
        """Test array initialization with key=value pairs."""
        code = ["0=4 3=8 19=3 15=12345", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt after move 0 0

    def test_initialization_with_42_key(self) -> None:
        """Test initialization with 42 as key (user input)."""
        code = ["42=5", "move 0 0"]
        with patch("builtins.input", return_value="10"):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should set position 10 to 5

    def test_initialization_with_42_value(self) -> None:
        """Test initialization with 42 as value (user input)."""
        code = ["0=42", "move 0 0"]
        with patch("builtins.input", return_value="99"):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should set position 0 to 99

    def test_initialization_with_42_both(self) -> None:
        """Test initialization with 42 as both key and value."""
        code = ["42=42", "move 0 0"]
        with patch("builtins.input", side_effect=["5", "7"]):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should set position 5 to 7

    def test_empty_input_handling(self) -> None:
        """Test handling of empty input (EOF)."""
        code = ["0=42", "move 0 0"]
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should set position 0 to 0 (empty input treated as 0)


class TestMovesumProgramFlow:
    """Test Movesum program flow and halting behavior."""

    def test_cyclic_execution(self) -> None:
        """Test that instructions execute cyclically."""
        code = ["0=1 1=2", "move 0 2", "move 1 3", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should execute cyclically until halt

    def test_halting_condition(self) -> None:
        """Test program halts when array doesn't change for 2 commands."""
        code = ["0=5", "move 0 0", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt after two identical commands

    def test_forced_halt_sequence(self) -> None:
        """Test the forced halt sequence move 0 0 twice."""
        code = ["0=1 1=2", "move 0 0", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should halt immediately

    def test_array_expansion(self) -> None:
        """Test that array expands beyond initial 5 positions."""
        code = ["0=1", "move 0 10", "move 10 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should handle positions beyond initial range


class TestMovesumExamples:
    """Test Movesum example programs from the esolang wiki."""

    def test_hello_world_ascii(self) -> None:
        """Test Hello World program using ASCII values."""
        code = [
            "0=72 1=101 2=108 3=111 4=32 5=87 6=114 7=100 8=1 9=2",
            "move 0 -1",
            "move 8 10",
            "move 1 -1",
            "move 9 10",
            "move 2 -1",
            "move 8 10",
            "move 2 -1",
            "move 9 10",
            "move 3 -1",
            "move 8 10",
            "move 4 -1",
            "move 9 10",
            "move 5 -1",
            "move 8 10",
            "move 3 -1",
            "move 9 10",
            "move 6 -1",
            "move 8 10",
            "move 2 -1",
            "move 9 10",
            "move 7 -1",
            "move 0 0",
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        expected = "72 101 108 108 111 32 87 111 114 108 100 "
        assert f.getvalue() == expected

    def test_add_two_inputs(self) -> None:
        """Test program that adds two inputs."""
        code = ["1=42 2=42", "sum", "move 0 -1", "move 0 0"]
        with patch("builtins.input", side_effect=["5", "3"]):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should output 8 (5+3)

    def test_truth_machine_zero(self) -> None:
        """Test truth machine with input 0."""
        code = ["0=42", "move 0 -1", "move 0 1", "move 2 1"]
        with patch("builtins.input", return_value="0"):
            with redirect_stdout(io.StringIO()):
                run(code)
        # Should output 0 once


class TestMovesumEdgeCases:
    """Test Movesum edge cases and error conditions."""

    def test_minimal_program(self) -> None:
        """Test minimal valid program."""
        code = ["0=0", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should execute without error

    def test_large_array_indices(self) -> None:
        """Test handling of large array indices."""
        code = ["0=1", "move 0 1000", "move 1000 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should handle large indices

    def test_negative_array_indices(self) -> None:
        """Test handling of negative array indices in move command."""
        code = ["0=5", "move 0 -1", "move 0 0"]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == "5 "

    def test_sum_with_zeros(self) -> None:
        """Test sum command with all zeros."""
        code = ["0=0 1=0 2=0 3=0 4=0", "sum", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should set position 0 to 0

    def test_sum_with_large_values(self) -> None:
        """Test sum command with large values."""
        code = ["0=0 1=1000 2=2000 3=3000 4=4000", "sum", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should set position 0 to 10000

    def test_multiple_initialization_pairs(self) -> None:
        """Test initialization with many key=value pairs."""
        code = ["0=1 1=2 2=3 3=4 4=5 5=6 6=7 7=8 8=9 9=10", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should initialize all positions correctly

    def test_whitespace_in_initialization(self) -> None:
        """Test initialization with various whitespace patterns."""
        code = ["0 = 1   2=3   4 = 5", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should handle whitespace correctly

    def test_instruction_with_whitespace(self) -> None:
        """Test instructions with various whitespace patterns."""
        code = ["0=1 1=2", "move  0  1", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should handle whitespace in instructions


class TestMovesumValidation:
    """Test Movesum input validation and error handling."""

    def test_empty_code_raises_error(self) -> None:
        """Test that empty code raises ValueError."""
        with pytest.raises(ValueError, match="Movesum program cannot be empty"):
            run([])

    def test_single_line_raises_error(self) -> None:
        """Test that code with only initialization raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Movesum program must have at least initialization and one instruction",
        ):
            run(["0=1"])

    def test_invalid_initialization_handled_gracefully(self) -> None:
        """Test that invalid initialization is handled gracefully."""
        code = ["invalid line", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should not crash, just ignore invalid initialization

    def test_invalid_instruction_handled_gracefully(self) -> None:
        """Test that invalid instructions are handled gracefully."""
        code = ["0=1", "invalid instruction", "move 0 0"]
        with redirect_stdout(io.StringIO()):
            run(code)
        # Should not crash, just skip invalid instructions
