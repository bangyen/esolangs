"""Evaluation budgets cover acquisition, rows, and suspended iterators."""

import threading
from io import StringIO

import pytest

import esolangs
import esolangs._evaluate as evaluator
from esolangs._evaluate import _evaluate, _iter_evaluate


@pytest.mark.medium
@pytest.mark.parametrize("name", ["brainfuck", "RAM0", "123", "Piet"])
def test_streaming_executes_the_expected_table(name):
    program = esolangs.generate(name, "0110")
    assert "".join(_iter_evaluate(name, program, inputs=2)) == "0110"


def test_row_budget_refuses_before_loading():
    class Unreadable(StringIO):
        def read(self, *_args):
            pytest.fail("source must not load when the table exceeds its budget")

    with pytest.raises(esolangs.InterpreterLimitError, match="max_rows"):
        _evaluate("brainfuck", Unreadable(), inputs=64)


@pytest.mark.parametrize("max_rows", [-1, True, 1.5])
def test_invalid_row_budgets(max_rows):
    with pytest.raises(esolangs.ArgumentError, match="max_rows"):
        _evaluate("brainfuck", ",.", inputs=1, max_rows=max_rows)


@pytest.mark.medium
def test_row_budget_can_be_raised_or_disabled():
    for limit in (2, None):
        assert _evaluate("brainfuck", ",.", inputs=1, max_rows=limit) == "01"
    with pytest.raises(esolangs.InterpreterLimitError):
        _evaluate("brainfuck", ",.", inputs=1, max_rows=1)


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_total_deadline_interrupts_source_acquisition(isolated):
    release = threading.Event()
    finished = threading.Event()

    class Blocked(StringIO):
        def read(self, *_args):
            try:
                release.wait(2)
                return ",."
            finally:
                finished.set()

    try:
        with pytest.raises(esolangs.ExecutionTimeoutError):
            _evaluate(
                "brainfuck", Blocked(), inputs=1, isolated=isolated, total_timeout=0.05
            )
    finally:
        release.set()
        assert finished.wait(2)


@pytest.mark.medium
def test_deadline_includes_iterator_pauses(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(evaluator, "monotonic", lambda: clock[0])
    answers = _iter_evaluate("brainfuck", ",.", inputs=1, total_timeout=5)
    assert next(answers) == "0"
    clock[0] = 6
    with pytest.raises(
        esolangs.ExecutionTimeoutError, match="total deadline"
    ) as caught:
        next(answers)
    assert "row 1 of 2" in " ".join(caught.value.__notes__)


@pytest.mark.medium
def test_deadline_clamps_each_row_and_expires_after_work(monkeypatch):
    clock = [0.0]
    bounds = []
    monkeypatch.setattr(evaluator, "monotonic", lambda: clock[0])

    def run(_name, _source, stdin, timeout):
        bounds.append(timeout)
        clock[0] += 3
        return stdin

    monkeypatch.setattr(esolangs, "run", run)
    with pytest.raises(esolangs.ExecutionTimeoutError):
        _evaluate("brainfuck", ",.", inputs=1, timeout=None, total_timeout=5)
    assert bounds == [5, 2]


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_total_deadline_bounds_a_growing_machine(isolated):
    with pytest.raises(esolangs.ExecutionTimeoutError):
        _evaluate(
            "brainfuck",
            "+[>+]",
            inputs=1,
            timeout=None,
            total_timeout=0.1,
            isolated=isolated,
        )


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_loading_errors_keep_their_public_type_under_a_deadline(isolated):
    with pytest.raises(esolangs.ProgramError):
        _evaluate("brainfuck", b"\xff", inputs=1, isolated=isolated, total_timeout=5)


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_termination_answers_still_require_a_proof_with_a_total_budget(isolated):
    source = esolangs.generate("123", "0110")
    assert (
        _evaluate(
            "123", source, inputs=2, timeout=None, total_timeout=5, isolated=isolated
        )
        == "0110"
    )


@pytest.mark.parametrize("budget", [0, True, float("inf"), 0.00001])
def test_invalid_total_deadlines(budget):
    with pytest.raises(esolangs.ArgumentError):
        _evaluate("brainfuck", ",.", inputs=1, total_timeout=budget)


def test_isolated_evaluation_requires_at_least_one_finite_budget():
    with pytest.raises(esolangs.ArgumentError, match="finite timeout"):
        _evaluate("brainfuck", ",.", inputs=1, timeout=None, isolated=True)
