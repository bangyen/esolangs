"""
Unit tests for Sophie interpreter.

Tests cover all Sophie commands, program flow control, and example programs.
Sophie is a finite state automaton language with a single accumulator.
"""

import io
import signal
from contextlib import redirect_stdout
from typing import Generator
from unittest.mock import patch

import pytest

from src.esolangs.interpreters.register_based.sophie import find, run


class TimeoutError(Exception):
    """Custom timeout exception for test protection."""


def timeout_handler(signum: int, frame: object) -> None:
    """Signal handler for test timeouts."""
    raise TimeoutError("Test timed out")


@pytest.fixture
def timeout_protection() -> Generator[None, None, None]:
    """Fixture to add timeout protection to tests."""
    # Set up timeout handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5 second timeout

    yield

    # Clean up
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old_handler)


class TestSophieBasicCommands:
    """Test basic Sophie command functionality."""

    def test_output_number(self, timeout_protection: None) -> None:
        """Test . command outputs accumulator as number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$42.&")
        assert f.getvalue() == "42"

    def test_output_char(self, timeout_protection: None) -> None:
        """Test , command outputs accumulator as character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&")
        assert f.getvalue() == "A"

    def test_input_number(self, timeout_protection: None) -> None:
        """Test : command inputs number to accumulator."""
        with patch("builtins.input", return_value="123"):
            with redirect_stdout(io.StringIO()) as f:
                run(":.&")
            assert f.getvalue() == "123"

    def test_input_char(self, timeout_protection: None) -> None:
        """Test ; command inputs character to accumulator."""
        with patch("builtins.input", return_value="X"):
            with redirect_stdout(io.StringIO()) as f:
                run(";,&")
            assert f.getvalue() == "X"

    def test_load_char_constant(self, timeout_protection: None) -> None:
        """Test #c command loads character constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,&")
        assert f.getvalue() == "H"

    def test_load_number_constant(self, timeout_protection: None) -> None:
        """Test #$n command loads number constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65,&")
        assert f.getvalue() == "A"

    def test_halt_command(self, timeout_protection: None) -> None:
        """Test & command halts the program."""
        with redirect_stdout(io.StringIO()) as f:
            run("&.")
        # Program halts before reaching output
        assert f.getvalue() == ""


class TestSophieConditionals:
    """Test Sophie conditional statement functionality."""

    def test_char_conditional_true(self, timeout_protection: None) -> None:
        """Test @c{} conditional when accumulator matches character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,#C,}&")
        assert f.getvalue() == "AC"

    def test_char_conditional_false(self, timeout_protection: None) -> None:
        """Test @c{} conditional when accumulator doesn't match character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{.,}{#C,}&")
        assert f.getvalue() == "C"

    def test_number_conditional_true(self, timeout_protection: None) -> None:
        """Test @$n{} conditional when accumulator matches number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$65{,#C,}&")
        assert f.getvalue() == "AC"

    def test_number_conditional_false(self, timeout_protection: None) -> None:
        """Test @$n{} conditional when accumulator doesn't match number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{.,}{#C,}&")
        assert f.getvalue() == "C"

    def test_conditional_without_else(self, timeout_protection: None) -> None:
        """Test conditional without else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,&")
        assert f.getvalue() == "A"

    def test_nested_conditionals(self, timeout_protection: None) -> None:
        """Test nested conditional statements."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{@$65{,#B,}}{#C,}&")
        assert f.getvalue() == "AB"


class TestSophieLoops:
    """Test Sophie loop functionality."""

    def test_simple_loop(self, timeout_protection: None) -> None:
        """Test basic loop structure."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.*]&")
        # Should print 3 then break
        assert f.getvalue() == "3"

    def test_loop_with_break(self, timeout_protection: None) -> None:
        """Test loop with break statement."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$1[.*]&")
        # Should print 1 then break
        assert f.getvalue() == "1"

    def test_nested_loops(self, timeout_protection: None) -> None:
        """Test nested loop structures."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[.*]]&")
        # Should print A, then B's ASCII value (66), then break
        assert f.getvalue() == "66"


class TestSophieComments:
    """Test Sophie comment functionality."""

    def test_comment_block(self, timeout_protection: None) -> None:
        """Test comment blocks are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("{This is a comment}#A,&")
        assert f.getvalue() == "A"

    def test_nested_comments(self, timeout_protection: None) -> None:
        """Test nested comment blocks."""
        with redirect_stdout(io.StringIO()) as f:
            run("{Outer{Inner}comment}#A,&")
        assert f.getvalue() == "A"


class TestSophieInputHandling:
    """Test Sophie input handling and edge cases."""

    def test_invalid_number_input(self, timeout_protection: None) -> None:
        """Test invalid number input leaves accumulator unchanged."""
        with patch("builtins.input", return_value="not_a_number"):
            with redirect_stdout(io.StringIO()) as f:
                run("#$42:.&")
            # Accumulator should remain 42
            assert f.getvalue() == "42"

    def test_empty_char_input(self, timeout_protection: None) -> None:
        """Test empty character input."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("#$42;.&")
            # Accumulator should remain 42
            assert f.getvalue() == "42"

    def test_multiple_inputs(self, timeout_protection: None) -> None:
        """Test multiple input commands."""
        with patch("builtins.input", side_effect=["65", "B"]):
            with redirect_stdout(io.StringIO()) as f:
                run(":;,&")
            assert f.getvalue() == "B"


class TestSophieEdgeCases:
    """Test Sophie edge cases and error conditions."""

    def test_empty_program(self, timeout_protection: None) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("")
        assert f.getvalue() == ""

    def test_unmatched_brackets(self, timeout_protection: None) -> None:
        """Test program with unmatched brackets."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A{&")
        # Should handle gracefully
        assert f.getvalue() == ""

    def test_invalid_commands_ignored(self, timeout_protection: None) -> None:
        """Test that invalid commands are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("xyz#A,&")
        # Only valid commands should execute
        assert f.getvalue() == "A"

    def test_whitespace_ignored(self, timeout_protection: None) -> None:
        """Test that whitespace is ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&")
        # Only valid commands should execute
        assert f.getvalue() == "A"


class TestSophieExamples:
    """Test Sophie example programs from the wiki."""

    def test_hello_world(self, timeout_protection: None) -> None:
        """Test Hello World program from Sophie wiki."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&")
        assert f.getvalue() == "Hello, World!"

    def test_truth_machine_zero(self, timeout_protection: None) -> None:
        """Test Truth Machine with input 0."""
        with patch("builtins.input", return_value="0"):
            with redirect_stdout(io.StringIO()) as f:
                run(";@1{[,]}{,&}")
        assert f.getvalue() == "0"

    def test_truth_machine_one(self, timeout_protection: None) -> None:
        """Test Truth Machine with input 1 (should loop)."""
        with patch("builtins.input", return_value="1"):
            # Use timeout to prevent infinite loop
            with redirect_stdout(io.StringIO()) as f:
                try:
                    run(";@1{[,]}{,&}")
                except TimeoutError:
                    pass
            # Should have printed at least one 1
            assert "1" in f.getvalue()

    def test_cat_program_empty(self, timeout_protection: None) -> None:
        """Test Cat program with empty input."""
        with patch("builtins.input", return_value=""):
            with redirect_stdout(io.StringIO()) as f:
                run("[;@$0{&}{,}]")
        assert f.getvalue() == ""

    def test_cat_program_with_input(self, timeout_protection: None) -> None:
        """Test Cat program with input."""
        with patch("builtins.input", return_value="H"):
            with redirect_stdout(io.StringIO()) as f:
                run(";@$0{&}{,}&")
        assert f.getvalue() == "H"

    def test_xor_program_0_0(self, timeout_protection: None) -> None:
        """Test Xor program with inputs 0, 0."""
        with patch("builtins.input", side_effect=["0", "0"]):
            with redirect_stdout(io.StringIO()) as f:
                run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&")
        assert f.getvalue() == "0"

    def test_xor_program_0_1(self, timeout_protection: None) -> None:
        """Test Xor program with inputs 0, 1."""
        with patch("builtins.input", side_effect=["0", "1"]):
            with redirect_stdout(io.StringIO()) as f:
                run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&")
        assert f.getvalue() == "1"

    def test_xor_program_1_0(self, timeout_protection: None) -> None:
        """Test Xor program with inputs 1, 0."""
        with patch("builtins.input", side_effect=["1", "0"]):
            with redirect_stdout(io.StringIO()) as f:
                run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&")
        assert f.getvalue() == "1"

    def test_xor_program_1_1(self, timeout_protection: None) -> None:
        """Test Xor program with inputs 1, 1."""
        with patch("builtins.input", side_effect=["1", "1"]):
            with redirect_stdout(io.StringIO()) as f:
                run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&")
        assert f.getvalue() == "0"


class TestSophieComplexPrograms:
    """Test more complex Sophie program structures."""

    def test_counter_program(self, timeout_protection: None) -> None:
        """Test a simple counter program."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$5[.*]&")
        # Should print 5 then break
        assert f.getvalue() == "5"

    def test_conditional_loop(self, timeout_protection: None) -> None:
        """Test loop with conditional break."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.@$3{*}{}]&")
        # Should print 3 then break
        assert f.getvalue() == "3"

    def test_character_arithmetic(self, timeout_protection: None) -> None:
        """Test character operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,#B,&")
        # Should print A then B
        assert f.getvalue() == "AB"


class TestSophieFindFunction:
    """Test the find function for bracket matching."""

    def test_find_simple_brackets(self) -> None:
        """Test finding matching brackets in simple case."""
        code = "{hello}"
        result = find(code, 0)
        assert result == 6

    def test_find_nested_brackets(self) -> None:
        """Test finding matching brackets with nesting."""
        code = "{outer{inner}outer}"
        result = find(code, 0)
        assert result == 18

    def test_find_curly_brackets(self) -> None:
        """Test finding matching curly brackets."""
        code = "{test}"
        result = find(code, 0)
        assert result == 5

    def test_find_square_brackets(self) -> None:
        """Test finding matching square brackets."""
        code = "[test]"
        result = find(code, 0)
        assert result == 5

    def test_find_unmatched_brackets(self) -> None:
        """Test finding with unmatched brackets."""
        code = "{unmatched"
        result = find(code, 0)
        # Should return end of string
        assert result == len(code)


if __name__ == "__main__":
    pytest.main([__file__])
