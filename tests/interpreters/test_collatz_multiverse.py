"""Unit tests for the Collatz Multiverse interpreter.

Tests cover the Collatz rule (odd/even branches, 0 treated as odd), DO/NOT
printing, variables, arrays, the special variables (negativeOne, lineNumber,
input), and the documented error cases.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.collatz_multiverse import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


# Sets up one=1, two=2, three=3 from the auto-initialized 0 and negativeOne=-1.
CONSTANTS = "\n".join(
    [
        "one = negativeOne x + negativeOne, NOT PRINT.",
        "one = negativeOne x + zero, NOT PRINT.",
        "two = negativeOne x + negativeOne, NOT PRINT.",
        "two = negativeOne x + one, NOT PRINT.",
        "three = negativeOne x + one, NOT PRINT.",
        "three = one x + two, NOT PRINT.",
    ]
)


class TestCollatzRule:
    def test_odd_rule_multiplies_and_adds(self) -> None:
        # n: 0 -> 3 (copy) -> 7 (3*2+1), then 7 is odd -> 7*3+1 = 22
        program = CONSTANTS + "\n".join(
            [
                "",
                "n = negativeOne x + three, NOT PRINT.",
                "n = two x + one, NOT PRINT.",
                "n = three x + one, DO PRINT.",
                "n = three x + one, DO PRINT.",
            ]
        )
        # 22 (odd branch), then 22 is even -> halved to 11
        assert run_program(program) == "\x16\x0b"

    def test_even_rule_halves(self) -> None:
        # x: 0 -> -1, then -1 is odd -> (-1)*(-1)+1 = 2
        # then 2 is even -> halved to 1
        program = CONSTANTS + "\n".join(
            [
                "",
                "x = negativeOne x + negativeOne, NOT PRINT.",
                "x = negativeOne x + one, NOT PRINT.",
                "x = one x + one, DO PRINT.",
            ]
        )
        assert run_program(program) == "\x01"

    def test_zero_is_treated_as_odd(self) -> None:
        # x starts 0, treated as odd: 0*(-1)+(-1) = -1
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"

    def test_copy_from_a_variable(self) -> None:
        # x starts 0, treated as odd: 0*(-1)+one = 1
        assert run_program(CONSTANTS + "\nx = negativeOne x + one, DO PRINT.") == "\x01"


class TestPrinting:
    def test_not_suppresses_output(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "x = negativeOne x + one, NOT PRINT.",
                "x = one x + zero, DO PRINT.",
            ]
        )
        # x = 1, then 1 is odd -> 1*1+0 = 1
        assert run_program(program) == "\x01"

    def test_print_wraps_to_byte(self) -> None:
        # x = 0*(-1)+(-1) = -1 -> low byte is 255
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"
        assert run_program("x = negativeOne x + negativeOne, NOT PRINT.") == ""


class TestVariables:
    def test_variables_auto_init_to_zero(self) -> None:
        # y and z start 0, x starts 0 (odd) -> 0*0+0 = 0
        assert run_program("x = y x + z, DO PRINT.") == "\x00"

    def test_negative_one_constant(self) -> None:
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"


class TestArrays:
    def test_bare_array_is_element_zero(self) -> None:
        # arr acts as arr[0]: 0 (odd) -> 0*(-1)+one = 1
        program = CONSTANTS + "\narr = negativeOne x + one, DO PRINT."
        assert run_program(program) == "\x01"

    def test_indexed_and_zero_elements_are_distinct(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "arr[negativeOne] = negativeOne x + one, DO PRINT.",
                "arr = negativeOne x + zero, DO PRINT.",
            ]
        )
        # arr[-1] = 1, arr[0] = 0
        assert run_program(program) == "\x01\x00"

    def test_index_uses_variable_value(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "i = negativeOne x + one, NOT PRINT.",
                "arr[i] = negativeOne x + one, DO PRINT.",
                "arr = negativeOne x + zero, DO PRINT.",
            ]
        )
        # arr[1] = 1, arr[0] = 0 (different cells)
        assert run_program(program) == "\x01\x00"

    def test_read_from_array(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "arr[negativeOne] = negativeOne x + one, NOT PRINT.",
                "x = negativeOne x + arr[negativeOne], DO PRINT.",
            ]
        )
        # x = 0*(-1)+1 = 1
        assert run_program(program) == "\x01"


class TestLineNumber:
    def test_reads_current_line(self) -> None:
        program = "\n".join(
            [
                "a = negativeOne x + lineNumber, DO PRINT.",
                "b = negativeOne x + lineNumber, DO PRINT.",
            ]
        )
        # line 1 -> a = 1, line 2 -> b = 2
        assert run_program(program) == "\x01\x02"

    def test_assignment_jumps(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "lineNumber = one x + two, NOT PRINT.",
                "x = negativeOne x + zero, DO PRINT.",
                "x = negativeOne x + one, DO PRINT.",
            ]
        )
        # line 7 (odd) -> 7*1+2 = 9, jumping over line 8
        assert run_program(program) == "\x01"

    def test_jump_off_program_halts(self) -> None:
        program = "\n".join(
            [
                "lineNumber = negativeOne x + negativeOne, NOT PRINT.",
                "x = negativeOne x + one, DO PRINT.",
            ]
        )
        # line 1 (odd) -> 1*(-1)+(-1) = -2, out of range, halts
        assert run_program(program) == ""


class TestInput:
    def test_input_reads_an_integer(self) -> None:
        # x = 0*(-1)+input = 65 -> 'A'
        assert run_program("x = negativeOne x + input, DO PRINT.", "65") == "A"

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program("x = negativeOne x + input, NOT PRINT.", "")

    def test_input_cannot_be_redefined(self) -> None:
        with pytest.raises(ValueError, match="redefined"):
            run_program("input = negativeOne x + zero, NOT PRINT.")


class TestMalformed:
    def test_numeric_literals_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = 3 x + 1, DO PRINT.")
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + 3, DO PRINT.")

    def test_missing_boolean(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + z.")

    def test_bad_boolean(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + z, MAYBE PRINT.")

    def test_garbage_line(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("hello world")

    def test_empty_program(self) -> None:
        assert run_program("") == ""

    def test_blank_lines_are_skipped(self) -> None:
        program = CONSTANTS + "\n\nx = negativeOne x + one, DO PRINT.\n"
        assert run_program(program) == "\x01"
