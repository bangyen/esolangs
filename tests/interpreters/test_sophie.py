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
from tests.interpreters.contract import CycleContract, SnapshotContract


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

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_number(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$42.&", io=IO())
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_output_char(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_number(self) -> None:
        with (
            patch("builtins.input", return_value="123"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":.&", io=IO())
        assert f.getvalue() == "123"

    @pytest.mark.usefixtures("timeout_protection")
    def test_input_char(self) -> None:
        with (
            patch("builtins.input", return_value="X"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";,&", io=IO())
        assert f.getvalue() == "X"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_char_constant(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#H,&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_load_number_constant(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$65,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_halt_command(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("&.", io=IO())
        # Program halts before reaching output
        assert f.getvalue() == ""


class TestSophieConditionals:

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_true(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_char_conditional_false(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A@B{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_true(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$65{,#C,}&", io=IO())
        assert f.getvalue() == "AC"

    @pytest.mark.usefixtures("timeout_protection")
    def test_number_conditional_false(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$65@$66{.,}{#C,}&", io=IO())
        assert f.getvalue() == "C"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_without_else(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{,&}", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_conditionals(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A@A{@$65{,#B,}}{#C,}&", io=IO())
        assert f.getvalue() == "AB"


class TestSophieLoops:

    @pytest.mark.usefixtures("timeout_protection")
    def test_simple_loop(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.*]&", io=IO())
        # Should print 3 then break
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_loop_with_break(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$1[.*]&", io=IO())
        # Should print 1 then break
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_loops(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[.*]]&", io=IO())
        # Should print A, then B's ASCII value (66), then break
        assert f.getvalue() == "66"

    @pytest.mark.usefixtures("timeout_protection")
    def test_loops_nested_three_deep(self) -> None:
        """Closing a loop pops one frame, not all but the outermost.

        Two levels cannot show the difference: dropping the top of a
        two-frame stack and keeping only its bottom leave the same stack.
        Three levels separate them, and the innermost break prints C.
        """
        with redirect_stdout(io.StringIO()) as f:
            run("#A[#B[#C[.*]]]&", io=IO())
        assert f.getvalue() == "67"


class TestSophieComments:

    @pytest.mark.usefixtures("timeout_protection")
    def test_comment_block(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("{This is a comment}#A,&", io=IO())
        assert f.getvalue() == "A"

    @pytest.mark.usefixtures("timeout_protection")
    def test_nested_comments(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("{Outer{Inner}comment}#A,&", io=IO())
        assert f.getvalue() == "A"


class TestSophieInputHandling:

    @pytest.mark.usefixtures("timeout_protection")
    def test_invalid_number_input(self) -> None:
        with (
            patch("builtins.input", return_value="not_a_number"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42:.&", io=IO())
        # Accumulator should remain 42
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_char_input(self) -> None:
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("#$42;.&", io=IO())
        # Accumulator should remain 42
        assert f.getvalue() == "42"

    @pytest.mark.usefixtures("timeout_protection")
    def test_multiple_inputs(self) -> None:
        with (
            patch("builtins.input", side_effect=["65", "B"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":;,&", io=IO())
        assert f.getvalue() == "B"


class TestSophieEdgeCases:

    @pytest.mark.usefixtures("timeout_protection")
    def test_empty_program(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_program_ending_on_a_load_marker(self) -> None:
        """``#`` and ``#$`` may be the last thing in the program.

        The bracket scan steps over whatever a ``#`` loads, so it has to
        cope with there being nothing left to step over.  Neither form is
        an unmatched bracket, so neither raises.
        """
        for code in ("#", "#$"):
            with redirect_stdout(io.StringIO()) as f:
                run(code, io=IO())
            assert f.getvalue() == "", code

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_bracket_loaded_by_a_marker_is_not_a_bracket(self) -> None:
        """``#[`` loads the ``[`` as data, so no loop is left unmatched."""
        with redirect_stdout(io.StringIO()) as f:
            run("#[", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_the_dollar_form_also_swallows_its_bracket(self) -> None:
        """``#$[`` loads the bracket too: the ``$`` is a marker, not the data.

        Only the plain ``#`` form was covered, so the scan's handling of
        the optional ``$`` went untested -- an advance that stopped on the
        marker, or ran one character past it, leaves the bracket standing
        as structure and the program is rejected.
        """
        with redirect_stdout(io.StringIO()) as f:
            run("#$[", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_marker_loaded_by_a_marker_leaves_the_next_bracket_standing(
        self,
    ) -> None:
        """``#$#`` consumes the second ``#`` as data, so a following ``[`` is real.

        This is the other side of the previous case, and it is what stops
        the scan from swallowing too much: the ``[`` here is structure, so
        it must be reported unmatched.  A scan that steps two characters
        past the marker would eat it and call the program balanced.
        """
        with pytest.raises(ValueError, match="unmatched"):
            run("#$#[", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_a_digit_load_stops_at_the_first_non_digit(self) -> None:
        """``#$1[`` loads the digits only, leaving the bracket as structure.

        The digit form runs a loop of its own, and every existing case ends
        the program on the digits -- so a loop that advanced wrongly, or not
        at all, had nothing to disagree about.  Putting a bracket straight
        after the number makes the stopping point visible: it stays
        unmatched.
        """
        for code in ("#$1[", "#$123["):
            with pytest.raises(ValueError, match="unmatched"):
                run(code, io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A{&", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_square_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A[.*", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_unmatched_closing_brace(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run("#A}", io=IO())

    @pytest.mark.usefixtures("timeout_protection")
    def test_break_outside_loop_halts(self) -> None:
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
        with redirect_stdout(io.StringIO()) as f:
            run("xyz#A,&", io=IO())
        # Only valid commands should execute
        assert f.getvalue() == "A"


class TestSophieExamples:

    @pytest.mark.usefixtures("timeout_protection")
    def test_hello_world(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#H,#e,#l,,#o,#,,# ,#W,#o,#r,#l,#d,#!,&", io=IO())
        assert f.getvalue() == "Hello, World!"

    @pytest.mark.usefixtures("timeout_protection")
    def test_truth_machine_zero(self) -> None:
        with (
            patch("builtins.input", return_value="0"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@1{[,]}{,&}", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_empty(self) -> None:
        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(io.StringIO()) as f,
        ):
            run("[;@$0{&}{,}]", io=IO())
        assert f.getvalue() == ""

    @pytest.mark.usefixtures("timeout_protection")
    def test_cat_program_with_input(self) -> None:
        with (
            patch("builtins.input", return_value="H"),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(";@$0{&}{,}&", io=IO())
        assert f.getvalue() == "H"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_0(self) -> None:
        with (
            patch("builtins.input", side_effect=["0", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_0_1(self) -> None:
        with (
            patch("builtins.input", side_effect=["0", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_0(self) -> None:
        with (
            patch("builtins.input", side_effect=["1", "0"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "1"

    @pytest.mark.usefixtures("timeout_protection")
    def test_xor_program_1_1(self) -> None:
        with (
            patch("builtins.input", side_effect=["1", "1"]),
            redirect_stdout(io.StringIO()) as f,
        ):
            run(":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&", io=IO())
        assert f.getvalue() == "0"


class TestSophieComplexPrograms:

    @pytest.mark.usefixtures("timeout_protection")
    def test_counter_program(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$5[.*]&", io=IO())
        # Should print 5 then break
        assert f.getvalue() == "5"

    @pytest.mark.usefixtures("timeout_protection")
    def test_conditional_loop(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#$3[.@$3{*}{}]&", io=IO())
        # Should print 3 then break
        assert f.getvalue() == "3"

    @pytest.mark.usefixtures("timeout_protection")
    def test_character_arithmetic(self) -> None:
        with redirect_stdout(io.StringIO()) as f:
            run("#A,#B,&", io=IO())
        # Should print A then B
        assert f.getvalue() == "AB"


class TestSophieFindFunction:

    def test_find_simple_brackets(self) -> None:
        code = "{hello}"
        result = find(code, 0)
        assert result == 6

    def test_find_nested_brackets(self) -> None:
        code = "{outer{inner}outer}"
        result = find(code, 0)
        assert result == 18

    def test_find_curly_brackets(self) -> None:
        code = "{test}"
        result = find(code, 0)
        assert result == 5

    def test_find_square_brackets(self) -> None:
        code = "[test]"
        result = find(code, 0)
        assert result == 5

    def test_find_unmatched_brackets(self) -> None:
        code = "{unmatched"
        result = find(code, 0)
        # Should return end of string
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
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.sophie import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "#$5"
    halting_program = "&"
    looping_program = "[]"


if __name__ == "__main__":
    pytest.main([__file__])
