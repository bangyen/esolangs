"""Portable deadlines retain answers, errors, output and worker cleanup."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
import esolangs.operations.execution as _execution_operations
from esolangs.results import ExecutionResult
from esolangs.runtime._isolated import _request_wire, _worker
from esolangs.runtime._json import worker_dumps, worker_object
from esolangs.runtime._lifecycle import HALTED_REPORT
from esolangs.runtime._result_wire import encode_result
from tests.support.generator_support import evaluate_generated, verify_generated
from tests.support.pick import one
from tests.support.reference import REFERENCE
from tests.support.worker_response import _decode

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
    assert caught.value.observation is None


@pytest.mark.medium
def test_input_error_retains_counts_and_output() -> None:
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, "+.,", isolated=True)
    assert caught.value.reads == 0
    assert caught.value.supplied == 0
    assert caught.value.partial_output == "\x01"
    assert caught.value.observation == ExecutionResult("\x01", 0, 0, 1)


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
    assert caught.value.observation is None

    for text in ("\ud800\udfff", "\ud800", "\udfff", "\U000103ff"):
        packet = {
            "output": text,
            "nested": [text, {"notes": [text]}],
            "literal": {"$python_text": "eda080"},
        }
        assert (
            json.loads(worker_dumps(packet), object_pairs_hook=worker_object) == packet
        )
    for payload in (0, None, "EDA080", "ed a0 80", "ff", "41", ""):
        with pytest.raises(ValueError, match=r"worker text|decode"):
            json.loads(
                json.dumps({"$python_text": payload}), object_pairs_hook=worker_object
            )
    with pytest.raises(ValueError, match="duplicate field"):
        json.loads(
            '{"$python_text":"eda080","$python_text":"edbfbf"}',
            object_pairs_hook=worker_object,
        )

    from unittest.mock import patch

    from esolangs.runtime._json import worker_loads

    for packet in (
        {"plain": [0, -0.0, True, None, "λ"]},
        [1, {"a": "b"}],
        {1: "int-key"},
    ):
        assert worker_dumps(packet) == json.dumps(packet)
        assert worker_loads(worker_dumps(packet)) == json.loads(
            json.dumps(packet), object_pairs_hook=worker_object
        )
    literal = {"$python_text": "\ud800\udfff"}
    calls = []

    def counted(pairs):
        calls.append(tuple(key for key, _ in pairs))
        return worker_object(pairs)

    with patch("esolangs.runtime._json.worker_object", counted):
        assert worker_loads(worker_dumps(literal)) == literal
    assert calls == [("$python_text",), ("$python_object",)]
    deep = literal
    for level in range(1100):
        deep = [deep] if level % 2 else {"node": deep}
    restored = worker_loads(worker_dumps(deep))
    for level in reversed(range(1100)):
        assert type(restored) is (list if level % 2 else dict)
        restored = restored[0] if level % 2 else restored["node"]
    assert restored == literal
    for document in (
        "",
        " ",
        "\u00a0[]",
        "[",
        "{",
        "[1,]",
        '{"a":}',
        '{"a" 1}',
        '{"a":1,}',
        "[1 2]",
        "00",
        "+1",
        "1.",
        "1e",
        "truex",
        "[] {}",
        '"\\uZZZZ"',
        '{"x":1,"\\u0078":2}',
    ):
        with pytest.raises(ValueError, match=r"Expecting|Extra data|Invalid|duplicate"):
            worker_loads(document)
    for document in (
        "0",
        "-0",
        "-0.0",
        "1e+2",
        "true",
        "false",
        "null",
        '"\\u0061"',
        '[0,{"x":[true,null]}]',
    ):
        assert worker_loads(document) == json.loads(
            document, object_pairs_hook=worker_object
        )
    for payload in (0, None, "EDA080", "ed a0 80", "ff", "41", ""):
        with pytest.raises(ValueError, match=r"worker text|decode"):
            worker_loads(json.dumps({"$python_text": payload}))
    for entries in (
        None,
        0,
        [],
        [["other", 1]],
        [["$python_text"]],
        [["$python_text", 1, 2]],
    ):
        with pytest.raises(ValueError, match="worker object"):
            worker_loads(json.dumps({"$python_object": entries}))
    import math

    assert worker_dumps(-0.0) == "-0.0"
    assert math.copysign(1, worker_loads("-0.0")) == -1
    assert math.isnan(worker_loads("NaN"))
    assert worker_loads("Infinity") == float("inf")
    shared = ["x"]
    assert worker_loads(worker_dumps([shared, shared])) == [["x"], ["x"]]
    circular = []
    circular.append(circular)
    with pytest.raises(ValueError, match="Circular reference"):
        worker_dumps(circular)

    json_depth = 33_000
    wide = 0
    for _ in range(json_depth):
        wide = [wide]
    wide = worker_loads(worker_dumps(wide))
    for _ in range(json_depth):
        assert type(wide) is list
        assert len(wide) == 1
        wide = wide[0]
    assert type(wide) is int
    assert wide == 0


def test_decode_truncated_write_on_timeout() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        _decode('{"output": "done"}\n{"output": "unfinished', expired=True)
    assert caught.value.partial_output == "done"
    assert caught.value.observation is None


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
        _isolated.execute_isolated(REFERENCE, "").unwrap()
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
    # A budget the caller named, but no clock ran out.
    assert isinstance(caught.value, esolangs.ExecutionBudgetError)
    assert caught.value.bound == "max_output"
    assert not isinstance(caught.value, TimeoutError)
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


@pytest.mark.medium
def test_an_output_cap_selects_isolation_on_every_route(spawned) -> None:
    """``run(max_output=0)`` said "requires isolated=True"; ``execute`` ran."""
    language = esolangs.Language(REFERENCE)
    limits = esolangs.ExecutionLimits(max_output=1)
    outcome = language.execute("+[.]", limits=limits)
    for call in (
        lambda: esolangs.run(REFERENCE, "+[.]", max_output=1),
        lambda: language.prepare("+[.]").run(max_output=1),
    ):
        with pytest.raises(esolangs.InterpreterLimitError) as caught:
            call()
        assert str(caught.value) == str(outcome.error)
        assert caught.value.bound == outcome.bound == "max_output"
        assert caught.value.partial_output == outcome.observation.output == "\x01"
    assert len(spawned) == 3
    with pytest.raises(esolangs.ArgumentError, match="max_memory must be a positive"):
        esolangs.run(REFERENCE, "+", max_memory=0)


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


def test_capped_worker_splits_and_truncates_a_single_large_write(
    monkeypatch, capsys
) -> None:
    import io
    import sys

    def dump(*_args, io_factory, **_kwargs):
        output = io_factory("")
        output.print_str("λ" * 10_000)
        return output.getvalue()

    payload = _request_wire(REFERENCE, "", "", max_output=8193)
    monkeypatch.setattr(_execution_operations, "_execute_invocation", dump)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    _worker()
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [len(message["output"]) for message in messages[:-1]] == [4096, 4096, 1]
    assert messages[-1]["output_limit"] is True
    assert messages[-1]["error"] == "ExecutionCapError"
    assert messages[-1]["bound"] == "max_output"


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

    for malformed in (
        '{"output":',
        "null\n",
        "[]\n",
        '{"output":"hidden","output":"prefix"}\n',
        '{"output_limit":true,"output_limit":false}\n',
    ):
        child = protocol_child(['{"output":"prefix"}\n', malformed])
        with pytest.raises(esolangs.InterpreterLimitError) as caught:
            _bounded_output(child, "{}", 1).unwrap()
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
        _bounded_output(child, "{}", 1).unwrap()
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
        return esolangs.ExecutionOutcome(
            "completed", ExecutionResult("", 0, 0, 0, HALTED_REPORT)
        )

    monkeypatch.setattr(_isolated, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    monkeypatch.setattr(_isolated, "_bounded_output", bounded)
    if startup > 1:
        with pytest.raises(esolangs.ExecutionTimeoutError):
            _launch("{}", 1, max_output=max_output).unwrap()
        assert calls == ["kill", None]
    else:
        assert _launch("{}", 1, max_output=max_output).unwrap().output == ""
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
        lambda request, *_args, **_kwargs: esolangs.ExecutionOutcome(
            "completed",
            ExecutionResult(
                json.dumps(json.loads(request)["program"]),
                None,
                None,
                None,
                HALTED_REPORT,
            ),
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
    image = esolangs.generate(language, "0110")
    payload = _request_wire(
        language,
        image.source,
        esolangs.encode_inputs(language, [0, 1]),
        settings=image.settings,
        scale=image.scale,
    )
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

    program = esolangs.generate(language, "00")
    request = _request_wire(
        language,
        program.source,
        esolangs.encode_inputs(language, [0]),
        settings=program.settings,
        max_output=100,
        termination=True,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    ordinary = esolangs.run(REFERENCE, "+.", max_steps=2)
    _worker()
    assert esolangs.run(REFERENCE, "+.", max_steps=2) == ordinary
    assert not hasattr(_execution_operations, "io_factory")
    assert not hasattr(vm, "io_factory")
    assert _decode(capsys.readouterr().out, expired=False).decision.halts is True
