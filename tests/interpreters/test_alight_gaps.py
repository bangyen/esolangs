"""Alight paths the wiki's three examples never take.

A call suspending a list or an argument row is run as a real grid.
``_replace_first`` and ``_first_call_or_none`` are pure functions over
parsed expression tuples, and reaching each of their arms through the
grid would mean laying out a 2D program per arm, so those are called on
the node shapes ``_Parser`` emits.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import (
    _command_expr,
    _first_call_or_none,
    _replace_first,
    run,
)
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.runner import run_program


def _run(code: list[str], stdin: str = "") -> str:
    return run_program(run, code, stdin)


class TestCallsInsideCompoundExpressions:
    """A user call suspends the reduction wherever it sits.

    ``_reduce`` returns the partly-reduced expression with the rest of
    the list or argument row still to do, so these run the real grid
    rather than a constructed node.
    """

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
        """The outer call keeps its unreduced arguments while the inner runs.

        Two arguments, the first a call: the reduction returns with the
        second still to do, which is the row a single-argument call never
        exercises.
        """
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


class TestReplaceFirst:
    """The first unresolved call becomes a ``val`` node; the rest stand."""

    def test_a_leaf_holds_no_call(self) -> None:
        assert _replace_first(("num", 1.0), 9.0) == (("num", 1.0), False)

    def test_a_call_becomes_the_value(self) -> None:
        assert _replace_first(("call", "f", []), 9.0) == (("val", 9.0), True)

    def test_a_call_under_a_negation_is_replaced(self) -> None:
        node = ("not", ("call", "f", []))
        assert _replace_first(node, 9.0) == (("not", ("val", 9.0)), True)

    def test_a_negation_over_a_leaf_replaces_nothing(self) -> None:
        node = ("not", ("num", 1.0))
        assert _replace_first(node, 9.0) == (("not", ("num", 1.0)), False)

    def test_the_left_operand_is_replaced_first(self) -> None:
        node = ("bin", "+", ("call", "f", []), ("call", "g", []))
        replaced, done = _replace_first(node, 9.0)
        assert done is True
        assert replaced == ("bin", "+", ("val", 9.0), ("call", "g", []))

    def test_the_right_operand_is_replaced_when_the_left_has_none(self) -> None:
        node = ("bin", "+", ("num", 1.0), ("call", "g", []))
        replaced, done = _replace_first(node, 9.0)
        assert done is True
        assert replaced == ("bin", "+", ("num", 1.0), ("val", 9.0))

    def test_a_call_inside_a_list_is_replaced(self) -> None:
        node = ("list", [("num", 1.0), ("call", "f", [])])
        replaced, done = _replace_first(node, 9.0)
        assert done is True
        assert replaced == ("list", [("num", 1.0), ("val", 9.0)])

    def test_a_list_of_leaves_replaces_nothing(self) -> None:
        node = ("list", [("num", 1.0), ("num", 2.0)])
        assert _replace_first(node, 9.0) == (
            ("list", [("num", 1.0), ("num", 2.0)]),
            False,
        )

    def test_a_call_in_an_argument_is_replaced_before_the_call(self) -> None:
        node = ("call", "outer", [("call", "inner", [])])
        replaced, done = _replace_first(node, 9.0)
        assert done is True
        assert replaced == ("call", "outer", [("val", 9.0)])


class TestCommandExpression:
    """Which commands carry an expression, and which evaluate nothing."""

    def test_a_declaration_evaluates_nothing(self) -> None:
        assert _command_expr("var c", "var") is None

    def test_a_bare_call_is_its_own_expression(self) -> None:
        assert _command_expr("f{}", "f") == ("call", "f", [])

    def test_a_word_that_is_neither_evaluates_nothing(self) -> None:
        # No brace, so it is not a call; not a keyword, so it carries no
        # expression either.
        assert _command_expr("out c", "out") is None

    def test_a_keyword_carries_its_expression(self) -> None:
        assert _command_expr("skip 1", "skip") == ("num", 1.0)

    def test_set_names_a_variable_then_evaluates(self) -> None:
        assert _command_expr("set x 1", "set") == ("num", 1.0)

    def test_a_bare_end_evaluates_nothing(self) -> None:
        assert _command_expr("end", "end") is None


class TestFirstCall:
    """The leftmost call to a given name, searched in evaluation order."""

    def test_a_leaf_holds_no_call(self) -> None:
        assert _first_call_or_none(("num", 1.0), "f") is None

    def test_a_call_to_another_name_is_not_found(self) -> None:
        assert _first_call_or_none(("call", "g", []), "f") is None

    def test_a_call_under_a_negation_is_found(self) -> None:
        node = ("call", "f", [])
        assert _first_call_or_none(("not", node), "f") == node

    def test_the_left_operand_is_searched_first(self) -> None:
        left = ("call", "f", [])
        node = ("bin", "+", left, ("call", "f", []))
        assert _first_call_or_none(node, "f") is left

    def test_the_right_operand_is_searched_next(self) -> None:
        right = ("call", "f", [])
        node = ("bin", "+", ("num", 1.0), right)
        assert _first_call_or_none(node, "f") is right

    def test_a_call_inside_a_list_is_found(self) -> None:
        wanted = ("call", "f", [])
        node = ("list", [("num", 1.0), wanted])
        assert _first_call_or_none(node, "f") is wanted

    def test_a_list_without_one_finds_nothing(self) -> None:
        node = ("list", [("num", 1.0), ("num", 2.0)])
        assert _first_call_or_none(node, "f") is None

    def test_an_argument_is_searched_before_the_call_itself(self) -> None:
        inner = ("call", "f", [])
        node = ("call", "f", [inner])
        assert _first_call_or_none(node, "f") is inner


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
