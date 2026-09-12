r"""Unit tests for Sophie interpreter."""

import io
import signal
from collections.abc import Generator
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.sophie import find, run
from tests.interpreters.contract import CycleContract, SnapshotContract


class _TestTimeoutError(Exception):
    r"""Custom timeout exception for test protection."""


def timeout_handler(_signum: int, _frame: object) -> None:
    r"""Signal handler for test timeouts."""
    raise _TestTimeoutError("Test timed out")


@pytest.fixture
def timeout_protection() -> Generator[None, None, None]:
    r"""Fixture to add timeout protection to tests."""
    # Set up timeout handler.
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5 second timeout.

    yield

    # Clean up.
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old_handler)


class TestSophieBasicCommands:
    r"""Test basic Sophie command functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_number(self) -> None:
        r"""Test ."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$42.&", io=IO())
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_char(self) -> None:
        r"""Test , command outputs accumulator as character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_number(self) -> None:
        r"""Test : command inputs number to accumulator."""
        with (
            patch("builtins.input", return_value="123"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":.&", io=IO())
        assert f.getvalue() == "123"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_char(self) -> None:
        r"""Test ; command inputs character to accumulator."""
        with (
            patch("builtins.input", return_value="X"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";,&", io=IO())
        assert f.getvalue() == "X"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_char_constant(self) -> None:
        r"""Test #c command loads character constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_number_constant(self) -> None:
        r"""Test #$n command loads number constant into accumulator."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_halt_command(self) -> None:
        r"""Test & command halts the program."""
        with redirect_stdout(io.StringIO()) as f:
            run("&.", io=IO())
        # Program halts before reaching.
        assert f.getvalue() == ""


class TestSophieConditionals:
    r"""Test Sophie conditional statement functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_true(self) -> None:
        r"""Test @c{} conditional when accumulator matches character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_false(self) -> None:
        r"""Test @c{} conditional when accumulator doesn't match character."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_true(self) -> None:
        r"""Test @$n{} conditional when accumulator matches number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$65{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_false(self) -> None:
        r"""Test @$n{} conditional when accumulator doesn't match number."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_without_else(self) -> None:
        r"""Test conditional without else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,&}", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_conditionals(self) -> None:
        r"""Test nested conditional statements."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{@$65{,#B,}}{#C,}&", io=IO())
        assert f.getvalue() == "AB"


class TestSophieLoops:
    r"""Test Sophie loop functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_simple_loop(self) -> None:
        r"""Test basic loop structure."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.*]&", io=IO())
        # Should print 3 then break.
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_loop_with_break(self) -> None:
        r"""Test loop with break statement."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$1[.*]&", io=IO())
        # Should print 1 then break.
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_loops(self) -> None:
        r"""Test nested loop structures."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[.*]]&", io=IO())
        # Should print A, then B's.
        assert f.getvalue() == "66"

    @pytest.mark.usefixtures("timeout_protection")
    def test_loops_nested_three_deep(self) -> None:
        r"""Closing a loop pops one frame, not all but the outermost."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[#C[.*]]]&", io=IO())
        assert f.getvalue() == "67"


class TestSophieComments:
    r"""Test Sophie comment functionality."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_comment_block(self) -> None:
        r"""Test comment blocks are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("{This is a comment}#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_comments(self) -> None:
        r"""Test nested comment blocks."""
        with redirect_stdout(io.StringIO()) as f:
            run("{Outer{Inner}comment}#A,&", io=IO())
        assert f.getvalue() == "A"


class TestSophieInputHandling:
    r"""Test Sophie input handling and edge cases."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_invalid_number_input(self) -> None:
        r"""Test invalid number input leaves accumulator unchanged."""
        with (
            patch("builtins.input", return_value="not_a_number"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42:.&", io=IO())
        # Accumulator should remain 42.
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_char_input(self) -> None:
        r"""Test empty character input."""
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42;.&", io=IO())
        # Accumulator should remain 42.
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_multiple_inputs(self) -> None:
        r"""Test multiple input commands."""
        with (
            patch("builtins.input", side_effect=["65", "B"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":;,&", io=IO())
        assert f.getvalue() == "B"


class TestSophieEdgeCases:
    r"""Test Sophie edge cases and error conditions."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_program(self) -> None:
        r"""Test that empty program produces no output."""
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_program_ending_on_a_load_marker(self) -> None:
        r"""``#`` and ``#$`` may be the last thing in the program."""
        for code in ("#", "#$"):
            with redirect_stdout(io.StringIO()) as f:
                run(code, io=IO())
            assert f.getvalue() == "", code

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_bracket_loaded_by_a_marker_is_not_a_bracket(self) -> None:
        r"""``#[`` loads the ``[`` as data, so no loop is left unmatched."""
        with redirect_stdout(io.StringIO()) as f:
            run("#[", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_the_dollar_form_also_swallows_its_bracket(self) -> None:
        r"""``#$[`` loads the bracket too: the ``$`` is a marker, not the data."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$[", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_marker_loaded_by_a_marker_leaves_the_next_bracket_standing(
        self,
    ) -> None:
        r"""``#$#`` consumes the second ``#`` as data, so a following ``[`` is."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#$#[", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_digit_load_stops_at_the_first_non_digit(self) -> None:
        r"""``#$1[`` loads the digits only, leaving the bracket as structure."""
        for code in ("#$1[", "#$123["):
            with pytest.raises(ValueError, match="unmatched"):
                run(code, io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_brackets(self) -> None:
        r"""Test program with unmatched brackets."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A{&", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_square_brackets(self) -> None:
        r"""Test program with an unmatched loop bracket."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A[.*", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_closing_brace(self) -> None:
        r"""Test program with an unmatched closing brace."""
        with pytest.raises(ValueError, match="unmatched"):
            run("#A}", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_break_outside_loop_halts(self) -> None:
        r"""Test a break with no enclosing loop."""
        with pytest.raises(HaltError):
            run("*&", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_braces_loaded_as_data(self) -> None:
        r"""Brackets loaded as ``#`` data are not treated as structure."""
        with redirect_stdout(io.StringIO()) as f:
            run("#{,", io=IO())
        assert f.getvalue() == "{"


class TestMiscCommands:
    @pytest.mark.usefixtures("timeout_protection")
    def test_dollar_char_loaded_as_data(self) -> None:
        r"""A ``#$<char>`` load skips the character as data."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$A,", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_number_no_else(self) -> None:
        r"""A number conditional that fails and has no else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{,#C,}", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_char_no_else(self) -> None:
        r"""A char conditional that fails and has no else block."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{,#C,}", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_invalid_commands_ignored(self) -> None:
        r"""Test that invalid commands are ignored."""
        with redirect_stdout(io.StringIO()) as f:
            run("xyz#A,&", io=IO())
        # Only valid commands should.
        assert f.getvalue() == "A"


class TestSophieExamples:
    r"""Test Sophie example programs from the wiki."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_hello_world(self) -> None:
        r"""Test Hello World program from Sophie wiki."""
        with redirect_stdout(io.StringIO()) as f:
            run("#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&", io=IO())
        assert f.getvalue() == "Hello, World!"

    @pytest.mark.usefixtures("timeout_protection")
    def test_truth_machine_zero(self) -> None:
        r"""Test Truth Machine with input 0."""
        with (
            patch("builtins.input", return_value="0"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@1{[,]}{,&}", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_empty(self) -> None:
        r"""Test Cat program with empty input."""
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("[;@$0{&}{,}]", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_with_input(self) -> None:
        r"""Test Cat program with input."""
        with (
            patch("builtins.input", return_value="H"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@$0{&}{,}&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_0(self) -> None:
        r"""Test Xor program with inputs 0, 0."""
        with (
            patch("builtins.input", side_effect=["0", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_1(self) -> None:
        r"""Test Xor program with inputs 0, 1."""
        with (
            patch("builtins.input", side_effect=["0", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_0(self) -> None:
        r"""Test Xor program with inputs 1, 0."""
        with (
            patch("builtins.input", side_effect=["1", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_1(self) -> None:
        r"""Test Xor program with inputs 1, 1."""
        with (
            patch("builtins.input", side_effect=["1", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"


class TestSophieComplexPrograms:
    r"""Test more complex Sophie program structures."""

    @pytest.mark.usefixtures("timeout_protection")
    def test_counter_program(self) -> None:
        r"""Test a simple counter program."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$5[.*]&", io=IO())
        # Should print 5 then break.
        assert f.getvalue() == "5"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_loop(self) -> None:
        r"""Test loop with conditional break."""
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.@$3{*}{}]&", io=IO())
        # Should print 3 then break.
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_character_arithmetic(self) -> None:
        r"""Test character operations."""
        with redirect_stdout(io.StringIO()) as f:
            run("#A,#B,&", io=IO())
        # Should print A then B.
        assert f.getvalue() == "AB"


class TestSophieFindFunction:
    r"""Test the find function for bracket matching."""

    def test_find_simple_brackets(self) -> None:
        r"""Test finding matching brackets in simple case."""
        code = "{hello}"
        result = find(code, 0)
        assert result == 6

    def test_find_nested_brackets(self) -> None:
        r"""Test finding matching brackets with nesting."""
        code = "{outer{inner}outer}"
        result = find(code, 0)
        assert result == 18

    def test_find_curly_brackets(self) -> None:
        r"""Test finding matching curly brackets."""
        code = "{test}"
        result = find(code, 0)
        assert result == 5

    def test_find_square_brackets(self) -> None:
        r"""Test finding matching square brackets."""
        code = "[test]"
        result = find(code, 0)
        assert result == 5

    def test_find_unmatched_brackets(self) -> None:
        r"""Test finding with unmatched brackets."""
        code = "{unmatched"
        result = find(code, 0)
        # Should return end of string.
        assert result == len(code)


class TestStepMachine:
    def test_halt_command_sets_halted(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("&", IO())
        assert not machine.halted
        machine.step()
        assert machine.halted

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.sophie import _Machine

        machine = _Machine("", IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.halted


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.sophie import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "#$5"
    halting_program = "&"
    looping_program = "[]"


if __name__ == "__main__":
    pytest.main([__file__])
