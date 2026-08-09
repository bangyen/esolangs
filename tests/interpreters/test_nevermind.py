"""Unit tests for the Nevermind interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.other.nevermind import run


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestNevermind:
    def test_print(self) -> None:
        assert run_and_capture(["print,hello"]) == "hello\n"

    def test_print_comma_escape(self) -> None:
        assert run_and_capture(["print,Hello*44 World!"]) == "Hello, World!\n"

    def test_print_unicode_digits(self) -> None:
        """Non-ASCII digits stay strings instead of being converted to int."""
        assert run_and_capture(["print,²"]) == "²\n"
        assert run_and_capture(["print,١٢٣"]) == "١٢٣\n"

    def test_make_and_print_variable(self) -> None:
        assert run_and_capture(["make,x,5", "print,$x"]) == "5\n"

    def test_arithmetic(self) -> None:
        code = ["make,x,5", "make,y,3", "make,z,$x,+,$y", "print,$z"]
        assert run_and_capture(code) == "8\n"

    def test_if_true(self) -> None:
        code = ["if,5,>,3", "print,big", "endif", "print,after"]
        assert run_and_capture(code) == "big\nafter\n"

    def test_if_false_skips_body(self) -> None:
        code = ["if,5,<,3", "print,big", "endif", "print,after"]
        assert run_and_capture(code) == "after\n"

    def test_loop(self) -> None:
        assert run_and_capture(["loop,3", "print,x", "endloop"]) == "x\nx\nx\n"

    def test_loop_exit_resumes_after_body(self) -> None:
        """Code after a finished loop still runs (skip flag must reset)."""
        code = ["loop,1", "print,inside", "endloop", "print,after"]
        assert run_and_capture(code) == "inside\nafter\n"

    def test_zero_loop_skips_body(self) -> None:
        """A loop of zero iterations runs nothing but continues after it."""
        code = ["loop,0", "print,x", "endloop", "print,after"]
        assert run_and_capture(code) == "after\n"

    def test_make_string_concatenation(self) -> None:
        """The ++ operator concatenates strings."""
        code = ["make,x,hello", "make,y,world", "make,z,$x,++,$y", "print,$z"]
        assert run_and_capture(code) == "helloworld\n"

    def test_calculator_addition(self) -> None:
        """The calculator example from esolangs.org."""
        code = [
            "make,a,10",
            "make,b,5",
            "make,operation,+",
            "if,$operation,==,+",
            "make,final,$a,+,$b",
            "print,$final",
            "endif",
        ]
        assert run_and_capture(code) == "15\n"

    def test_input_command(self) -> None:
        """Input stores a value in the answer variable."""
        assert (
            run_and_capture(["input,prompt", "print,$answer"], inputs=["hi"]) == "hi\n"
        )

    def test_make_subtract(self) -> None:
        code = ["make,x,10", "make,y,4", "make,z,$x,-,$y", "print,$z"]
        assert run_and_capture(code) == "6\n"

    def test_make_multiply(self) -> None:
        code = ["make,x,3", "make,y,4", "make,z,$x,*,$y", "print,$z"]
        assert run_and_capture(code) == "12\n"

    def test_make_divide(self) -> None:
        code = ["make,x,8", "make,y,2", "make,z,$x,/,$y", "print,$z"]
        assert run_and_capture(code) == "4.0\n"

    def test_nested_if(self) -> None:
        code = ["if,5,>,3", "if,2,>,1", "print,deep", "endif", "endif", "print,done"]
        assert run_and_capture(code) == "deep\ndone\n"

    def test_false_if_skips_nested_block(self) -> None:
        """A false outer if scans past a nested if to the matching endif."""
        code = ["if,5,<,3", "if,2,>,1", "print,deep", "endif", "endif", "print,done"]
        assert run_and_capture(code) == "done\n"

    def test_unmatched_if_scans_off_end(self) -> None:
        """A false if with no matching endif halts cleanly."""
        assert run_and_capture(["if,5,<,3", "print,x"]) == ""

    def test_loop_with_nested_if(self) -> None:
        code = ["loop,2", "if,1,>,0", "print,x", "endif", "endloop"]
        assert run_and_capture(code) == "x\nx\n"
