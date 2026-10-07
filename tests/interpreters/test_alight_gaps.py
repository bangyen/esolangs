"""Alight paths the wiki's three examples never take."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import (
    run,
)
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.runner import run_program


def _run(code: list[str], stdin: str = "") -> str:
    return run_program(run, code, stdin)


class TestCallsInsideCompoundExpressions:
    """A user call suspends the reduction wherever it sits."""

    def test_a_call_inside_a_list_literal_returns(self) -> None:
        program = [
            "begin;var l;set l [f{65}, 66];var c;set c at{l, 0.5};out c;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "A"

    def test_a_call_before_another_item_leaves_the_rest(self) -> None:
        program = [
            "begin;var l;set l [f{65}, g{66}];var c;set c at{l, 1.5};out c;end;",
            "func f{a};end a;",
            "func g{a};end a;",
        ]
        assert _run(program) == "B"

    def test_a_call_inside_a_builtin_argument_returns(self) -> None:
        program = [
            "begin;var l;set l [f{65}];var v;set v len{l}+64;out v;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "A"

    def test_a_call_in_a_user_calls_argument_row_suspends_it(self) -> None:
        """The outer call keeps its unreduced arguments while the inner runs."""
        program = [
            "begin;var v;set v add{f{64}, 1};out v;end;",
            "func f{a};end a;",
            "func add{a, b};end a+b;",
        ]
        assert _run(program) == "A"

    def test_a_bare_call_statement_runs_for_its_effect(self) -> None:
        program = [
            "begin;var c;set c 65;f{c};out c;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "A"


def _output_before(error: type[Exception], code: list[str]) -> str:
    """Run ``code`` to ``error`` and return what it printed first."""
    io = ScriptedIO("")
    with pytest.raises(error):
        run(code, io)
    return io.getvalue()


class TestRegressions:
    """One named program per fix; each failed on the pre-fix interpreter."""

    def test_arithmetic_is_exact(self) -> None:
        # Exact rationals: 0.1+0.2 = 0.3 holds, so the skip passes over "out b".
        program = [
            "begin;var a;set a 65;var b;set b 66;var x;set x 0.1+0.2;"
            "skip x = 0.3;out b;out a;end;"
        ]
        assert _run(program) == "A"

    def test_a_literal_past_the_float_range_is_exact(self) -> None:
        # 10**5000 / 10**4999 + 55 = 65; a float literal overflowed to inf.
        big, small = "1" + "0" * 5000, "1" + "0" * 4999
        assert _run([f"begin;var x;set x {big}/{small}+55;out x;end;"]) == "A"

    def test_len_pads_with_nil_and_accepts_a_zero_count(self) -> None:
        """``len{l, n}`` appends n nils; 0, outside "positive", pads nothing."""
        program = [
            'begin;var l;set l len{"A", 0};set l len{l, 2};var c;'
            "set c len{l}+62;skip at{l, 2.5} = nil;out l;out c;end;"
        ]
        assert _run(program) == "A"

    def test_a_list_mixing_numbers_and_lists_halts(self) -> None:
        # Wiki: lists "may contain either numbers or other lists (but not both)".
        with pytest.raises(HaltError, match="wrong type"):
            _run(["begin;var l;set l [65, [66]];end;"])

    def test_an_apostrophe_inside_a_string_is_a_character(self) -> None:
        # ``'`` escapes only outside a string; "a'" is the list ['a, 39].
        program = ['begin;var l;set l "a\'";var c;set c at{l, 1.5};out c;end;']
        assert _run(program) == "'"

    def test_a_tab_is_whitespace_inside_a_command(self) -> None:
        # Wiki: "Whitespace is allowed in a command where it does not split
        # an identifier" -- a tab, not just a space.
        assert _run(["begin;var c;set c\t65;out c;end;"]) == "A"

    def test_a_function_name_may_start_with_a_digit(self) -> None:
        # Names are alphanumeric; ``2f{65}`` is a call, not the number 2.
        program = ["begin;var c;set c 2f{65};out c;end;", "func 2f{a};end a;"]
        assert _run(program) == "A"

    def test_a_non_decimal_digit_is_an_identifier(self) -> None:
        # ``\u00b2`` is alphanumeric but not a decimal digit: a variable name.
        program = ["begin;var \u00b2;set \u00b2 65;var c;set c \u00b2;out c;end;"]
        assert _run(program) == "A"

    def test_a_bare_builtin_call_resolves_a_user_call_inside_it(self) -> None:
        # ``len{[f{65}]}`` as a command runs f; it used to hit "unresolved call".
        program = ["begin;len{[f{65}]};end;", "func f{a};out a;end a;"]
        assert _run(program) == "A"

    def test_a_malformed_command_fails_before_its_call_runs(self) -> None:
        # An undeclared target and trailing text are rejected before f prints.
        callee = "func f{a};out a;end a;"
        assert _output_before(HaltError, ["begin;set q f{65};end;", callee]) == ""
        assert _output_before(ValueError, ["begin;turn f{65} 3;end;", callee]) == ""

    def test_an_operand_left_of_a_call_is_evaluated_first(self) -> None:
        # Left to right: 1/0 halts before f{65} is called and prints.
        program = ["begin;var x;set x 1/0+f{65};end;", "func f{a};out a;end a;"]
        assert _output_before(HaltError, program) == ""


class TestComparisonsAndMalformedCommands:
    """Equality over lists, a call under ``!``, and commands rejected on parse."""

    def test_equal_lists_compare_equal_and_other_lists_do_not(self) -> None:
        # ``=`` compares any two values; a guard of left skips the next command.
        head = "begin;var l;set l [1, 2];var b;set b 66;var a;set a 65;"
        tail = ";out b;out a;end;"
        same = head + "skip l = [1, 2]" + tail
        longer = head + "skip l = [1, 2, 3]" + tail
        other = head + "skip l = [1, 3]" + tail
        assert _run([same]) == "A"
        assert _run([longer]) == "BA"
        assert _run([other]) == "BA"

    def test_not_negates_a_call_result(self) -> None:
        # f returns right, so !f{right} is left and the skip passes over out 66.
        program = [
            "begin;var b;set b 66;var a;set a 65;skip !f{right};out b;out a;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "A"

    def test_a_call_after_a_callfree_nested_list_still_runs(self) -> None:
        program = [
            "begin;var l;set l [[65], [f{66}]];var m;set m at{l, 1.5};"
            "var c;set c at{m, 0.5};out c;end;",
            "func f{a};end a;",
        ]
        assert _run(program) == "B"

    def test_set_without_a_variable_name_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="bad variable name"):
            _run(["begin;set ;end;"])

    def test_text_after_a_bare_call_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown command"):
            _run(["begin;f{65} 3;end;", "func f{a};end a;"])
