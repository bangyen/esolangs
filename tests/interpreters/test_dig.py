"""Unit tests for Dig interpreter.

Tests cover Dig commands and example programs from esolangs.org.
Dig is a 2D esoteric programming language with a mole (pointer) that moves on a
grid. Movement commands work overground; work commands only function underground
after digging with ``$``. The value read by ``$``/``#``/``%`` and the operators
is the first digit adjacent to the command (up, right, down, left).
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.dig import run


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    """Run a Dig program (patching input) and return its stdout."""
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestDigHaltAndMovement:
    """Test overground movement commands."""

    def test_halt_command(self) -> None:
        """Test @ halt command."""
        assert run_and_capture(["@"]) == ""

    def test_move_right_then_halt(self) -> None:
        """Test simple movement with halt."""
        assert run_and_capture([">@"]) == ""

    def test_work_commands_ignored_overground(self) -> None:
        """Test that work commands do nothing while overground."""
        assert run_and_capture([">H:@", "  2 "]) == ""


class TestDigUndergroundCommands:
    """Test work commands that only function underground."""

    def test_print_initial_zero(self) -> None:
        """Test that : prints the mole's initial value of 0."""
        assert run_and_capture([">$:", " 2 "]) == "0"

    def test_print_digit(self) -> None:
        """Test that a digit sets the mole and : outputs it."""
        assert run_and_capture([">$5:", " 2 "]) == "5"

    def test_last_digit_wins(self) -> None:
        """Test that consecutive digits keep only the last value."""
        assert run_and_capture([">$99:", " 3 "]) == "9"

    def test_print_character(self) -> None:
        """Test that letters set the mole to their ASCII value."""
        assert run_and_capture([">$H:", " 2 "]) == "H"

    def test_newline_output(self) -> None:
        """Test that % with a 1 beside it outputs a newline."""
        assert run_and_capture([">$%:", " 21"]) == "\n"

    def test_space_output(self) -> None:
        """Test that % with a 0 beside it outputs a space."""
        assert run_and_capture([">$%:", " 20"]) == " "


class TestDigArithmetic:
    """Test the arithmetic operators against an adjacent digit."""

    def test_addition(self) -> None:
        assert run_and_capture([">$ 3+:", " 4  2 "]) == "5"

    def test_subtraction(self) -> None:
        assert run_and_capture([">$ 7-:", " 4  3 "]) == "4"

    def test_multiplication(self) -> None:
        assert run_and_capture([">$ 4*:", " 4  2 "]) == "8"

    def test_division(self) -> None:
        assert run_and_capture([">$ 9/:", " 4  3 "]) == "3"

    def test_large_result_printed_as_character(self) -> None:
        """Test that values >= 10 are printed as characters."""
        assert run_and_capture([">$ 6+:", " 4  5 "]) == "\x0b"


class TestDigInput:
    """Test the input commands."""

    def test_integer_input(self) -> None:
        """Test that ~ reads a single integer."""
        assert run_and_capture([">$~:", " 2 "], inputs=["7"]) == "7"

    def test_character_input(self) -> None:
        """Test that = reads a single character."""
        assert run_and_capture([">$=:", " 2 "], inputs=["A"]) == "A"


class TestDigExamplePrograms:
    """Test example programs from esolangs.org."""

    def test_hello_world(self) -> None:
        """Test the Hello World program from esolangs.org."""
        hello_world = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]
        assert run_and_capture(hello_world) == "Hello World!"

    def test_nand_gate(self) -> None:
        """Test the NAND gate program from esolangs.org."""
        nand_gate = [
            "'2  > $~ >$ 1:@",
            ">$~;#@2   3",
            "    > $~;#@2",
            "         > $0:@",
        ]
        for a, b, expected in [
            ("0", "0", "1"),
            ("0", "1", "1"),
            ("1", "0", "1"),
            ("1", "1", "0"),
        ]:
            assert run_and_capture(nand_gate, inputs=[a, b]) == expected


class TestDigEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that an empty program raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            run([], io=IO())

    def test_single_character_program(self) -> None:
        """Test a program containing only a halt command."""
        assert run_and_capture(["@"]) == ""

    def test_no_adjacent_digit_halts(self) -> None:
        """A work command with no adjacent digit is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$+:", "    "], io=IO())

    def test_divide_by_zero_halts(self) -> None:
        """Dividing by an adjacent zero is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$/", " 10"], io=IO())

    def test_empty_input_line_reads_zero(self) -> None:
        """An empty input line stores 0 in the mole."""
        assert run_and_capture([">$=:", " 2 "], inputs=[""]) == "0"
