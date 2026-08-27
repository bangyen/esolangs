"""Unit tests for the Eval interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.eval import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestEval:
    def test_hello_world(self) -> None:
        assert run_and_capture('"Hello, World!".') == "Hello, World!"

    def test_push_zero_increment(self) -> None:
        assert run_and_capture("0+.") == "1"

    def test_stringmode_backtick(self) -> None:
        """A backtick inside stringmode becomes a double quote."""
        assert run_and_capture('"`".') == '"'

    def test_charmode(self) -> None:
        """' wraps the string in double quotes."""
        assert run_and_capture("'ab\".") == '"ab"'

    def test_move_between_stacks(self) -> None:
        """= moves a value to the other stack; ~ switches the current stack."""
        assert run_and_capture("0=~.") == "0"

    def test_pointer_check(self) -> None:
        assert run_and_capture("0`0`+.") == "2"

    def test_truth_machine(self) -> None:
        assert run_and_capture('"0+.^!"^0?!0.') == "0"

    def test_duplicate(self) -> None:
        """^ copies the top without removing it, so it can be printed twice.

        Nothing used ``^`` except the truth machine, where its result is
        consumed by ``!`` rather than shown -- so the command could have
        done nothing at all.
        """
        assert run_and_capture("0+^..") == "11"

    def test_decrement(self) -> None:
        """- subtracts one, where + adds it."""
        assert run_and_capture("0-.") == "-1"
        assert run_and_capture("0--.") == "-2"
        assert run_and_capture("0+-.") == "0"

    def test_pop_discards_the_top(self) -> None:
        """; drops the top value, leaving the one beneath it."""
        assert run_and_capture("0+0+;.") == "1"

    def test_reverse_turns_the_stack_over(self) -> None:
        """* reverses the current stack, so the bottom becomes the top."""
        assert run_and_capture("0+0*.") == "1"
        assert run_and_capture("0+0+*..") == "11"

    def test_backtick_pushes_the_stack_index(self) -> None:
        """` pushes which stack is *not* current -- 1 on the first, 0 on the
        second.

        ``test_pointer_check`` adds two of them together, where pushing the
        current index instead sums to 0 rather than 2 -- but nothing showed
        the value itself, or that it follows the switch.
        """
        assert run_and_capture("`.") == "1"
        assert run_and_capture("~`.") == "0"

    def test_move_targets_the_other_stack(self) -> None:
        """= puts the value on the stack that is not current.

        ``test_move_between_stacks`` moves a 0 and prints a 0, which the
        same program prints whether or not the move happened.  Moving a 1
        and finding it only after ``~`` shows where it went.
        """
        assert run_and_capture("0+=~.") == "1"

    def test_output_on_empty_stack_halts(self) -> None:
        """Reading a value that is not there is an invalid operation."""
        for code in (".", ";", "^"):
            with pytest.raises(HaltError):
                run(code, IO())

    def test_eval_string_halts_on_non_string(self) -> None:
        """! on a non-string value is an invalid operation."""
        with pytest.raises(HaltError):
            run("0!", IO())

    def test_eval_string_evaluates_program(self) -> None:
        """! evaluates a pushed string as a program."""
        assert run_and_capture('"0+."!') == "1"

    def test_arithmetic_on_string_halts(self) -> None:
        """+ on a non-numeric top is an invalid operation."""
        with pytest.raises(HaltError):
            run('"abc"+', IO())
