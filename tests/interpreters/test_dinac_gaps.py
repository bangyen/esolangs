"""DINAC's rejection paths, which the wiki's examples never take.

The module docstring lists what a malformed program and an invalid
runtime operation each raise; every case listed there is run here.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.other.dinac import _step_value, _Value, run
from tests.interpreters.runner import run_program


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


class TestExpressionErrors:
    def test_an_unclosed_parenthesis_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unclosed parenthesis"):
            _run("OUT (41")

    def test_a_missing_value_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected a value"):
            _run("OUT ~")

    def test_a_bare_quote_at_the_end_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed aschar literal"):
            _run("OUT '")

    def test_a_quote_before_a_delimiter_takes_it_raw(self) -> None:
        # ``' `` is a space literal: the scan stops on the delimiter, so
        # the character after the quote is read directly.
        assert _run("OUT ' ") == " "

    def test_a_non_name_before_a_paren_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a valid function name"):
            _run("OUT 41(41)")

    def test_a_malformed_argument_list_is_refused(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x\nOUT f(41 41)"
        with pytest.raises(ValueError, match="malformed argument list"):
            _run(program)

    def test_trailing_text_is_refused(self) -> None:
        with pytest.raises(ValueError, match="trailing text"):
            _run("OUT 41 41")


class TestStructureErrors:
    def test_a_top_level_indent_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unexpected indent"):
            _run("    OUT 41")

    def test_an_indent_that_jumps_two_levels_is_refused(self) -> None:
        with pytest.raises(ValueError, match="indent jumps"):
            _run("IF 41\n        OUT 41\nELSE\n    OUT 42")

    def test_an_if_without_an_else_is_refused(self) -> None:
        with pytest.raises(ValueError, match="IF without its ELSE"):
            _run("IF 41\n    OUT 41")

    def test_an_if_followed_by_something_else_is_refused(self) -> None:
        with pytest.raises(ValueError, match="IF without its ELSE"):
            _run("IF 41\n    OUT 41\nOUT 42")


class TestDeclarationErrors:
    def test_a_type_name_that_is_not_a_literal_is_refused(self) -> None:
        with pytest.raises(ValueError, match="does not name a type"):
            _run("DEF/zz f x:41\n    GIVE x\nOUT 41")

    def test_a_def_without_a_slash_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed DEF header"):
            _run("DEFX f x:41\n    GIVE x\nOUT 41")

    def test_a_def_without_a_name_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed DEF name"):
            _run("DEF/41 IF x:41\n    GIVE x\nOUT 41")

    def test_a_parameter_without_a_sample_value_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed parameter"):
            _run("DEF/41 f x\n    GIVE 41\nOUT 41")

    def test_a_repeated_parameter_name_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed parameter"):
            _run("DEF/41 f x:41 x:41\n    GIVE 41\nOUT 41")

    def test_the_same_overload_twice_is_refused(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x\nDEF/41 f y:41\n    GIVE y\nOUT 41"
        with pytest.raises(ValueError, match="duplicate overload"):
            _run(program)

    def test_in_needs_a_variable_name(self) -> None:
        with pytest.raises(ValueError, match="IN needs a variable name"):
            _run("IN 41")

    def test_a_set_without_a_colon_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed SET"):
            _run("SET x 41")


class TestRuntimeErrors:
    def test_stepping_a_snuval_halts(self) -> None:
        with pytest.raises(HaltError, match="cannot apply"):
            _step_value(_Value("snuval", 0), "+")

    def test_assigning_to_an_undeclared_name_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared name"):
            _run("x . 41")

    def test_reading_into_an_undeclared_name_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared name"):
            _run("IN x", "41\n")

    def test_reading_into_a_snuval_halts(self) -> None:
        with pytest.raises(HaltError, match="has no type to read into"):
            _run("SET x:41\nx . $\nIN x", "41\n")

    def test_give_outside_a_function_halts(self) -> None:
        with pytest.raises(HaltError, match="GIVE outside a function"):
            _run("GIVE 41")


class TestCallRewriting:
    """A call in argument position is stepped and rewritten in place."""

    def test_a_call_under_a_negation_returns(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x\nOUT ~f(00)"
        assert _run(program) == "01"

    def test_a_call_under_a_step_returns(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x\nOUT f(41)+"
        assert _run(program) == "42"

    def test_a_call_on_each_side_of_a_comparison_returns(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x\nOUT f(41)=f(41)"
        assert _run(program) == "01"

    def test_a_call_inside_a_call_returns(self) -> None:
        program = "DEF/41 f x:41\n    GIVE x+\nOUT f(f(41))"
        assert _run(program) == "43"
