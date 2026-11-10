"""Tests for the SwitchCase interpreter."""

from esolangs.languages.switchcase.interpreter import run
from tests.interpreters.runner import native_runner

_output = native_runner(run)


def test_the_page_minsky_increment_runs() -> None:
    """The page's translation: initialize, then increment A twice."""
    code = "$_\n0?=A=B\n$A\n0?+1\n!+1\n$A\n0?+1\n!+1\n$A\n2?@"
    assert _output(code) == "2"


def test_a_jump_skips_the_rest_of_its_arm() -> None:
    from .oracle_checks import check_raw_switchcase

    check_raw_switchcase()
    assert _output("$_\n0?'3@\n$_\n0?+1\n$_\n0?@") == "0"


def test_a_case_with_no_match_and_no_default_does_nothing(monkeypatch) -> None:
    from esolangs.languages.switchcase import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "SwitchCase",
        "$_\n5?+1\n$_\n0?@",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("", "0"), ("", "0"), ("", "0")),
    )
    assert _output("$_\n5?+1\n$_\n0?@") == "0"


def test_redefining_a_variable_zeroes_it() -> None:
    assert _output("$_\n0?=A\n$A\n0?+4\n$_\n0?=A\n$A\n0?@") == "0"
