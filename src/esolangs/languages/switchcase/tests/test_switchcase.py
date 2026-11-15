"""Tests for the SwitchCase interpreter."""

import pytest

from esolangs import InputExhaustedError, Language
from esolangs.languages.switchcase.interpreter import run
from tests.interpreters.runner import native_runner
from tests.support.vm_support import (
    assert_rejected_input_retry,
    assert_rejected_output_retry,
)

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


def test_wide_arithmetic_and_numeric_output_ignore_the_host_digit_cap() -> None:
    from tests.support.execution import assert_digit_cap_independent

    digits = "9" * 641
    jump = "0" * 640 + "2"
    source = f"$_\n0?'{jump}\n$_\n0?+{digits}@\n$_\n{digits}?-{digits}@"
    assert_digit_cap_independent("SwitchCase", source, "", digits + "0")
    assert_digit_cap_independent("SwitchCase", "$_\n0?#@", digits, digits)


def test_rejected_io_stays_at_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "$_\n0?#@"
    assert_rejected_input_retry(
        "SwitchCase", source, "oops 7", "7", "7", position=4, reads=1, prefix=1
    )
    debugger = Language("SwitchCase").make_debugger(source)
    debugger.step()
    boundary = debugger.snapshot()
    for attempts in (1, 2):
        with pytest.raises(InputExhaustedError):
            debugger.step()
        assert debugger.snapshot() == boundary
        assert debugger.observation.input_past_end == attempts
    assert_rejected_output_retry(
        "SwitchCase", "$_\n0?+65.@", "A", "A65", prefix=2, monkeypatch=monkeypatch
    )
    assert_rejected_output_retry(
        "SwitchCase", "$_\n0?+123@", "123", "123", prefix=2, monkeypatch=monkeypatch
    )
