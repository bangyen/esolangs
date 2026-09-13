"""Unit tests for the EGL interpreter."""

import pytest

from esolangs.interpreters.grid_based.egl import run
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


@pytest.mark.parametrize("code", ["", "0,1:", "1,1:(", "1,1:>"])
def test_malformed_program(code: str) -> None:
    with pytest.raises(ValueError):
        execute(code)
