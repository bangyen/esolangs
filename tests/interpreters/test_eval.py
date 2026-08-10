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

    def test_eval_string_halts_on_non_string(self) -> None:
        """! on a non-string value is an invalid operation."""
        with pytest.raises(HaltError):
            run("0!", IO())

    def test_eval_string_evaluates_program(self) -> None:
        """! evaluates a pushed string as a program."""
        assert run_and_capture('"0+."!') == "1"
