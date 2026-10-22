"""Tests for the SwitchCase interpreter."""

from esolangs.languages.switchcase.interpreter import run
from esolangs.runtime.io import ScriptedIO


def _output(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_the_page_minsky_increment_runs() -> None:
    """The page's translation: initialize, then increment A twice."""
    code = "$_\n0?=A=B\n$A\n0?+1\n!+1\n$A\n0?+1\n!+1\n$A\n2?@"
    assert _output(code) == "2"


def test_a_jump_skips_the_rest_of_its_arm() -> None:
    assert _output("$_\n0?'3@\n$_\n0?+1\n$_\n0?@") == "0"


def test_a_case_with_no_match_and_no_default_does_nothing() -> None:
    assert _output("$_\n5?+1\n$_\n0?@") == "0"


def test_redefining_a_variable_zeroes_it() -> None:
    assert _output("$_\n0?=A\n$A\n0?+4\n$_\n0?=A\n$A\n0?@") == "0"
