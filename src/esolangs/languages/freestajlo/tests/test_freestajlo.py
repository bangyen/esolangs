"""Tests for the Freestajlo interpreter."""

import pytest

from esolangs.languages.freestajlo.interpreter import run
from esolangs.runtime.io import ScriptedIO


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1 2 3 1&::::", "2321"),  # & copies the item that deep, 0 the top
        ("5 6 7 9 2~::::", "7695"),  # ~ inserts 9 two items down
        ("1 2|:::", "221"),
        ("3 4`:", "-8"),
        ("7_3%: 7 3_%: 7_2/:", "2-2-3"),  # % takes a's sign, / truncates
        ("2 10^: 2 1_^:", "10240"),
        ('"ab":::', "97980"),  # the first character ends on top, 0 under
    ],
)
def test_arithmetic_and_stack_commands(code: str, expected: str) -> None:
    assert _out(code) == expected


def test_stacks_are_separate_and_the_transfer_stack_carries_values() -> None:
    assert _out("1!5 0!(:1!$)0!(:") == "05"


def test_a_function_runs_where_it_is_named() -> None:
    assert _out("f{'a.}ff") == "aa"
