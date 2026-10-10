"""Alight paths the wiki's three examples never take."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.runner import run_program

_ID = "func f{a};end a;"
_ECHO = "func f{a};out a;end a;"
# ``=`` compares any two values; a guard of left skips the next command.
_HEAD = "begin;var l;set l [1, 2];var b;set b 66;var a;set a 65;"
_TAIL = ";out b;out a;end;"


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        # A user call suspends the reduction wherever it sits.
        pytest.param(
            ["begin;var l;set l [f{65}, 66];var c;set c at{l, 0.5};out c;end;", _ID],
            "A",
            id="call_inside_a_list_literal",
        ),
        pytest.param(
            [
                "begin;var l;set l [f{65}, g{66}];var c;set c at{l, 1.5};out c;end;",
                _ID,
                "func g{a};end a;",
            ],
            "B",
            id="call_before_another_item_leaves_the_rest",
        ),
        pytest.param(
            ["begin;var l;set l [f{65}];var v;set v len{l}+64;out v;end;", _ID],
            "A",
            id="call_inside_a_builtin_argument",
        ),
        # The outer call keeps its unreduced arguments while the inner runs.
        pytest.param(
            [
                "begin;var v;set v add{f{64}, 1};out v;end;",
                _ID,
                "func add{a, b};end a+b;",
            ],
            "A",
            id="call_in_a_user_calls_argument_row",
        ),
        pytest.param(
            ["begin;var c;set c 65;f{c};out c;end;", _ID],
            "A",
            id="bare_call_statement_runs_for_its_effect",
        ),
        # Exact rationals: 0.1+0.2 = 0.3 holds, so the skip passes over "out b".
        pytest.param(
            [
                "begin;var a;set a 65;var b;set b 66;var x;set x 0.1+0.2;"
                "skip x = 0.3;out b;out a;end;"
            ],
            "A",
            id="arithmetic_is_exact",
        ),
        # 10**5000 / 10**4999 + 55 = 65; a float literal overflowed to inf.
        pytest.param(
            [f"begin;var x;set x 1{'0' * 5000}/1{'0' * 4999}+55;out x;end;"],
            "A",
            id="literal_past_the_float_range_is_exact",
        ),
        # ``len{l, n}`` appends n nils; 0, outside "positive", pads nothing.
        pytest.param(
            [
                'begin;var l;set l len{"A", 0};set l len{l, 2};var c;'
                "set c len{l}+62;skip at{l, 2.5} = nil;out l;out c;end;"
            ],
            "A",
            id="len_pads_with_nil_and_accepts_zero",
        ),
        # ``'`` escapes only outside a string; "a'" is the list ['a, 39].
        pytest.param(
            ['begin;var l;set l "a\'";var c;set c at{l, 1.5};out c;end;'],
            "'",
            id="apostrophe_inside_a_string",
        ),
        # Wiki: "Whitespace is allowed in a command where it does not split
        # an identifier" -- a tab, not just a space.
        pytest.param(["begin;var c;set c\t65;out c;end;"], "A", id="tab_is_whitespace"),
        # Names are alphanumeric; ``2f{65}`` is a call, not the number 2.
        pytest.param(
            ["begin;var c;set c 2f{65};out c;end;", "func 2f{a};end a;"],
            "A",
            id="function_name_may_start_with_a_digit",
        ),
        # ``²`` is alphanumeric but not a decimal digit: a variable name.
        pytest.param(
            ["begin;var ²;set ² 65;var c;set c ²;out c;end;"],
            "A",
            id="non_decimal_digit_is_an_identifier",
        ),
        # ``len{[f{65}]}`` as a command runs f; it used to hit "unresolved call".
        pytest.param(
            ["begin;len{[f{65}]};end;", _ECHO], "A", id="bare_builtin_resolves_a_call"
        ),
        pytest.param([_HEAD + "skip l = [1, 2]" + _TAIL], "A", id="equal_lists"),
        pytest.param([_HEAD + "skip l = [1, 2, 3]" + _TAIL], "BA", id="longer_list"),
        pytest.param([_HEAD + "skip l = [1, 3]" + _TAIL], "BA", id="other_list"),
        # f returns right, so !f{right} is left and the skip passes over out 66.
        pytest.param(
            [
                "begin;var b;set b 66;var a;set a 65;skip !f{right};out b;out a;end;",
                _ID,
            ],
            "A",
            id="not_negates_a_call_result",
        ),
        pytest.param(
            [
                "begin;var l;set l [[65], [f{66}]];var m;set m at{l, 1.5};"
                "var c;set c at{m, 0.5};out c;end;",
                _ID,
            ],
            "B",
            id="call_after_a_callfree_nested_list",
        ),
    ],
)
def test_output(program: list[str], expected: str) -> None:
    assert run_program(run, program) == expected


@pytest.mark.parametrize(
    ("program", "error", "match"),
    [
        # Wiki: lists "may contain either numbers or other lists (but not both)".
        (["begin;var l;set l [65, [66]];end;"], HaltError, "wrong type"),
        (["begin;set ;end;"], ValueError, "bad variable name"),
        (["begin;f{65} 3;end;", _ID], ValueError, "unknown command"),
    ],
)
def test_rejected(program: list[str], error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        run_program(run, program)


@pytest.mark.parametrize(
    ("program", "error"),
    [
        # An undeclared target and trailing text are rejected before f prints.
        (["begin;set q f{65};end;", _ECHO], HaltError),
        (["begin;turn f{65} 3;end;", _ECHO], ValueError),
        # Left to right: 1/0 halts before f{65} is called and prints.
        (["begin;var x;set x 1/0+f{65};end;", _ECHO], HaltError),
    ],
)
def test_fails_before_printing(program: list[str], error: type[Exception]) -> None:
    io = ScriptedIO("")
    with pytest.raises(error):
        run(program, io)
    assert io.getvalue() == ""
