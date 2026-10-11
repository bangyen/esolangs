"""Underload through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from esolangs import _isolated
from esolangs._evaluate import _evaluate
from tests.vm.test_memory_budget import _BUDGET, _LINUX


@pytest.mark.parametrize(
    ("source", "message", "hint"),
    [
        ("X", "unknown Underload command", "use () strings"),
        ("(", "unmatched Underload", "close the string"),
    ],
)
def test_underload_errors_have_the_right_hint(source, message, hint):
    with pytest.raises(esolangs.HaltError, match=message) as caught:
        esolangs.run("Underload", source, timeout=1)
    assert any(hint in note for note in caught.value.__notes__)


def test_underload_literal_text_is_preserved():
    assert esolangs.run("Underload", "(X)S", timeout=1) == "X"


@pytest.mark.medium
def test_memory_probe_template_reaches_execution() -> None:
    assert _evaluate("Underload", _growing_template(3), inputs=1, isolated=True) == "01"


@pytest.mark.parametrize("limit", [0, True, 1.5, "1", 1 << 63])
def test_invalid_memory_budget_precedes_source_reads(limit: object) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_memory"):
        esolangs.run("Underload", Path("missing"), isolated=True, max_memory=limit)


def test_memory_budget_requires_isolation() -> None:
    with pytest.raises(esolangs.ArgumentError, match="isolated"):
        esolangs.run("Underload", Path("missing"), max_memory=_BUDGET)


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_unsupported_platform_refuses_before_acquisition(monkeypatch, platform) -> None:
    monkeypatch.setattr(_isolated.sys, "platform", platform)
    with pytest.raises(esolangs.ArgumentError, match="Linux"):
        _evaluate(
            "Underload", Path("missing"), inputs=1, isolated=True, max_memory=_BUDGET
        )


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_growing_state_fails_and_worker_is_reaped(spawned) -> None:
    source = "(A)S(x)" + ":*" * 29
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit") as caught:
        esolangs.run("Underload", source, isolated=True, timeout=10, max_memory=_BUDGET)
    assert caught.value.partial_output == "A"
    assert spawned[0].poll() is not None
    assert esolangs.run("Underload", "(ok)S", isolated=True, max_memory=_BUDGET) == "ok"


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_memory_failure_during_evaluation_is_not_an_answer() -> None:
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit") as caught:
        _evaluate(
            "Underload",
            _growing_template(29),
            inputs=1,
            isolated=True,
            max_memory=_BUDGET,
        )
    assert "row 0" in " ".join(caught.value.__notes__)
    assert caught.value.partial_output == "0"


def _growing_template(doublings: int) -> str:
    return esolangs.generate("Underload", "01") + "(x)" + ":*" * doublings
