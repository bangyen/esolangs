"""Tests for the Kiss interpreter."""

import pytest

from esolangs import ExecutionLimits, ExecutionResult, InputExhaustedError, Language
from esolangs.languages.kiss.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.support.vm_support import (
    assert_rejected_input_retry,
    assert_rejected_output_retry,
)


@pytest.mark.medium
def test_rejected_input_stays_with_the_failed_step() -> None:
    assert_rejected_input_retry(
        "Kiss", "S (K K) (S K)", "20", "0", "0", position=1, reads=1, rejected="2"
    )


def test_k_exits_zero_and_s_exits_nonzero() -> None:
    assert run("K", ScriptedIO()) == 0
    assert run("S", ScriptedIO()) == 1
    from .oracle_checks import check_raw_kiss

    check_raw_kiss()


def test_the_cat_exits_zero_after_echoing(monkeypatch) -> None:
    io = ScriptedIO("1")
    assert run("S (K K) (S K)", io) == 0
    assert io.getvalue() == "1"

    from esolangs.languages.kiss import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Kiss",
        "S (K K) (S K)",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("1", "1"), ("0", "0"), ("1", "1")),
    )


def test_only_the_head_is_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    """The argument ``K K K`` stays unreduced while the head outputs."""
    machine = _Machine("K (K K K)", ScriptedIO())
    machine.step()
    assert machine.stack == ["K", "K", "K"]
    assert_rejected_output_retry(
        "Kiss", "K K", "0", "0", prefix=0, monkeypatch=monkeypatch
    )


@pytest.mark.medium
@pytest.mark.parametrize(("stdin", "position"), [("1", 1), ("1\n1", 2)])
def test_bit_input_ends_at_physical_eof_or_newline(stdin, position) -> None:
    api = Language("Kiss")
    source = "S (K K) (S (K K) (S K))"
    for limits, steps in (
        (None, None),
        (ExecutionLimits(max_steps=4), 1),
        (ExecutionLimits(max_steps=4, total_timeout=5), 1),
    ):
        outcome = api.run(source, stdin=stdin, limits=limits)
        assert isinstance(outcome.error, InputExhaustedError)
        assert (outcome.error.reads, outcome.error.supplied, outcome.error.unit) == (
            1,
            1,
            "bit",
        )
        assert outcome.observation == ExecutionResult(
            "", position, position, 1, steps=steps
        )

    debugger = api.make_debugger(source, stdin=stdin)
    debugger.step()
    with pytest.raises(InputExhaustedError):
        debugger.step()
    sealed = debugger.snapshot()
    with pytest.raises(InputExhaustedError) as caught:
        debugger.step()
    assert caught.value.observation == ExecutionResult(
        "", position, position, 2, steps=1
    )
    assert debugger.snapshot() == sealed
    assert api.run(source, stdin="11\n").unwrap().output == "1"


def test_the_empty_program_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one combinator"):
        run(" \n", ScriptedIO())
