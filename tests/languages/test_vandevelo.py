"""Vandevelo through the shared API, CLI and machinery."""

from dataclasses import replace

import pytest

import esolangs
from esolangs import _isolated
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES
from tests.vm.test_memory_budget import _BUDGET, _LINUX


@pytest.mark.medium
def test_termination_polarity_comes_from_the_registry(monkeypatch) -> None:
    language = LANGUAGES["Vandevelo"]
    program = esolangs.generate("Vandevelo", "0110")
    monkeypatch.setitem(
        LANGUAGES,
        "Vandevelo",
        replace(
            language,
            contract=replace(language.contract, answer_values=("diverges", "halts")),
        ),
    )
    assert _evaluate("Vandevelo", program, inputs=2) == "1001"


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_budget_allows_answers_and_bound_language() -> None:
    bound = esolangs.Language("brainfuck")
    assert bound.run("+.", isolated=True, max_memory=_BUDGET, max_output=1) == "\x01"
    for language in ("brainfuck", "Vandevelo"):
        source = esolangs.generate(language, "0110")
        assert (
            _evaluate(language, source, inputs=2, isolated=True, max_memory=_BUDGET)
            == "0110"
        )


@pytest.mark.medium
@pytest.mark.parametrize("language", ["brainfuck", "Vandevelo"])
def test_evaluation_forwards_budget_without_changing_answers(
    monkeypatch, language
) -> None:
    # Exercise plumbing on every host; the Linux-only tests enforce a real cap.
    monkeypatch.setattr(_isolated.sys, "platform", "linux")
    calls = []
    target = esolangs if language == "brainfuck" else _isolated
    attribute = "_run_isolated" if language == "brainfuck" else "termination_isolated"
    runner = getattr(target, attribute)

    def capture(*args, **kwargs):
        calls.append(kwargs.pop("max_memory"))
        return runner(*args, **kwargs)

    monkeypatch.setattr(target, attribute, capture)
    bound = esolangs.Language(language)
    assert (
        _evaluate(
            bound.name,
            bound.generate("0110"),
            inputs=2,
            isolated=True,
            max_memory=_BUDGET,
        )
        == "0110"
    )
    assert calls == [_BUDGET] * 4


@pytest.mark.medium
def test_finite_timeout_has_no_boolean_verdict(capsys, monkeypatch) -> None:
    from esolangs import cli_run
    from tests.cli.test_cli import call_main
    from tests.support import divergence

    finite = "a ~> Nil?\n" * 20000
    assert esolangs.run("Vandevelo", finite, timeout=1) == ""
    monkeypatch.setattr(divergence, "_CYCLE_STEPS", 8)
    assert divergence.diverges("Vandevelo", finite, "") is None
    with pytest.raises(esolangs.ExecutionTimeoutError):
        divergence.terminates("Vandevelo", finite, "", 0.001)
    # CI hit the 1ms source-read deadline before execution; test its verdict.
    monkeypatch.setattr(cli_run, "_read_program", lambda *_args, **_kwargs: finite)
    monkeypatch.setattr(cli_run, "_read_stdin", lambda *_args, **_kwargs: "")
    with pytest.raises(SystemExit) as exc:
        call_main(
            ["run", "Vandevelo", "finite.vand", "--timeout", "0.001"], capsys, stdin=""
        )
    assert exc.value.code == 124
    error = capsys.readouterr().err
    assert "answer is undecided" in error
    assert "answer 1" not in error
