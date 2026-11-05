"""Portable deadlines retain answers, errors, output and worker cleanup."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs import compat
from esolangs.results import ExecutionResult
from esolangs.runtime._isolated import _decode, _request_wire, _worker
from esolangs.runtime._lifecycle import HALTED_REPORT
from esolangs.runtime._result_wire import encode_result
from tests.support.generator_support import evaluate_generated, verify_generated
from tests.support.pick import one
from tests.support.reference import REFERENCE

#: A run that never halts by itself, and one that answers by terminating.
_UNUSUAL = [*one(self_halts=False), *one(answer_mode="termination")]


@pytest.mark.medium
@pytest.mark.parametrize(
    "language", [*_UNUSUAL, *one(source_kind="raster", boolean_generator=True)]
)
def test_generated_xor_runs_every_row_in_a_worker(language) -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(verify_generated, language, "0110", isolated=True).result()


@pytest.mark.medium
def test_timeout_retains_streamed_output() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run(REFERENCE, "+.[]", timeout=1, isolated=True)
    assert caught.value.partial_output == "\x01"
    assert esolangs.run(REFERENCE, "++.", isolated=True).output == "\x02"
    assert caught.value.execution is None


@pytest.mark.medium
def test_input_error_retains_counts_and_output() -> None:
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, "+.,", isolated=True)
    assert caught.value.reads == 0
    assert caught.value.supplied == 0
    assert caught.value.partial_output == "\x01"
    assert caught.value.execution == ExecutionResult("\x01", 0, 0, 1)


@pytest.mark.parametrize("timeout", [0, float("inf")])
def test_refuses_an_invalid_deadline(timeout) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(REFERENCE, "", timeout=timeout, isolated=True)


def test_decode_missing_result_and_notes() -> None:
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _decode('{"output": "abc"}\n', expired=False)
    assert caught.value.partial_output == "abc"
    payload = {
        "error": "ProgramError",
        "args": ["bad"],
        "notes": ["row 1"],
        "execution": None,
        "output_limit": False,
    }
    with pytest.raises(esolangs.ProgramError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.__notes__ == ["row 1"]
    assert caught.value.execution is None


def test_decode_truncated_write_on_timeout() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        _decode('{"output": "done"}\n{"output": "unfinished', expired=True)
    assert caught.value.partial_output == "done"
    assert caught.value.execution is None


def test_cancellation_kills_and_reaps_child(monkeypatch) -> None:
    from esolangs.runtime import _isolated

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
        _isolated.run_isolated_result(REFERENCE, "")
    assert calls == ["communicate", "kill", "communicate"]


def test_unknown_error_reconstructs_suggestions() -> None:
    payload = {
        "error": "UnknownLanguageError",
        "args": ["brainfuk", [REFERENCE]],
        "execution": None,
        "notes": [],
        "output_limit": False,
    }
    with pytest.raises(esolangs.UnknownLanguageError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.language == "brainfuk"
    assert caught.value.suggestions == (REFERENCE,)


@pytest.mark.medium
@pytest.mark.parametrize("limit", [0, 1, 4097])
def test_output_limit_stops_an_infinite_writer_and_reaps(limit, spawned) -> None:
    with pytest.raises(esolangs.InterpreterLimitError, match="output limit") as caught:
        esolangs.run(REFERENCE, "+[.]", isolated=True, max_output=limit)
    assert caught.value.partial_output == "\x01" * limit
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


@pytest.mark.medium
def test_output_limit_beyond_the_decimal_rendering_limit_accepts_small_output() -> None:
    assert (
        esolangs.run(REFERENCE, "++.", isolated=True, max_output=10**5000).output
        == "\x02"
    )


@pytest.mark.medium
def test_capped_timeout_retains_output_and_reaps(spawned) -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run(REFERENCE, "+.[]", timeout=1, isolated=True, max_output=10)
    assert caught.value.partial_output == "\x01"
    assert spawned[0].poll() is not None


@pytest.mark.parametrize("limit", [-1, True, 1.5, "1"])
def test_refuses_invalid_output_limits(limit) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_output"):
        esolangs.run(REFERENCE, "", isolated=True, max_output=limit)


def test_output_limit_requires_isolation() -> None:
    with pytest.raises(esolangs.ArgumentError, match="isolated"):
        esolangs.run(REFERENCE, "", max_output=1)


def test_capped_worker_splits_and_truncates_a_single_large_write(
    monkeypatch, capsys
) -> None:
    import io
    import sys

    def dump(*_args, **_kwargs):
        output = esolangs.ScriptedIO()
        output.print_str("λ" * 10_000)
        return output.getvalue()

    payload = _request_wire(REFERENCE, "", "", max_output=8193)
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(esolangs, "_run_result", dump)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [len(message["output"]) for message in messages[:-1]] == [4096, 4096, 1]
    assert messages[-1]["output_limit"] is True
    assert messages[-1]["error"] == "InterpreterLimitError"


@pytest.mark.medium
def test_capped_input_error_retains_public_class_and_prefix() -> None:
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, "+.,", isolated=True, max_output=2)
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


def test_capped_protocol_truncated_record_retains_prefix(protocol_child) -> None:
    from esolangs.runtime._isolated import _bounded_output

    child = protocol_child(['{"output":"prefix"}\n', '{"output":'])
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _bounded_output(child, "{}", 1)
    assert caught.value.partial_output == "prefix"
    assert child.killed
    assert child.reaped


def test_capped_protocol_verdict_does_not_excuse_a_lingering_worker(
    protocol_child,
) -> None:
    import subprocess

    from esolangs.runtime._isolated import _bounded_output

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


@pytest.mark.parametrize("language", _UNUSUAL)
def test_isolated_row_timeout_stays_undecided(language, monkeypatch) -> None:
    from esolangs.runtime import _isolated

    def expire(*_args, **_kwargs):
        error = esolangs.ExecutionTimeoutError("deadline")
        error.partial_output = "prefix"
        raise error

    monkeypatch.setattr(esolangs, "run", expire)
    monkeypatch.setattr(_isolated, "termination_result_isolated", expire)
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        evaluate_generated(language, "0110", isolated=True)
    assert caught.value.partial_output == "prefix"
    assert any("row 0" in note for note in caught.value.__notes__)


@pytest.mark.parametrize("max_output", [None, 1])
@pytest.mark.parametrize("startup", [0.4, 1.2])
def test_process_creation_consumes_the_worker_deadline(
    monkeypatch, max_output, startup
) -> None:
    from esolangs.runtime import _isolated
    from esolangs.runtime._isolated import _launch

    clock = [0.0]
    calls = []

    class Child:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def kill(self):
            calls.append("kill")

        def communicate(self, *_args, **kwargs):
            calls.append(kwargs.get("timeout"))
            return json.dumps(
                {
                    "result": "",
                    "execution": encode_result(
                        ExecutionResult("", 0, 0, 0, HALTED_REPORT)
                    ),
                }
            ), ""

    def spawn(*_args, **_kwargs):
        clock[0] += startup
        return Child()

    def bounded(_child, _request, timeout):
        calls.append(timeout)
        return ExecutionResult("", 0, 0, 0, HALTED_REPORT)

    monkeypatch.setattr(_isolated, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    monkeypatch.setattr(_isolated, "_bounded_output", bounded)
    if startup > 1:
        with pytest.raises(esolangs.ExecutionTimeoutError):
            _launch("{}", 1, max_output=max_output)
        assert calls == ["kill", None]
    else:
        assert _launch("{}", 1, max_output=max_output).output == ""
        assert calls == [pytest.approx(0.6)]


@pytest.mark.parametrize(
    "rows",
    [
        (((0, 0, 0),),),
        (((255, 255, 255),) * 7,) * 5,
        (
            ((0, 0, 0), (1, 2, 3), (1, 2, 3)),
            ((0, 0, 0), (1, 2, 3), (1, 2, 3)),
            ((255, 0, 17), (0, 0, 0), (4, 5, 6)),
        ),
    ],
)
def test_raster_transport_preserves_every_pixel(rows, monkeypatch) -> None:
    from esolangs.runtime import _isolated
    from esolangs.runtime._isolated import _raster_rows, _raster_transport

    image = esolangs.Raster(rows)
    runs = _raster_transport(image)
    assert runs is _raster_transport(image)
    monkeypatch.setattr(
        _isolated,
        "_launch",
        lambda request, *_args, **_kwargs: ExecutionResult(
            json.dumps(json.loads(request)["program"]), None, None, None, HALTED_REPORT
        ),
    )
    language = one(source_kind="raster", boolean_generator=True)[0]
    wire = esolangs.run(language, image, isolated=True).output
    assert _raster_rows(json.loads(wire)) == rows


@pytest.mark.medium
def test_worker_executes_compact_raster_pixels(monkeypatch, capsys) -> None:
    import io
    import sys

    language = one(source_kind="raster", boolean_generator=True)[0]
    image = compat.generate(language, "0110")
    payload = _request_wire(language, image, esolangs.encode_inputs(language, [0, 1]))
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert esolangs.read_answer(language, messages[-1]["result"]) == "1"


@pytest.mark.parametrize(
    ("budget", "isolated", "platform", "message"),
    [
        (1, False, "linux", "isolated"),
        (1 << 63, True, "linux", "platform limit"),
        (1, True, "darwin", "Linux"),
    ],
)
def test_memory_budget_rejects_unsupported_execution(
    monkeypatch, budget, isolated, platform, message
) -> None:
    import sys

    from esolangs.runtime._isolated import check_memory

    monkeypatch.setattr(sys, "platform", platform)
    with pytest.raises(esolangs.ArgumentError, match=message):
        check_memory(budget, isolated=isolated)


def test_memory_budget_accepts_linux_worker(monkeypatch) -> None:
    import sys

    from esolangs.runtime._isolated import check_memory

    monkeypatch.setattr(sys, "platform", "linux")
    check_memory(1, isolated=True)


@pytest.mark.medium
def test_worker_returns_a_termination_verdict(monkeypatch, capsys) -> None:
    import io
    import sys

    from esolangs import vm
    from tests.support.pick import first

    language = first(
        answer_mode="termination", boolean_generator=True, parameterized=False
    )

    monkeypatch.setattr(vm, "ScriptedIO", vm.ScriptedIO)
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    request = _request_wire(
        language,
        compat.generate(language, "00"),
        esolangs.encode_inputs(language, [0]),
        max_output=100,
        termination=True,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    original_io = esolangs.ScriptedIO, vm.ScriptedIO
    _worker()
    assert (esolangs.ScriptedIO, vm.ScriptedIO) == original_io
    assert _decode(capsys.readouterr().out, expired=False).decision.halts is True
