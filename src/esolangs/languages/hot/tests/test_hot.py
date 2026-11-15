"""Tests for the Hot interpreter."""

import pytest

from esolangs.languages.hot.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.support.vm_support import (
    assert_rejected_input_retry,
    assert_rejected_output_retry,
)


@pytest.mark.medium
def test_rejected_input_stays_with_the_failed_step() -> None:
    assert_rejected_input_retry(
        "Hot",
        "A(S(S(SKK)(K(D(DC))))(K(D(CC))))",
        "20",
        "0",
        "1",
        position=1,
        reads=1,
        rejected="2",
    )


def test_a_starved_head_gets_f_appended() -> None:
    """``K`` takes two arguments, so the run starts as ``K F F``."""
    machine = _Machine("K", ScriptedIO())
    assert machine.stack == ["K", "F", "F"]
    machine.step()
    assert machine.stack == ["F", "F"]

    from .oracle_checks import check_raw_hot

    check_raw_hot()


def test_rejected_output_keeps_the_framing_bit(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_rejected_output_retry(
        "Hot", "D(D(C(C K)))", "1", "1", prefix=1, monkeypatch=monkeypatch
    )


def test_an_unmatched_close_is_refused() -> None:
    with pytest.raises(ValueError, match="no matching"):
        run("K)", ScriptedIO())


def test_the_empty_program_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one combinator"):
        run(" \n", ScriptedIO())
