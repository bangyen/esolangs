"""The private evaluation harness: supplied programs and budgets."""

import threading
from io import StringIO
from pathlib import Path

import pytest

import esolangs
import esolangs._evaluate as evaluator
from esolangs._evaluate import _evaluate, _iter_evaluate


def test_supplied_program_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("evaluation called a generator")

    monkeypatch.setattr(esolangs, "generate", refuse)
    assert _evaluate("brainfuck", ",>,<.", inputs=2) == "0011"
    assert _evaluate("Deadfish", "o", inputs=1) == "00"


@pytest.mark.parametrize(
    "name",
    [
        "Clockwise",
        "A Painter Ant",
        "Minifuck",
        "Piet",
        "123",
    ],
)
def test_evaluate_files(name: str, tmp_path: Path) -> None:
    program = esolangs.generate(name, "0110")
    path = tmp_path / "source"
    if isinstance(program, esolangs.Raster):
        path.write_bytes(program.to_png())
    else:
        path.write_text(program + "\n")
    assert _evaluate(name, path, inputs=2) == "0110"


@pytest.mark.parametrize("inputs", [True, 0, 65, 2.5, "2"])
def test_api_refuses_bad_inputs(inputs: object) -> None:
    with pytest.raises(esolangs.ArgumentError, match="inputs must"):
        _evaluate("brainfuck", ",.", inputs=inputs)  # type: ignore[arg-type]


def test_api_refuses_bad_source() -> None:
    with pytest.raises(esolangs.ProgramError, match="string of source"):
        _evaluate("brainfuck", 42, inputs=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["Minifuck", "Vandevelo"])
def test_api_refuses_raster_for_text_answer(name: str) -> None:
    raster = esolangs.generate("Piet", "0110")
    with pytest.raises(esolangs.ProgramError, match="string of source"):
        _evaluate(name, raster, inputs=2)


def test_timeout_is_not_a_boolean_answer() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as exc:
        _evaluate("brainfuck", "+[]", inputs=1, timeout=0.01)
    assert any("row 0" in note for note in exc.value.__notes__)


def test_termination_input_exhaustion_is_a_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import esolangs._evaluate as evaluate_module

    def exhausted(*_args: object, **_kwargs: object) -> None:
        raise esolangs.InputExhaustedError(2, 1)

    program = esolangs.generate("ArrowQueue", "01")
    monkeypatch.setattr(evaluate_module, "make_vm", exhausted)
    with pytest.raises(esolangs.InputExhaustedError) as exc:
        _evaluate("ArrowQueue", program, inputs=1)
    assert any("row 0" in note for note in exc.value.__notes__)


@pytest.mark.medium
@pytest.mark.parametrize("streaming", [False, True])
def test_isolated_row_output_limit_resets_per_row(streaming):
    source = "+" * 48 + "."
    evaluate = _iter_evaluate if streaming else _evaluate
    assert (
        "".join(evaluate("brainfuck", source, inputs=1, isolated=True, max_output=1))
        == "00"
    )


@pytest.mark.medium
def test_evaluation_output_overflow_retains_partial_output_and_row():
    with pytest.raises(esolangs.InterpreterLimitError, match="output limit") as caught:
        _evaluate("brainfuck", "+" * 48 + "..", inputs=1, isolated=True, max_output=1)
    assert caught.value.partial_output == "0"
    assert any("row 0" in note for note in caught.value.__notes__)
    assert any("answered (none)" in note for note in caught.value.__notes__)


@pytest.mark.medium
def test_termination_output_limit_is_not_a_divergence_verdict():
    with pytest.raises(esolangs.InterpreterLimitError, match="output limit"):
        _evaluate(
            "123",
            esolangs.generate("123", "0110"),
            inputs=2,
            isolated=True,
            max_output=0,
        )
    source = esolangs.generate("Vandevelo", "01")
    assert _evaluate("Vandevelo", source, inputs=1, isolated=True, max_output=0) == "01"


@pytest.mark.parametrize("limit", [-1, True, 1.0])
def test_evaluation_rejects_invalid_output_limit_before_loading(limit, tmp_path):
    with pytest.raises(esolangs.ArgumentError, match="max_output"):
        _evaluate(
            "brainfuck", tmp_path / "missing", inputs=1, isolated=True, max_output=limit
        )


def test_evaluation_output_limit_requires_isolation():
    with pytest.raises(esolangs.ArgumentError, match="isolated=True"):
        _evaluate("brainfuck", "", inputs=1, max_output=1)


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
