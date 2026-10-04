"""Algebraic diagnostics and public empty-program contract."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.other.algebraic_programming_language import run
from tests.interpreters.contract import EmptyProgramContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(program: str, stdin: str = "") -> str:
    return run_program(run, program, stdin)


class TestErrors:
    def test_bracket_multiplication_is_rejected(self) -> None:
        with raises_message(ValueError, "bracket multiplication is invalid syntax"):
            run_and_capture("1(2)")

    def test_an_unknown_variable_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown variable 'q'"):
            run_and_capture("F() = q\nF()")

    def test_an_unknown_function_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown function 'G'"):
            run_and_capture("G()")

    def test_a_bare_unknown_function_name_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown function 'G'"):
            run_and_capture("F(x) = 1\nF(G)")

    def test_the_wrong_argument_count_is_rejected(self) -> None:
        with raises_message(ValueError, "'F' takes 1 argument(s), got 2"):
            run_and_capture("F(x) = x\nF(1, 2)")

    def test_an_unbalanced_bracket_is_rejected(self) -> None:
        with raises_message(ValueError, "expected ')'"):
            run_and_capture("(1 + 2")

    def test_an_unbalanced_brace_is_rejected(self) -> None:
        with raises_message(ValueError, "unbalanced { in program"):
            run_and_capture("F() = {\n1")

    def test_trailing_input_is_rejected(self) -> None:
        with raises_message(ValueError, "trailing input at ')'"):
            run_and_capture("1 + 2)")

    def test_an_empty_expression_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected end of expression"):
            run_and_capture("1 +")

    def test_a_bad_parameter_is_rejected(self) -> None:
        with raises_message(ValueError, "bad parameter '1'"):
            run_and_capture("F(1) = 2\nF(3)")

    def test_an_operator_with_no_arguments_is_rejected(self) -> None:
        with raises_message(ValueError, "operator '##' takes no arguments"):
            run_and_capture("## = 2\n1")

    def test_an_operator_repeating_a_parameter_is_rejected(self) -> None:
        with raises_message(ValueError, "operator 'a#a' repeats a parameter"):
            run_and_capture("a#a = 2\n1")

    def test_division_by_zero_is_a_halt(self) -> None:
        with raises_message(HaltError, "division by zero"):
            run_and_capture("1 / 0")

    def test_modulo_by_zero_is_a_halt(self) -> None:
        with raises_message(HaltError, "modulo by zero"):
            run_and_capture("1 % 0")

    def test_zero_to_a_negative_power_is_a_halt(self) -> None:
        with raises_message(HaltError, "zero to a negative power"):
            run_and_capture("0 ** -1")

    def test_non_numeric_input_is_a_halt(self) -> None:
        with raises_message(HaltError, "input 'oops' is not a number"):
            run_and_capture("n", "oops\n")

    def test_arithmetic_on_a_function_is_a_halt(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("F() = 1\nF + 1")

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program(run, "a + b", "1\n", suppress_eof=False)

    def test_a_definition_with_no_left_hand_side_is_rejected(self) -> None:
        with raises_message(ValueError, "definition has no left-hand side"):
            run_and_capture("= 2")

    def test_a_malformed_function_header_is_rejected(self) -> None:
        with raises_message(ValueError, "malformed function header 'F1'"):
            run_and_capture("F1 = 2\n1")


class TestContract(EmptyProgramContract):
    run = staticmethod(run_and_capture)
    empty_program = ""
    empty_output = ""


class TestCoveragePaths:
    def test_an_operator_argument_slot_with_nothing_after_it(self) -> None:
        with raises_message(ValueError, "trailing input at '#'"):
            run_and_capture("a # b = a\n1 #")

    def test_a_stray_comma_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected token ','"):
            run_and_capture(",")

    def test_a_bare_return_operator_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected end of expression"):
            run_and_capture("$")

    def test_trailing_input_in_a_function_header_is_rejected(self) -> None:
        with raises_message(ValueError, "trailing input in header 'F(x) y'"):
            run_and_capture("F(x) y = 1\n1")

    def test_a_digit_leading_operator_pattern_is_rejected(self) -> None:
        with raises_message(ValueError, "bad operator pattern '1a'"):
            run_and_capture("1a = 2\n1")

    def test_trailing_input_after_a_block_is_rejected(self) -> None:
        with raises_message(ValueError, "trailing input after block in '{1} 2'"):
            run_and_capture("F() = {1} 2\nF()")


class TestGuardsAndBoundaries:
    def test_a_dot_with_no_digit_after_it_is_its_own_token(self) -> None:
        with raises_message(ValueError, "trailing input at '.'"):
            run_and_capture("3.")

    def test_a_dot_before_a_letter_is_not_a_decimal_point(self) -> None:
        with raises_message(ValueError, "trailing input at '.'"):
            run_and_capture("3.a")

    def test_arithmetic_on_a_function_names_the_value_it_refused(self) -> None:
        with raises_message(HaltError, "expected a number, got <F/1>"):
            run_and_capture("F(x) = x\n1 + F")
