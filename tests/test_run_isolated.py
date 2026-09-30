"""Portable deadlines retain answers, errors, output and worker cleanup."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs._isolated import _decode, _worker


@pytest.mark.medium
@pytest.mark.parametrize("language", ["Suffolk", "123", "Piet"])
def test_generated_xor_runs_every_row_in_a_worker(language):
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(esolangs.verify, language, "0110", isolated=True).result()


@pytest.mark.medium
def test_timeout_retains_streamed_output():
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run_isolated("brainfuck", "+.[]", timeout=1)
    assert caught.value.partial_output == "\x01"
    assert esolangs.run_isolated("brainfuck", "++.") == "\x02"


@pytest.mark.medium
def test_input_error_retains_counts_and_output():
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run_isolated("brainfuck", "+.,")
    assert caught.value.reads == 0
    assert caught.value.supplied == 0
    assert caught.value.partial_output == "\x01"


@pytest.mark.parametrize("timeout", [None, 0, float("inf")])
def test_refuses_missing_or_invalid_deadline(timeout):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run_isolated("brainfuck", "", timeout=timeout)


def test_isolated_evaluation_requires_a_deadline():
    with pytest.raises(esolangs.ArgumentError, match="finite"):
        esolangs.evaluate("Suffolk", "0110", None, isolated=True)


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


@pytest.mark.parametrize("language", ["Suffolk", "123"])
def test_isolated_row_timeout_stays_undecided(language, monkeypatch):
    from esolangs import _isolated

    def expire(*_args, **_kwargs):
        error = esolangs.ExecutionTimeoutError("deadline")
        error.partial_output = "prefix"
        raise error

    monkeypatch.setattr(esolangs, "run_isolated", expire)
    monkeypatch.setattr(_isolated, "termination_isolated", expire)
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.evaluate(language, "0110", isolated=True)
    assert caught.value.partial_output == "prefix"
    assert "row 0" in caught.value.__notes__[0]
