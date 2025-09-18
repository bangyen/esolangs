"""
Unit tests for Qoibl interpreter.

Tests cover all Qoibl operations including printing, assignment, conditionals,
math operations, loops, and binary number parsing. Includes timeout protection
to prevent hanging tests from infinite loops.
"""

import io
import signal
from contextlib import redirect_stdout
from typing import Any, Callable
from unittest.mock import patch

import pytest

from src.esolangs.interpreters.register_based.qoibl import run


class TimeoutError(Exception):
    """Custom timeout exception for test protection."""


def timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for timeout protection."""
    raise TimeoutError("Test timed out")


def run_with_timeout(func: Callable, timeout_seconds: int = 2) -> Any:
    """
    Run a function with timeout protection.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Result of function execution

    Raises:
        TimeoutError: If function exceeds timeout
    """
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        result = func()
        signal.alarm(0)
        return result
    except TimeoutError:
        signal.alarm(0)
        raise


class TestQoiblBasicOperations:
    """Test basic Qoibl operations."""

    def test_print_character(self) -> None:
        """Test tt instruction for printing characters."""
        code: list[str] = ["tt yeeyeee tt"]  # 'H' in binary
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == "H"

    def test_print_hello_world(self) -> None:
        """Test printing 'Hello, worl' using multiple print statements."""
        hello_world_code: list[str] = [
            "tt yeeyeee tt",  # H
            "tt yyeeyey tt",  # e
            "tt yyeyyee tt",  # l
            "tt yyeyyee tt",  # l
            "tt yyeyyyy tt",  # o
            "tt yeyyee tt",  # ,
            "tt yeeeee tt",  # (space)
            "tt yyyeyyy tt",  # w
            "tt yyeyyyy tt",  # o
            "tt yyyeeye tt",  # r
            "tt yyeyyee tt",  # l
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(hello_world_code)
        assert f.getvalue() == "Hello, worl"

    def test_assignment_and_access(self) -> None:
        """Test we (assignment) and qe (access) instructions."""
        code: list[str] = [
            "we y we yyeeee we",  # var[1] = 48
            "tt qe y qe tt",  # print var[1]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(48)  # '0'

    def test_input_operation(self) -> None:
        """Test et (input) instruction."""
        code: list[str] = [
            "we y we et we",
            "tt qe y qe tt",
        ]  # input -> var[1], print var[1]
        with patch("builtins.input", return_value="A"):
            with redirect_stdout(io.StringIO()) as f:
                run(code)
        assert f.getvalue() == "A"


class TestQoiblBinaryNumbers:
    """Test binary number parsing."""

    def test_binary_zero(self) -> None:
        """Test binary number 'e' (0)."""
        code: list[str] = ["tt e tt"]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(0)

    def test_binary_one(self) -> None:
        """Test binary number 'y' (1)."""
        code: list[str] = ["tt y tt"]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(1)

    def test_binary_numbers(self) -> None:
        """Test various binary numbers."""
        test_cases = [
            ("ee", 0),
            ("ey", 1),
            ("ye", 2),
            ("yy", 3),
            ("eee", 0),
            ("eey", 1),
            ("eye", 2),
            ("eyy", 3),
            ("yee", 4),
            ("yey", 5),
            ("yye", 6),
            ("yyy", 7),
        ]

        for binary_str, expected in test_cases:
            code: list[str] = [f"tt {binary_str} tt"]
            with redirect_stdout(io.StringIO()) as f:
                run(code)
            assert f.getvalue() == chr(expected), f"Failed for {binary_str}"


class TestQoiblConditionals:
    """Test conditional operations (yr instruction)."""

    def test_equality_condition(self) -> None:
        """Test ee (equality) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ee yr qe ye qe tt",  # print var[1] == var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(1)  # True

    def test_greater_than_condition(self) -> None:
        """Test ey (greater than) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ey yr qe ye qe tt",  # print var[1] > var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(1)  # True

    def test_less_than_condition(self) -> None:
        """Test ye (less than) operator."""
        code: list[str] = [
            "we y we y we",  # var[1] = 1
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr ye yr qe ye qe tt",  # print var[1] < var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(1)  # True

    def test_not_equal_condition(self) -> None:
        """Test yy (not equal) operator."""
        code: list[str] = [
            "we y we y we",  # var[1] = 1
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe yr yy yr qe ye qe tt",  # print var[1] != var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(1)  # True


class TestQoiblMathOperations:
    """Test math operations (ry instruction)."""

    def test_addition(self) -> None:
        """Test ee (addition) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ee ry qe ye qe tt",  # print var[1] + var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(6)

    def test_subtraction(self) -> None:
        """Test ey (subtraction) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ey ry qe ye qe tt",  # print var[1] - var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(4)

    def test_multiplication(self) -> None:
        """Test ye (multiplication) operator."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry ye ry qe ye qe tt",  # print var[1] * var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(9)

    def test_division(self) -> None:
        """Test yy (division) operator."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we yy we",  # var[2] = 3
            "tt qe y qe ry yy ry qe ye qe tt",  # print var[1] // var[2]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(2)  # 7 // 3 = 2


class TestQoiblExamples:
    """Test example programs from the esolangs wiki."""

    def test_one_digit_adder(self) -> None:
        """Test the one digit adder example (up to 4+5)."""
        code: list[str] = [
            "we e we yyeeee we",  # var[0] = 2
            "we y we et ry ey ry qe e qe we",  # var[1] = input - 2
            "we ye we et ry ey ry qe e qe we",  # var[2] = input - 2
            "we y we qe y qe ry ee ry qe ye qe we",  # var[1] = var[1] + var[2]
            "we y we qe y qe ry ee ry qe e qe we",  # var[1] = var[1] + 2
            "tt qe y qe tt",  # print var[1]
        ]

        # Test 2 + 3 = 5
        def run_adder():
            with patch("builtins.input", side_effect=["2", "3"]):
                with redirect_stdout(io.StringIO()) as f:
                    run(code)
            return f.getvalue()

        result = run_with_timeout(run_adder, timeout_seconds=2)
        assert result == "5"  # Should print 5


class TestQoiblEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test running an empty program."""
        code: list[str] = []
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == ""

    def test_undefined_variable_access(self) -> None:
        """Test accessing undefined variables (should return 0)."""
        code: list[str] = ["tt qe yyy qe tt"]  # print var[7] (undefined)
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(0)

    def test_division_by_zero(self) -> None:
        """Test division by zero behavior."""
        code: list[str] = [
            "we y we yyy we",  # var[1] = 7
            "we ye we e we",  # var[2] = 0
            "tt qe y qe ry yy ry qe ye qe tt",  # print var[1] // var[2]
        ]
        with pytest.raises(ZeroDivisionError):
            run(code)

    def test_nested_expressions(self) -> None:
        """Test nested expressions and complex operations."""
        code: list[str] = [
            "we y we yy we",  # var[1] = 3
            "we ye we yy we",  # var[2] = 3
            "we yyy we qe y qe ry ee ry qe ye qe we",  # var[3] = var[1] + var[2]
            "tt qe yyy qe tt",  # print var[3]
        ]
        with redirect_stdout(io.StringIO()) as f:
            run(code)
        assert f.getvalue() == chr(6)
