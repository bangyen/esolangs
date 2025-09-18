"""
Unit tests for Dig interpreter.

Tests cover Dig commands and example programs from esolangs.org.
Dig is a 2D esoteric programming language with underground work commands.

The Dig interpreter manages a mole (pointer) that moves on a 2D grid and can dig
underground to access work commands. Movement commands work overground, while
work commands only function underground after digging.
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from src.esolangs.interpreters.register_based.dig import run


class TestDigBasicCommands:
    """Test basic Dig command functionality."""

    def test_halt_command(self) -> None:
        """Test @ halt command."""
        with redirect_stdout(io.StringIO()):
            run(["@"])
        # Should halt immediately without error

    def test_simple_movement(self) -> None:
        """Test simple movement with halt."""
        with redirect_stdout(io.StringIO()):
            run(["@ "])
        # Should move right and halt


class TestDigExamplePrograms:
    """Test example programs from esolangs.org."""

    def test_hello_world(self) -> None:
        """Test Hello World program from esolangs.org."""
        hello_world = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]

        with redirect_stdout(io.StringIO()) as f:
            run(hello_world)
        assert f.getvalue() == "Hello World!"

    def test_cat_program(self) -> None:
        """Test Cat program (infinite loop)."""
        cat_program = [">$=:'", "^2  <"]

        # Test that it doesn't crash immediately
        with patch("builtins.input", return_value="X"):
            with redirect_stdout(io.StringIO()) as f:
                # Use a function to break after first input
                def break_func():
                    return True

                run(cat_program, break_func)
        assert f.getvalue() == "X"

    def test_truth_machine(self) -> None:
        """Test Truth Machine program."""
        truth_machine = ["'   @", "    :", "    $1", ">$~;#", " 2  >$+:'", "    ^21 <"]

        # Test with input 0
        with patch("builtins.input", return_value="0"):
            with redirect_stdout(io.StringIO()) as f:
                run(truth_machine)
        assert f.getvalue() == "0"

        # Test with input 1 (should loop)
        with patch("builtins.input", return_value="1"):
            with redirect_stdout(io.StringIO()) as f:

                def break_func():
                    return True  # Break after first iteration

                run(truth_machine, break_func)
        assert f.getvalue() == "1"

    def test_nand_gate(self) -> None:
        """Test NAND Gate program."""
        nand_gate = [
            "'2  > $~ >$ 1:@",
            ">$~;#@2   3",
            "    > $~;#@2",
            "         > $0:@",
        ]

        # Test NAND(0,0) = 1
        with patch("builtins.input", side_effect=["0", "0"]):
            with redirect_stdout(io.StringIO()) as f:
                run(nand_gate)
        assert f.getvalue() == "1"

        # Test NAND(0,1) = 1
        with patch("builtins.input", side_effect=["0", "1"]):
            with redirect_stdout(io.StringIO()) as f:
                run(nand_gate)
        assert f.getvalue() == "1"

        # Test NAND(1,0) = 1
        with patch("builtins.input", side_effect=["1", "0"]):
            with redirect_stdout(io.StringIO()) as f:
                run(nand_gate)
        assert f.getvalue() == "1"

        # Test NAND(1,1) = 0
        with patch("builtins.input", side_effect=["1", "1"]):
            with redirect_stdout(io.StringIO()) as f:
                run(nand_gate)
        assert f.getvalue() == "0"


class TestDigUndergroundCommands:
    """Test Dig work commands that only work underground."""

    def test_simple_output(self) -> None:
        """Test simple character output underground."""
        # Based on hello world structure
        with redirect_stdout(io.StringIO()) as f:
            run([">$H:@", " 8  "])
        assert f.getvalue() == "H"

    def test_simple_digit_output(self) -> None:
        """Test simple digit output underground."""
        # Based on hello world structure
        with redirect_stdout(io.StringIO()) as f:
            run([">$5:@", " 8  "])
        assert f.getvalue() == "5"

    def test_punctuation_output(self) -> None:
        """Test punctuation output underground."""
        # Based on hello world structure
        with redirect_stdout(io.StringIO()) as f:
            run([">$!:@", " 8  "])
        assert f.getvalue() == "!"

    def test_newline_output(self) -> None:
        """Test newline output using % command."""
        # Based on hello world structure
        with redirect_stdout(io.StringIO()) as f:
            run([">$%:@", " 81  "])
        assert f.getvalue() == "\n"

    def test_space_output(self) -> None:
        """Test space output using % command."""
        # Based on hello world structure
        with redirect_stdout(io.StringIO()) as f:
            run([">$%:@", " 80  "])
        assert f.getvalue() == " "


class TestDigEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test empty program."""
        with pytest.raises(ValueError):
            run([])
        # Should raise ValueError for empty program

    def test_single_character_program(self) -> None:
        """Test program with single character."""
        with redirect_stdout(io.StringIO()):
            run(["@"])
        # Should halt immediately


class TestDigComplexPrograms:
    """Test more complex Dig programs."""

    def test_multi_character_output(self) -> None:
        """Test outputting multiple characters."""
        # Simple program that outputs "Hi"
        program = [">$H:i:@", " 8    "]

        with redirect_stdout(io.StringIO()) as f:
            run(program)
        assert f.getvalue() == "Hi"

    def test_conditional_movement(self) -> None:
        """Test conditional movement with # command."""
        # Program with conditional rotation
        program = ["1#", "@ "]

        with redirect_stdout(io.StringIO()):
            run(program)
        # Should rotate right and move down to @


if __name__ == "__main__":
    pytest.main([__file__])
