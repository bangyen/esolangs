"""Unit tests for the Grapheme interpreter.

Covers the mode system (string/int/function), the arithmetic and stack
commands, variables, function execution, truthiness-driven skips, and the
documented error conventions.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.grapheme import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestModes:
    def test_stringmode(self) -> None:
        # E HELLOWORLD E Y -> the E's terminate the string, dropping one E
        assert run_program("EHLLOWORLDEY") == "HLLOWORLD"

    def test_stringmode_accumulates_to_end(self) -> None:
        # no closing E: the string is flushed at end of program
        assert run_program("EAY") == ""

    def test_intmode(self) -> None:
        # F A F -> 10; F B F -> 20; A adds; Y prints
        assert run_program("FAFFBFAY") == "30"

    def test_intmode_empty_is_zero(self) -> None:
        assert run_program("FFY") == "0"

    def test_funcmode(self) -> None:
        # H Y H makes a function of Y; I runs it on the pushed 10
        assert run_program("FAFHYHIE") == "10"


class TestArithmetic:
    def test_add(self) -> None:
        assert run_program("FAFFBFAY") == "30"

    def test_subtract(self) -> None:
        assert run_program("FAFFBFBY") == "-10"

    def test_multiply(self) -> None:
        assert run_program("FAFFBFSY") == "200"

    def test_floor_divide(self) -> None:
        assert run_program("FCFFBFRY") == "1"

    def test_string_math_uses_ords(self) -> None:
        # "A" (65) + "A" (65) = 130
        assert run_program("EAEEAEAY") == "130"

    def test_divide_by_zero_halts(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run_program("FFFFR")


class TestStack:
    def test_duplicate(self) -> None:
        assert run_program("FAFKYY") == "1010"

    def test_swap(self) -> None:
        assert run_program("FAFFBFLYY") == "1020"

    def test_reverse(self) -> None:
        assert run_program("EABEECDEPYY") == "ABCD"

    def test_pop(self) -> None:
        assert run_program("EAEM") == ""

    def test_truthiness_to_number(self) -> None:
        assert run_program("FAFTY") == "0"  # 10 is truthy -> push 0
        assert run_program("FFTY") == "1"  # 0 is falsy -> push 1


class TestStrings:
    def test_length(self) -> None:
        assert run_program("EAEOY") == "1"

    def test_int_to_string(self) -> None:
        # 10 -> digits 1,0 -> "AJ"
        assert run_program("FAFNY") == "AJ"

    def test_string_to_int(self) -> None:
        # J on "AJ" parses intmode-style: A=1, J=10 -> (0+1)*10=10, (10+10)*10=200
        assert run_program("EAJEJY") == "200"

    def test_function_to_string(self) -> None:
        assert run_program("HABHNY") == "AB"


class TestVariables:
    def test_set_and_get(self) -> None:
        assert run_program("EAEKKCDY") == "A"

    def test_undeclared_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_program("EAED")


class TestFunctions:
    def test_g_executes_string(self) -> None:
        assert run_program("FAFEYEG") == "10"

    def test_g_on_input_with_bad_commands_rejected(self) -> None:
        """A string read from input and executed via G is validated, not asserted on."""
        import pytest

        with pytest.raises(ValueError, match="unhandled command"):
            run_program("WG", "zkg")

    def test_i_runs_function(self) -> None:
        assert run_program("FAFHYHIE") == "10"

    def test_z_runs_while_stack_nonempty(self) -> None:
        assert run_program("FAFHYHZ") == "10"

    def test_q_conditional_execution(self) -> None:
        # truthy 10 on the stack, fn Y: Q pops fn and the 10, then Y pops empty
        with pytest.raises(HaltError, match="popped"):
            run_program("FAFHYHQ")


class TestSkips:
    def test_u_skips_when_falsy(self) -> None:
        # [10, 0]: U pops 0 (falsy) and skips the K, so Y prints the 10
        assert run_program("FAFFFUKY") == "10"

    def test_u_does_not_skip_when_truthy(self) -> None:
        # [0, 10]: U pops 10 (truthy), K duplicates the 0, Y prints it
        assert run_program("FFFAFUKY") == "0"

    def test_x_skips_next_when_falsy(self) -> None:
        # [10, 0]: X pops 0 (falsy) and skips the K, so Y prints the 10
        assert run_program("FAFFFXKY") == "10"

    def test_x_skips_after_next_when_truthy(self) -> None:
        # [0, 10]: X pops 10 (truthy), Y prints the 0, then the K is skipped
        assert run_program("FFFAFXYK") == "0"


class TestIO:
    def test_input(self) -> None:
        assert run_program("WKY", "hi") == "hi"

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run("W", ScriptedIO(""))


class TestErrors:
    def test_pop_empty_halts(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("AB")

    def test_lowercase_rejected(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            run_program("hello")

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestEdgeCases:
    def test_j_on_an_int_is_identity(self) -> None:
        assert run_program("FAFJJY") == "10"

    def test_j_on_a_function_counts_its_commands(self) -> None:
        assert run_program("HABHJY") == "2"

    def test_j_on_a_string_stops_at_an_f(self) -> None:
        assert run_program("EFAEJY") == "0"

    def test_n_on_a_string_is_identity(self) -> None:
        assert run_program("EAENY") == "A"

    def test_n_on_zero_is_j(self) -> None:
        assert run_program("FFNY") == "J"

    def test_math_on_a_function_halts(self) -> None:
        with pytest.raises(HaltError, match="math on a function"):
            run_program("HABHFFA")

    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0
        assert run_program("EETY") == "1"  # "" falsy -> push 1
        assert run_program("HABHTY") == "0"  # nonempty function truthy
        assert run_program("HHTY") == "1"  # empty function falsy

    def test_recursion_limit_exceeded(self) -> None:
        with pytest.raises(HaltError, match="recursion"):
            run_program("HKGHKG")

    def test_command_limit_exceeded(self) -> None:
        from esolangs.interpreters.other.grapheme import run

        io = ScriptedIO("")
        with pytest.raises(HaltError, match="command limit"):
            run("FF", io, limit=1)

    def test_function_cannot_name_a_variable(self) -> None:
        with pytest.raises(HaltError, match="cannot name"):
            run_program("FAFHHC")
        with pytest.raises(HaltError, match="cannot name"):
            run_program("FAFHHD")

    def test_g_needs_a_string_or_function(self) -> None:
        with pytest.raises(HaltError, match="G needs"):
            run_program("FAFG")

    def test_i_pushes_back_a_non_function(self) -> None:
        assert run_program("FAFIY") == "10"

    def test_v_branches_on_a_falsy_value(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("FFFFVY")

    def test_y_cannot_output_a_function(self) -> None:
        with pytest.raises(HaltError, match="Y cannot"):
            run_program("HABHY")

    def test_unterminated_int_mode(self) -> None:
        assert run_program("F") == ""

    def test_unterminated_func_mode(self) -> None:
        assert run_program("H") == ""
