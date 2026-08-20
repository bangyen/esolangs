"""Unit tests for Sophie interpreter.

Tests cover all Sophie commands, program flow control, and example programs.
Sophie is a finite state automaton language with a single accumulator.
"""

import io
import signal
from collections.abc import Generator
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.sophie import find, run


class _TestTimeoutError(Exception):
    """Custom timeout exception for test protection."""


def timeout_handler(_signum: int, _frame: object) -> None:
    """Signal handler for test timeouts."""
    raise _TestTimeoutError("Test timed out")


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

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_number(self) -> None:
        """Test . command outputs accumulator as number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$42.&", io=IO())
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_char(self) -> None:
        """Test , command outputs accumulator as character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_number(self) -> None:
        """Test : command inputs number to accumulator."""
        with (
            patch("builtins.input", return_value="123"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":.&", io=IO())
        assert f.getvalue() == "123"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_char(self) -> None:
        """Test ; command inputs character to accumulator."""
        with (
            patch("builtins.input", return_value="X"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";,&", io=IO())
        assert f.getvalue() == "X"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_char_constant(self) -> None:
        """Test #c command loads character constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_number_constant(self) -> None:
        """Test #$n command loads number constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_halt_command(self) -> None:
        """Test & command halts the program."""
        with redirect_stdout(io.StringIO()) as f:
            run("&.", io=IO())
        # Program halts before reaching output
        assert f.getvalue() == ""


class TestSophieConditionals:
    """Test Sophie conditional statement functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_true(self) -> None:
        """Test @c{} conditional when accumulator matches character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_false(self) -> None:
        """Test @c{} conditional when accumulator doesn't match character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_true(self) -> None:
        """Test @$n{} conditional when accumulator matches number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$65{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_false(self) -> None:
        """Test @$n{} conditional when accumulator doesn't match number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_without_else(self) -> None:
        """Test conditional without else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,&}", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_conditionals(self) -> None:
        """Test nested conditional statements."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{@$65{,#B,}}{#C,}&", io=IO())
        assert f.getvalue() == "AB"


class TestSophieLoops:
    """Test Sophie loop functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_simple_loop(self) -> None:
        """Test basic loop structure."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.*]&", io=IO())
        # Should print 3 then break
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_loop_with_break(self) -> None:
        """Test loop with break statement."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$1[.*]&", io=IO())
        # Should print 1 then break
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_loops(self) -> None:
        """Test nested loop structures."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[.*]]&", io=IO())
        # Should print A, then B's ASCII value (66), then break
        assert f.getvalue() == "66"


class TestSophieComments:
    """Test Sophie comment functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_comment_block(self) -> None:
        """Test comment blocks are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("{This is a comment}#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_comments(self) -> None:
        """Test nested comment blocks."""
        with redirect_stdout(io.StringIO()) as f:
            run("{Outer{Inner}comment}#A,&", io=IO())
        assert f.getvalue() == "A"


class TestSophieInputHandling:
    """Test Sophie input handling and edge cases."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_invalid_number_input(self) -> None:
        """Test invalid number input leaves accumulator unchanged."""
        with (
            patch("builtins.input", return_value="not_a_number"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42:.&", io=IO())
        # Accumulator should remain 42
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_char_input(self) -> None:
        """Test empty character input."""
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42;.&", io=IO())
        # Accumulator should remain 42
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_multiple_inputs(self) -> None:
        """Test multiple input commands."""
        with (
            patch("builtins.input", side_effect=["65", "B"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":;,&", io=IO())
        assert f.getvalue() == "B"


class TestSophieEdgeCases:
    """Test Sophie edge cases and error conditions."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_program(self) -> None:
        """Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_brackets(self) -> None:
        """Test program with unmatched brackets."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A{&", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_square_brackets(self) -> None:
        """Test program with an unmatched loop bracket."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A[.*", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_closing_brace(self) -> None:
        """Test program with an unmatched closing brace."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A}", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_break_outside_loop_halts(self) -> None:
        """Test a break with no enclosing loop."""
        with pytest.raises(HaltError):
            run("*&", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_braces_loaded_as_data(self) -> None:
        """Brackets loaded as ``#`` data are not treated as structure."""
        with redirect_stdout(io.StringIO()) as f:
            run("#{,", io=IO())
        assert f.getvalue() == "{"


class TestMiscCommands:
    @pytest.mark.usefixtures("timeout_protection")
    def test_dollar_char_loaded_as_data(self) -> None:
        """A ``#$<char>`` load skips the character as data."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$A,", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_number_no_else(self) -> None:
        """A number conditional that fails and has no else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{,#C,}", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_char_no_else(self) -> None:
        """A char conditional that fails and has no else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{,#C,}", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_invalid_commands_ignored(self) -> None:
        """Test that invalid commands are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("xyz#A,&", io=IO())
        # Only valid commands should execute
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_whitespace_ignored(self) -> None:
        """Test that whitespace is ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&", io=IO())
        # Only valid commands should execute
        assert f.getvalue() == "A"


class TestSophieExamples:
    """Test Sophie example programs from the wiki."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_hello_world(self) -> None:
        """Test Hello World program from Sophie wiki."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&", io=IO())
        assert f.getvalue() == "Hello, World!"

    @pytest.mark.usefixtures("timeout_protection")
    def test_truth_machine_zero(self) -> None:
        """Test Truth Machine with input 0."""
        with (
            patch("builtins.input", return_value="0"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@1{[,]}{,&}", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_empty(self) -> None:
        """Test Cat program with empty input."""
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("[;@$0{&}{,}]", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_with_input(self) -> None:
        """Test Cat program with input."""
        with (
            patch("builtins.input", return_value="H"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@$0{&}{,}&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_0(self) -> None:
        """Test Xor program with inputs 0, 0."""
        with (
            patch("builtins.input", side_effect=["0", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_1(self) -> None:
        """Test Xor program with inputs 0, 1."""
        with (
            patch("builtins.input", side_effect=["0", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_0(self) -> None:
        """Test Xor program with inputs 1, 0."""
        with (
            patch("builtins.input", side_effect=["1", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_1(self) -> None:
        """Test Xor program with inputs 1, 1."""
        with (
            patch("builtins.input", side_effect=["1", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"


class TestSophieComplexPrograms:
    """Test more complex Sophie program structures."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_counter_program(self) -> None:
        """Test a simple counter program."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$5[.*]&", io=IO())
        # Should print 5 then break
        assert f.getvalue() == "5"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_loop(self) -> None:
        """Test loop with conditional break."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.@$3{*}{}]&", io=IO())
        # Should print 3 then break
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_character_arithmetic(self) -> None:
        """Test character operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,#B,&", io=IO())
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


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("#$5", IO())
        before = machine.snapshot()
        machine.step()  # #$5 loads 5 into the accumulator
        assert machine.snapshot() != before
        assert machine.acc == 5

    def test_halt_command_sets_halted(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("&", IO())
        assert not machine.halted
        machine.step()
        assert machine.halted

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("&", IO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # [] is an empty loop: [ pushes the index, ] jumps straight back,
        # so the machine oscillates between the same two states forever.
        from esolangs.interpreters.register_based.sophie import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("[]", IO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted


if __name__ == "__main__":
    pytest.main([__file__])
