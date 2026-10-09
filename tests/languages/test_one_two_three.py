"""123 through the shared API, CLI and machinery."""

import json
import threading

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs._isolated import _worker
from esolangs.exceptions import ArgumentError
from tests.generator_support import evaluate_generated, verify_generated
from tests.test_dialects import Unreadable


class TestTheTerminationProofFallsBackToTheClock:
    """A cycle is not the only way to diverge; growth never repeats a state."""

    def test_the_proof_needs_no_clock_at_all(self) -> None:
        """Which is the measurement, and also why the clock arm is untested."""
        assert evaluate_generated("123", "0110", None) == "0110"


class TestTerminationTimeoutIsUndecided:
    def test_timeout_propagates_with_row_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def expired(*_args: object) -> None:
            raise esolangs.ExecutionTimeoutError("forced timeout")

        monkeypatch.setattr(esolangs, "_run", expired)
        with pytest.raises(
            esolangs.ExecutionTimeoutError, match="forced timeout"
        ) as exc:
            verify_generated("123", "01")
        assert any("while evaluating row 0" in note for note in exc.value.__notes__)

    @pytest.mark.medium
    def test_vm_construction_is_timed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        from esolangs import _evaluate

        def slow_machine(*_args: object, **_kwargs: object) -> None:
            time.sleep(1)
            pytest.fail("construction escaped the timeout")

        monkeypatch.setattr(_evaluate, "make_vm", slow_machine)
        with pytest.raises(esolangs.ExecutionTimeoutError):
            evaluate_generated("123", "01", timeout=0.02)


def test_evaluate_refuses_a_timeout_off_the_main_thread() -> None:
    """The termination path drove ``_run`` directly and leaked ``SIGALRM``'s error."""
    box: list[BaseException] = []

    def work() -> None:
        try:
            evaluate_generated("123", "0110")
        except BaseException as exc:
            box.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(30)
    assert not thread.is_alive()
    assert len(box) == 1
    assert isinstance(box[0], ArgumentError)


def test_termination_diagnostic_does_not_score_a_timeout() -> None:
    with pytest.raises(esolangs.ArgumentError, match="timeout is undecided"):
        esolangs.read_answer("123", "1")


@pytest.mark.parametrize("language", ["Brainfuck", "123"])
def test_evaluation_refuses_settings_before_source_reads(language):
    settings = DialectSettings(cell_modulus=255)
    with pytest.raises(esolangs.ArgumentError):
        _evaluate(language, Unreadable(), inputs=1, settings=settings)


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_empty_settings_survive_termination_evaluation(isolated):
    source = esolangs.generate("123", "01")
    assert (
        _evaluate(
            "123", source, inputs=1, settings=DialectSettings(), isolated=isolated
        )
        == "01"
    )


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


def test_capped_termination_worker_reports_overflow_instead_of_divergence(
    monkeypatch, capsys
):
    import io
    import sys

    from esolangs import vm

    payload = {
        "language": "123",
        "program": "112",
        "raster": False,
        "stdin": "",
        "termination": ["0", "1"],
        "max_output": 0,
    }
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(vm, "ScriptedIO", vm.ScriptedIO)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert messages[-1]["error"] == "InterpreterLimitError"
    assert messages[-1]["output_limit"] is True
    assert "result" not in messages[-1]
