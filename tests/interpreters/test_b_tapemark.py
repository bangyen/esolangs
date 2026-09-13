"""Unit tests for the B-tapemark interpreter."""

import pytest

from esolangs.interpreters.grid_based.b_tapemark import _advance, _load, run
from esolangs.interpreters.io import ScriptedIO


def execute(source: str, stdin: str = "") -> str:
    """Run ``source`` and return its output."""
    io = ScriptedIO(stdin)
    run(source, io)
    return io.getvalue()


def test_documented_hello_world() -> None:
    assert execute(">HELLO+WORLD!") == "HELLO WORLD"


def test_documented_cat() -> None:
    io = ScriptedIO("A\nB\n")
    with pytest.raises(EOFError):
        run("/>-+|\\\n\\    /", io)
    assert io.getvalue() == "AB"


def test_copy_and_character_input() -> None:
    assert execute(">*A+!") == "A"
    assert execute(">-+!", "Z\n") == "Z"


def test_quoted_text_is_blank() -> None:
    assert execute('>A"IGNORED"B!') == "AB"


def test_transition_does_not_mutate_its_input() -> None:
    state = _load(">*A!")
    advanced, output = _advance(state)
    assert state == _load(">*A!")
    assert advanced != state
    assert output is None


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("!", "exactly one start"),
        ("> <!", "exactly one start"),
        ('>"', "unmatched quote"),
        (">a!", "invalid.*'a'"),
        (">²!", "invalid.*'²'"),
    ],
)
def test_malformed_program(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        execute(source)
