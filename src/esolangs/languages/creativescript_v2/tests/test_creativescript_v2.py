"""Tests for the CreativeScript v2 interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.creativescript_v2.interpreter import run
from esolangs.runtime.io import ScriptedIO

#: The page's equality program, as a function of two inputs.
EQUALS = """in! a
in! b
set! one 1
sub! a b diff
mul! diff diff sq
add! sq one sq_plus1
add! sq sq_plus1 temp
sub! temp one temp_minus1
div! temp_minus1 sq_plus1 neq
sub! one neq eq
out! eq"""


def output(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(3, 3, "1"), (3, 4, "0"), (4, 3, "0"), (0, 0, "1"), (-2, 5, "0"), (7, -7, "0")],
)
def test_the_pages_equality_program_needs_floor_division(
    a: int, b: int, expected: str
) -> None:
    assert output(EQUALS, f"{a}\n{b}\n") == expected


def test_say_prints_the_rest_of_the_line_and_a_plus_b_adds() -> None:
    assert output("say! Hello world!") == "Hello world!"
    assert output("in! a\nin! b\nadd! a b c\nout! c", "2\n40\n") == "42"


def test_division_and_modulo_floor() -> None:
    code = "set! n -7\nset! d 2\ndiv! n d q\nmod! n d r\nout! q\nsay! ,\nout! r"
    assert output(code) == "-4,1"


def test_division_by_zero_and_unset_variables_halt() -> None:
    with pytest.raises(HaltError):
        output("set! a 1\nset! z 0\ndiv! a z c")
    with pytest.raises(HaltError):
        output("out! never")


@pytest.mark.parametrize(
    ("code", "match"),
    [
        ("add! a 1 c", "needs a variable"),
        ("set! 3 4", "needs a variable"),
        ("jump! 2", "not a CreativeScript v2 command"),
        ("add! a b", "takes 3 operands"),
        ("out! 5", "needs a variable"),
    ],
)
def test_malformed_programs_are_refused(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        output(code)
