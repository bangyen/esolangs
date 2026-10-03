"""Portable deadlines retain answers, errors, output and worker cleanup."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs._isolated import _decode, _worker
from tests.generator_support import evaluate_generated, verify_generated


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Suffolk", "123", "Piet"])
def test_generated_xor_runs_every_row_in_a_worker(language):
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(verify_generated, language, "0110", isolated=True).result()


@pytest.mark.medium
def test_timeout_retains_streamed_output():
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run("brainfuck", "+.[]", timeout=1, isolated=True)
    assert caught.value.partial_output == "\x01"
    assert esolangs.run("brainfuck", "++.", isolated=True) == "\x02"


@pytest.mark.medium
def test_input_error_retains_counts_and_output():
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run("brainfuck", "+.,", isolated=True)
    assert caught.value.reads == 0
    assert caught.value.supplied == 0
    assert caught.value.partial_output == "\x01"


@pytest.mark.parametrize("timeout", [None, 0, float("inf")])
def test_refuses_missing_or_invalid_deadline(timeout):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("brainfuck", "", timeout=timeout, isolated=True)


def test_isolated_evaluation_requires_a_deadline():
    with pytest.raises(esolangs.ArgumentError, match="finite"):
        evaluate_generated("Suffolk", "0110", None, isolated=True)


def test_decode_missing_result_and_notes():
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _decode('{"output": "abc"}\n', expired=False)
    assert caught.value.partial_output == "abc"
    payload = {"error": "ProgramError", "args": ["bad"], "notes": ["row 1"]}
    with pytest.raises(esolangs.ProgramError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.__notes__ == ["row 1"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "language": "brainfuck",
            "program": "+.",
            "raster": False,
            "stdin": "",
            "seed": None,
        },
        {
            "language": "brainfuck",
            "program": ",",
            "raster": False,
            "stdin": "",
            "seed": None,
        },
        {
            "language": "brainfuck",
            "program": "",
            "raster": False,
            "stdin": "",
            "termination": ["0", "1"],
        },
        {
            "language": "brainfuck",
            "program": "[",
            "raster": False,
            "stdin": "",
            "seed": None,
        },
        {
            "language": "missing",
            "program": "",
            "raster": False,
            "stdin": "",
            "seed": None,
        },
    ],
)
def test_worker_protocol(payload, monkeypatch, capsys):
    import io
    import sys

    # The worker normally exits after rebinding; restore its I/O class here.
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert "result" in messages[-1] or "error" in messages[-1]


def test_decode_truncated_write_on_timeout():
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        _decode('{"output": "done"}\n{"output": "unfinished', expired=True)
    assert caught.value.partial_output == "done"


def test_worker_raster_protocol(monkeypatch, capsys):
    import io
    import sys

    program = esolangs.generate("Piet", "01")
    payload = {
        "language": "Piet",
        "program": program.rows,
        "raster": True,
        "stdin": "1\n",
        "seed": None,
    }
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert messages[-1] == {"result": "1"}


def test_cancellation_kills_and_reaps_child(monkeypatch):
    from esolangs import _isolated

    calls = []

    class Child:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def communicate(self, *_args, **_kwargs):
            calls.append("communicate")
            if len(calls) == 1:
                raise KeyboardInterrupt
            return "", ""

        def kill(self):
            calls.append("kill")

    monkeypatch.setattr(
        _isolated.subprocess, "Popen", lambda *_args, **_kwargs: Child()
    )
    with pytest.raises(KeyboardInterrupt):
        _isolated.run_isolated("brainfuck", "")
    assert calls == ["communicate", "kill", "communicate"]


def test_unknown_error_reconstructs_suggestions():
    payload = {"error": "UnknownLanguageError", "args": ["brainfuk", ["brainfuck"]]}
    with pytest.raises(esolangs.UnknownLanguageError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.language == "brainfuk"
    assert caught.value.suggestions == ("brainfuck",)


@pytest.mark.medium
@pytest.mark.parametrize("limit", [0, 1, 4097])
def test_output_limit_stops_an_infinite_writer_and_reaps(limit, monkeypatch):
    from esolangs import _isolated

    children = []
    popen = _isolated.subprocess.Popen

    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    with pytest.raises(esolangs.InterpreterLimitError, match="output limit") as caught:
        esolangs.run("brainfuck", "+[.]", isolated=True, max_output=limit)
    assert caught.value.partial_output == "\x01" * limit
    assert len(children) == 1
    assert children[0].poll() is not None


@pytest.mark.medium
def test_output_limit_accepts_exact_length_and_unicode():
    assert esolangs.run("brainfuck", "", isolated=True, max_output=0) == ""
    assert esolangs.run("Sophie", "#λ,", isolated=True, max_output=1) == "λ"
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        esolangs.run("Sophie", "#λ,,", isolated=True, max_output=1)
    assert caught.value.partial_output == "λ"


@pytest.mark.medium
def test_capped_timeout_retains_output_and_reaps(monkeypatch):
    from esolangs import _isolated

    children = []
    popen = _isolated.subprocess.Popen

    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run("brainfuck", "+.[]", timeout=1, isolated=True, max_output=10)
    assert caught.value.partial_output == "\x01"
    assert children[0].poll() is not None


@pytest.mark.parametrize("limit", [-1, True, 1.5, "1"])
def test_refuses_invalid_output_limits(limit):
    with pytest.raises(esolangs.ArgumentError, match="max_output"):
        esolangs.run("brainfuck", "", isolated=True, max_output=limit)


def test_output_limit_requires_isolation():
    with pytest.raises(esolangs.ArgumentError, match="isolated"):
        esolangs.run("brainfuck", "", max_output=1)


def test_capped_worker_splits_and_truncates_a_single_large_write(monkeypatch, capsys):
    import io
    import sys

    def dump(*_args, **_kwargs):
        output = esolangs.ScriptedIO()
        output.print_str("λ" * 10_000)
        return output.getvalue()

    payload = {
        "language": "brainfuck",
        "program": "",
        "raster": False,
        "stdin": "",
        "seed": None,
        "max_output": 8193,
    }
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(esolangs, "run", dump)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [len(message["output"]) for message in messages[:-1]] == [4096, 4096, 1]
    assert messages[-1]["output_limit"] is True
    assert messages[-1]["error"] == "InterpreterLimitError"


@pytest.mark.medium
def test_capped_input_error_retains_public_class_and_prefix():
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run("brainfuck", "+.,", isolated=True, max_output=2)
    assert caught.value.partial_output == "\x01"
    assert caught.value.reads == 0
    assert caught.value.supplied == 0


@pytest.fixture
def protocol_child():
    import io

    class Child:
        def __init__(self, records):
            self.stdin = io.StringIO()
            self.stdout = iter(records)
            self.killed = self.reaped = False

        def kill(self):
            self.killed = True

        def wait(self, **_kwargs):
            self.reaped = True
            return 0

    return Child


def test_capped_protocol_truncated_record_retains_prefix(protocol_child):
    from esolangs._isolated import _bounded_output

    child = protocol_child(['{"output":"prefix"}\n', '{"output":'])
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _bounded_output(child, "{}", 1)
    assert caught.value.partial_output == "prefix"
    assert child.killed
    assert child.reaped


def test_capped_protocol_backpressure_and_stop_join_reader(protocol_child, monkeypatch):
    from queue import Full, Queue
    from threading import Event

    from esolangs import _isolated

    attempts = []
    stopped = Event()

    class Backpressure(Queue):
        def put(self, value, **kwargs):
            attempts.append(value)
            if len(attempts) == 1:
                raise Full
            return super().put(value, **kwargs)

    def records():
        yield '{"output":"prefix"}\n'
        yield (
            json.dumps(
                {
                    "error": "InterpreterLimitError",
                    "args": ["output limit"],
                    "output_limit": True,
                }
            )
            + "\n"
        )
        # Force one more record after the parent has stopped consumption.
        assert stopped.wait(1)
        yield '{"output":"late"}\n'

    child = protocol_child(records())
    original_kill = child.kill

    def kill():
        original_kill()
        stopped.set()

    child.kill = kill
    monkeypatch.setattr(_isolated, "Queue", Backpressure)
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _isolated._bounded_output(child, "{}", 1)  # noqa: SLF001
    assert caught.value.partial_output == "prefix"
    assert len(attempts) == 3
    assert child.killed
    assert child.reaped


def test_capped_protocol_transfer_error_reaps(protocol_child):
    from esolangs._isolated import _bounded_output

    class BrokenWriter:
        def write(self, _text):
            raise OSError("broken pipe")

    child = protocol_child([])
    child.stdin = BrokenWriter()
    with pytest.raises(OSError, match="broken pipe"):
        _bounded_output(child, "{}", 1)
    assert child.killed
    assert child.reaped


def test_capped_protocol_cancellation_reaps(protocol_child, monkeypatch):
    from queue import Queue

    from esolangs import _isolated

    class Cancelled(Queue):
        def get(self, **_kwargs):
            raise KeyboardInterrupt

    monkeypatch.setattr(_isolated, "Queue", Cancelled)
    child = protocol_child(['{"result":""}\n'])
    with pytest.raises(KeyboardInterrupt):
        _isolated._bounded_output(child, "{}", 1)  # noqa: SLF001
    assert child.killed
    assert child.reaped


def test_capped_protocol_deadline_before_read_reaps(protocol_child, monkeypatch):
    from esolangs import _isolated

    clock = iter([0, 2])
    monkeypatch.setattr(_isolated, "monotonic", lambda: next(clock))
    child = protocol_child([])
    with pytest.raises(esolangs.ExecutionTimeoutError):
        _isolated._bounded_output(child, "{}", 1)  # noqa: SLF001
    assert child.killed
    assert child.reaped


def test_capped_protocol_verdict_does_not_excuse_a_lingering_worker(protocol_child):
    import subprocess

    from esolangs._isolated import _bounded_output

    child = protocol_child(['{"output":"prefix"}\n', '{"result":"prefix"}\n'])
    original_wait = child.wait

    def wait(timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired("worker", timeout)
        return original_wait()

    child.wait = wait
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        _bounded_output(child, "{}", 1)
    assert caught.value.partial_output == "prefix"
    assert child.killed
    assert child.reaped


@pytest.mark.parametrize("language", ["Suffolk", "123"])
def test_isolated_row_timeout_stays_undecided(language, monkeypatch):
    from esolangs import _isolated

    def expire(*_args, **_kwargs):
        error = esolangs.ExecutionTimeoutError("deadline")
        error.partial_output = "prefix"
        raise error

    monkeypatch.setattr(esolangs, "run", expire)
    monkeypatch.setattr(_isolated, "termination_isolated", expire)
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        evaluate_generated(language, "0110", isolated=True)
    assert caught.value.partial_output == "prefix"
    assert "row 0" in caught.value.__notes__[0]
