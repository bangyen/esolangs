"""Unit tests for the Nevermind interpreter."""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from esolangs.interpreters.other.nevermind import run


def run_and_capture(code: List[str], inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            run(code)
    return buffer.getvalue()


class TestNevermind:
    def test_print(self) -> None:
        assert run_and_capture(["print,hello"]) == "hello\n"

    def test_print_comma_escape(self) -> None:
        assert run_and_capture(["print,Hello*44 World!"]) == "Hello, World!\n"

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
        """input stores a value in the answer variable."""
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

    def test_loop_with_nested_if(self) -> None:
        code = ["loop,2", "if,1,>,0", "print,x", "endif", "endloop"]
        assert run_and_capture(code) == "x\nx\n"
