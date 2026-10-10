"""123 through the shared API, CLI and machinery."""

import contextlib
import json
import threading
from pathlib import Path

import pytest

import esolangs
from esolangs import DialectSettings, cli_io
from esolangs._evaluate import _evaluate
from esolangs._isolated import _worker
from esolangs.exceptions import ArgumentError
from tests.cli.test_cli import _program, call_main
from tests.cli_support import _LOOPS, call_both
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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("arguments", "diagnostic"),
    [
        (["--table", "xyz", "brainfuck"], "unknown option"),
        (["--judge", "123"], "unknown option"),
    ],
)
def test_run_rejects_bad_options_before_acquiring_source_or_stdin(
    arguments, diagnostic, monkeypatch, capsys
):
    import esolangs.cli_run as cli_run

    def unreadable(*_args, **_kwargs):
        pytest.fail("invalid run options must be rejected before reading")

    monkeypatch.setattr(cli_run, "_read_program", unreadable)
    monkeypatch.setattr(cli_run, "_read_stdin", unreadable)
    with pytest.raises(SystemExit) as caught:
        call_main(["run", *arguments, "never-read.txt"], capsys)
    assert caught.value.code == 2
    assert diagnostic in capsys.readouterr().err


# 3.0s over 12 tests: waits out a real timeout.
@pytest.mark.medium
class TestATimeoutIsNotAProgramError:
    """They shared exit 1, so a script could not tell them apart."""

    def test_a_program_failure_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half of the distinction, which is what makes 124 useful."""
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", _program(tmp_path, ",")], capsys, stdin="")
        assert exc.value.code == 1

    def test_a_termination_languages_timeout_is_undecided(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A timeout alone cannot establish a Boolean result."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)], capsys
            )
        assert exc.value.code == 124
        assert "the Boolean answer is undecided" in capsys.readouterr().err


class TestAnUnboundedRunSaysSo:
    """Several of these languages loop forever by design."""

    def test_a_bounded_run_never_arms_it(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --timeout there is nothing to warn about."""
        monkeypatch.setattr(cli_io, "_UNBOUNDED_NOTICE_AFTER", 0.01)
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            ["run", "--timeout", "10", "brainfuck", str(path)], capsys, stdin="1\n0\n"
        )
        assert "no bound" not in err

    def test_debug_warns_about_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` gained this a round earlier and `debug` did not."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "123", str(path)], capsys)
        assert "not terminating" in err

    def test_a_bounded_debug_is_not_told_to_pass_a_bound(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--steps is a bound as much as --timeout is."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "--steps", "200", "123", str(path)], capsys)
        assert "pass --timeout" not in err


class TestTheVerifierIsShipped:
    """Two blind readers and the test suite each wrote this same function."""

    def test_it_reads_the_termination_polarity_as_data(self) -> None:
        """Rather than assuming halting is the zero."""
        facts = esolangs.describe("123")
        assert facts["answer_encoding"] == ("halts", "diverges")
        assert verify_generated("123", "0110", timeout=5)

    def test_a_malformed_table_is_refused_before_anything_runs(self) -> None:
        """Named as a table, not as whichever generator saw it first."""
        with pytest.raises(esolangs.TruthTableError):
            evaluate_generated("brainfuck", "011")


class TestTheCallersSignalsAreTheirOwn:
    """The fix for the death took the caller's SIGALRM hostage."""

    @pytest.mark.parametrize("program", ["+", ","])
    def test_a_periodic_alarm_survives_a_timed_run(self, program: str) -> None:
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        timer = signal.setitimer(signal.ITIMER_REAL, 30, 5)
        try:
            with contextlib.suppress(esolangs.EsolangError):
                esolangs.run("brainfuck", program, timeout=1)
            remaining, interval = signal.getitimer(signal.ITIMER_REAL)
            assert remaining > 0
            assert interval == 5
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            signal.setitimer(signal.ITIMER_REAL, *timer)

    def test_a_pending_alarm_survives_a_timed_run(self) -> None:
        """Arming ours cancelled theirs, and nothing put it back."""
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        try:
            signal.alarm(30)
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
            esolangs.run("brainfuck", program, stdin=stdin, timeout=5)
            remaining = signal.alarm(0)
            assert remaining > 0, "the caller's alarm was cancelled"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_the_floor_applies_to_evaluate_too(self) -> None:
        """Its termination path never reaches ``run``, so it checked nothing."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            evaluate_generated("123", "0110", 1e-06)


class TestTheEncodersRefuseWhatTheyCannotAnswer:
    """Each says so rather than returning something plausible."""

    def test_encode_inputs_refuses_a_language_that_reads_nothing(self) -> None:
        """It returned stdin for a program with no input command."""
        with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
            esolangs.encode_inputs("123", [0, 1])

    def test_read_answer_refuses_a_non_string(self) -> None:
        with pytest.raises(esolangs.ProgramError, match="output must be a string"):
            esolangs.read_answer("brainfuck", None)  # type: ignore[arg-type]


def test_read_answer_refuses_a_termination_language(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Their output is not the answer, so reading one would invent it."""
    with pytest.raises(SystemExit) as exc:
        call_main(["read-answer", "123"], capsys, stdin="VO")
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--timeout" in err
    assert "observe" in err


def test_run_timeout_is_the_one_for_a_termination_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """For the four that answer by diverging, the timeout carries the 1."""
    program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
    with pytest.raises(SystemExit) as exc:
        call_main(
            ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
            capsys,
        )
    assert exc.value.code == 124
    assert "the Boolean answer is undecided" in capsys.readouterr().err


def test_run_halt_is_the_zero_for_a_termination_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """And the other polarity, from the same program and a different row."""
    program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
    out, err = call_both(
        ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)],
        capsys,
    )
    assert out == ""
    assert err == ""


def test_it_no_longer_costs_a_timeout_per_row() -> None:
    """It was five seconds per 1-row: twenty seconds for this call."""
    import time

    start = time.monotonic()
    evaluate_generated("123", "0110")
    assert time.monotonic() - start < 5.0
