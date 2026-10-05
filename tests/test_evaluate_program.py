"""Evaluation runs supplied programs without invoking a generator."""

from pathlib import Path

import pytest

import esolangs
from esolangs._evaluate import _evaluate, _iter_evaluate
from tests.test_cli import call_main


def test_supplied_program_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("evaluation called a generator")

    monkeypatch.setattr(esolangs, "generate", refuse)
    assert _evaluate("brainfuck", ",>,<.", inputs=2) == "0011"
    assert _evaluate("Deadfish", "o", inputs=1) == "00"


@pytest.mark.parametrize(
    "name",
    [
        "Fargo",
        "Grapheme",
        "Clockwise",
        "Taglate",
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


def test_verify_is_removed(capsys: pytest.CaptureFixture[str]) -> None:
    assert not hasattr(esolangs, "verify")
    with pytest.raises(SystemExit) as exc:
        call_main(["verify", "brainfuck", "0110"], capsys)
    assert exc.value.code == 2
    assert "unknown command" in capsys.readouterr().err


def test_answer_is_removed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        call_main(["answer", "brainfuck", "0110", "10"], capsys)
    assert exc.value.code == 2
    assert "unknown command" in capsys.readouterr().err


def test_evaluate_is_removed(capsys: pytest.CaptureFixture[str]) -> None:
    assert not hasattr(esolangs, "evaluate")
    assert not hasattr(esolangs, "iter_evaluate")
    assert not hasattr(esolangs.Language("brainfuck"), "evaluate")
    assert not hasattr(esolangs.Language("brainfuck"), "iter_evaluate")
    with pytest.raises(SystemExit) as exc:
        call_main(["evaluate", "--inputs", "2", "brainfuck", "program.txt"], capsys)
    assert exc.value.code == 2
    assert "unknown command" in capsys.readouterr().err


def test_checks_are_removed(capsys: pytest.CaptureFixture[str]) -> None:
    assert not hasattr(esolangs, "check_program")
    assert not hasattr(esolangs, "check_stdin")
    assert not hasattr(esolangs.Language("brainfuck"), "check_program")
    assert not hasattr(esolangs.Language("brainfuck"), "check_stdin")
    with pytest.raises(SystemExit) as exc:
        call_main(["check-stdin", "brainfuck"], capsys)
    assert exc.value.code == 2
    assert "unknown command" in capsys.readouterr().err


@pytest.mark.parametrize("inputs", [True, 0, -1, 65, 2.5, "2"])
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
