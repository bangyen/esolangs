"""Unit tests for the ZTOALC L interpreter.

ZTOALC L executes lines in Collatz-trajectory order determined by the initial
pointer value. With pointer 3, lines are visited in the order 2, 4, 3, 1.
"""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from esolangs.interpreters.other.ztoalc import run


def run_and_capture(code: List[str], inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            run(code)
    return buffer.getvalue()


class TestZTOALC:
    def test_print_constant(self) -> None:
        assert run_and_capture(["10", "print 65"]) == "A"

    def test_print_other_constant(self) -> None:
        assert run_and_capture(["2", "print 66"]) == "B"


class TestZTOALCVariables:
    """Lines are visited in Collatz order: 2 (assign), 4 (arith), 3 (print), 1."""

    def test_assignment_and_subtract(self) -> None:
        """x = 66, x - 1, print x -> 'A'."""
        code = ["3", "jump x 0", "x = 66", "print x", "x - 1"]
        assert run_and_capture(code) == "A"

    def test_assignment_and_add(self) -> None:
        code = ["3", "jump x 0", "x = 66", "print x", "x + 1"]
        assert run_and_capture(code) == "C"

    def test_input(self) -> None:
        """x = input reads a character, then arithmetic applies."""
        code = ["3", "jump x 0", "x = input", "print x", "x - 1"]
        assert run_and_capture(code, inputs=["A"]) == "@"

    def test_array_creation_and_indexing(self) -> None:
        """x = [3] creates a zeroed array; y = x[1] indexes it."""
        code = ["3", "jump y 0", "x = [3]", "print y", "y = x[1]"]
        assert run_and_capture(code) == "\x00"

    def test_negative_literal(self) -> None:
        """x = -5 then x + 8 gives 3."""
        code = ["3", "jump x 0", "x = -5", "print x", "x + 8"]
        assert run_and_capture(code) == "\x03"
