"""Unit tests for the EGL interpreter."""

import pytest

from esolangs.interpreters.grid_based.egl import _advance, run
from esolangs.interpreters.io import ScriptedIO


def execute(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_documented_examples() -> None:
    assert execute("10,10:v>>_++=") == "2"
    assert execute("10,1:++(>+++++<-)>=") == "10"


def test_numeric_input() -> None:
    assert execute("1,1:x=", "42\n") == "42"


def test_grid_output() -> None:
    assert execute("2,2:+>++v+++#") == "|1|2|\n|0|3|\n"


def test_reflections() -> None:
    assert execute("1,4:v+_=") == "0"
    assert execute("4,1:>+|=") == "0"
    assert execute("4,4:v>+%=") == "0"


def test_loop_tests_its_declaration_cell() -> None:
    assert execute("2,1:+(->)=") == "0"


def test_transition_does_not_mutate_its_input() -> None:
    state = (0, 0, 0, (0, 0), ())
    advanced, output = _advance(state, "+", {}, 2, 1)
    assert state == (0, 0, 0, (0, 0), ())
    assert advanced == (1, 0, 0, (1, 0), ())
    assert output is None


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("", "must begin"),
        ("0,1:", "dimensions must be positive"),
        ("1,1:(", "unmatched parenthesis"),
        ("1,1:>", "moved outside"),
    ],
)
def test_malformed_program(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(code)
