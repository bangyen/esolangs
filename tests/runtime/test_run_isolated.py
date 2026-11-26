"""Portable deadlines retain answers, errors, output and worker cleanup."""

import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from time import monotonic

import pytest

import esolangs
import esolangs.operations.execution as _execution_operations
from esolangs.results import ExecutionResult
from esolangs.runtime._isolated import _worker
from esolangs.runtime._json import worker_dumps, worker_object
from esolangs.runtime._lifecycle import HALTED_REPORT
from esolangs.runtime._request_wire import encode_request
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
@pytest.mark.parametrize("bound", ["execution_timeout", "total_timeout"])
def test_timeout_retains_streamed_output(bound) -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run(
            REFERENCE,
            "+.[]",
            limits=esolangs.ExecutionLimits(**{bound: 1}),
            isolated=True,
        )
    assert caught.value.partial_output == "\x01"
    assert esolangs.run(REFERENCE, "++.", isolated=True).output == "\x02"
    assert caught.value.bound == bound
    assert caught.value.observation is None


@pytest.mark.medium
@pytest.mark.parametrize("bound", ["total_timeout", "preparation_timeout"])
def test_timeout_retains_output_already_queued(monkeypatch, spawned, bound) -> None:
    from esolangs.runtime import _isolated

    queued = Event()
    monotonic = _isolated.monotonic
    displacement = 0.0
    read_output = _isolated._read_worker_output

    class ObservedQueue(Queue):
        def put(self, item, *args, **kwargs):
            super().put(item, *args, **kwargs)
            if isinstance(item, str) and json.loads(item).get("output_limit"):
                queued.set()

    def expire_after_output_was_queued(*args):
        nonlocal displacement
        assert queued.wait(3), "worker did not write output and hit its cap"
        displacement = 10.0
        return read_output(*args)

    monkeypatch.setattr(_isolated, "Queue", ObservedQueue)
    monkeypatch.setattr(_isolated, "monotonic", lambda: monotonic() + displacement)
    monkeypatch.setattr(
        _isolated, "_read_worker_output", expire_after_output_was_queued
    )
    outcome = esolangs.execute(
        REFERENCE,
        ",.[.]",
        stdin="A",
        limits=esolangs.ExecutionLimits(max_output=1, **{bound: 5}),
    )
    assert isinstance(outcome.error, esolangs.ExecutionTimeoutError)
    assert outcome.bound == bound
    assert outcome.error.partial_output == "A"
    assert outcome.error.observation is None
    assert outcome.observation == ExecutionResult("A", None, None, None)
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


@pytest.mark.medium
def test_input_error_retains_counts_and_output() -> None:
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, "+.,", isolated=True)
    assert caught.value.reads == 0
    assert caught.value.supplied == 0
    assert caught.value.partial_output == "\x01"
    assert caught.value.observation == ExecutionResult("\x01", 0, 0, 1)


@pytest.mark.medium
@pytest.mark.parametrize(
    "budgets",
    [
        {},
        {"max_steps": 5},
        {"total_timeout": 5},
        {"execution_timeout": 5},
        {"preparation_timeout": 5},
    ],
)
def test_syntax_rejection_preserves_known_zero_input_counters(budgets) -> None:
    limits = esolangs.ExecutionLimits(**budgets)
    outcome = esolangs.execute(REFERENCE, "[", limits=limits)
    assert isinstance(outcome.error, esolangs.ProgramError)
    assert (
        outcome.error.observation == outcome.observation == ExecutionResult("", 0, 0, 0)
    )
    outcome = esolangs.execute(REFERENCE, object(), limits=limits)
    assert isinstance(outcome.error, esolangs.ProgramError)
    assert outcome.error.observation is None
    if not budgets:
        _check_vm_initialization_rejection()
        _check_binary_source_boundary()


def _check_binary_source_boundary() -> None:
    from esolangs.runtime._files import _BLOCK

    api = esolangs.Language(REFERENCE)
    limits = esolangs.ExecutionLimits(total_timeout=5, max_steps=3)
    prefix = b"[" + b" " * (_BLOCK - 2)
    assert api.run(prefix + "é".encode() + b"]+.", limits=limits).output == "\x01"
    with pytest.raises(
        esolangs.ProgramError, match=f"invalid UTF-8 at byte {_BLOCK - 1}"
    ):
        api.run(prefix + b"\xc3(]+.", limits=limits)


def _check_vm_initialization_rejection() -> None:
    api = esolangs.Language(REFERENCE)
    refusal = esolangs.ProgramError("stdin acquisition refused")

    class RefusesInput:
        def read(self):
            raise refusal

    for create in (api.make_vm, api.make_debugger):
        stdin = StringIO("X")
        with pytest.raises(esolangs.ProgramError, match="unmatched") as syntax:
            create("[", stdin=stdin)
        assert stdin.tell() == 1
        assert syntax.value.observation == ExecutionResult("", 0, 0, 0)

        stdin = StringIO("X")
        with pytest.raises(esolangs.ProgramError) as source:
            create(object(), stdin=stdin)
        assert stdin.tell() == 0
        assert source.value.observation is None

        with pytest.raises(esolangs.ProgramError, match="acquisition refused") as read:
            create("+.", stdin=RefusesInput())
        assert read.value is refusal
        assert refusal.observation is None


@pytest.mark.medium
@pytest.mark.parametrize("flag", ["-P", "-I"])
def test_worker_preserves_parent_import_and_stdio_options(flag, tmp_path) -> None:
    decoy = tmp_path / "esolangs.py"
    decoy.write_text("raise RuntimeError('local package must not be imported')\n")
    subprocess.run(
        [
            sys.executable,
            flag,
            "-c",
            "import esolangs; "
            "assert esolangs.run('brainfuck', ',.', stdin='é', "
            "isolated=True).output == 'é'; "
            "assert esolangs.run('brainfuck', ',.', stdin='é', limits="
            "esolangs.ExecutionLimits(execution_timeout=4)).output == 'é'",
        ],
        env={**os.environ, "PYTHONIOENCODING": "utf-16"},
        cwd=tmp_path,
        check=True,
        timeout=10,
    )


@pytest.mark.medium
@pytest.mark.parametrize("flag", ["-E", "-I"])
def test_worker_ignores_python_environment_when_the_parent_does(flag, tmp_path) -> None:
    subprocess.run(
        [
            sys.executable,
            flag,
            "-c",
            "import esolangs; "
            "assert esolangs.run('brainfuck', ',.', stdin='é').output == 'é'; "
            "assert esolangs.run('brainfuck', ',.', stdin='é', "
            "isolated=True).output == 'é'; "
            "assert esolangs.run('brainfuck', ',.', stdin='é', "
            "limits=esolangs.ExecutionLimits(max_output=1)).output == 'é'",
        ],
        env={
            **os.environ,
            "PYTHONHOME": str(tmp_path / "missing-home"),
            "PYTHONIOENCODING": "utf-16",
        },
        check=True,
        timeout=10,
    )


@pytest.mark.medium
def test_worker_preserves_parent_python_startup_policy(tmp_path) -> None:
    executable = sys._base_executable
    userbase = tmp_path / "user-base"
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("PYTHON")
    }
    env["PYTHONUSERBASE"] = str(userbase)
    site_path = subprocess.check_output(
        [executable, "-S", "-c", "import site; print(site.getusersitepackages())"],
        env=env,
        text=True,
        timeout=10,
    ).strip()
    usersite = Path(site_path)
    assert usersite.is_relative_to(userbase)
    usersite.mkdir(parents=True)
    package_root = Path(esolangs.__file__).resolve().parent.parent
    probe = """
import subprocess
import sys
sys.path.insert(0, sys.argv[1])
import esolangs
assert sys.prefix == sys.base_prefix
if sys.flags.isolated:
    # Give the worker a temporary default user site without changing HOME.
    spawn = subprocess.Popen
    def with_user_site(argv, **options):
        options['env']['PYTHONUSERBASE'] = sys.argv[2]
        return spawn(argv, **options)
    subprocess.Popen = with_user_site
cap = esolangs.ExecutionLimits(max_output=1)
for options in ({}, {'isolated': True}, {'limits': cap}):
    output = esolangs.run('brainfuck', ',.', stdin='é', **options).output
    if output != 'é':
        raise AssertionError(output)
"""

    def run(*flags: str) -> None:
        result = subprocess.run(
            [executable, *flags, "-c", probe, str(package_root), str(userbase)],
            env=env,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert (result.returncode, result.stdout) == (0, b""), result.stderr

    hook = usersite / "usercustomize.py"
    for with_hook in (False, True):
        if with_hook:
            hook.write_text("print('user-site startup')\n")
            output = subprocess.check_output(
                [executable, "-c", "pass"], env=env, timeout=10
            )
            assert b"user-site startup" in output
        for flag in ("-s", "-I", "-S"):
            run(flag)

    observed = tmp_path / "startup.jsonl"
    cache = str(tmp_path / "cache prefix")
    hook.write_text(f"""\
import json
import sys
policy = [
    sys.dont_write_bytecode, sys.pycache_prefix, sys.flags.optimize,
    sys.get_int_max_str_digits(),
]
with open({str(observed)!r}, 'a', encoding='utf-8') as log:
    log.write(json.dumps(policy) + '\\n')
""")
    digits = sys.int_info.default_max_str_digits
    for flags, policy in (
        ((), [False, None, 0, digits]),
        (("-B", "-X", "int_max_str_digits=640"), [True, None, 0, 640]),
        (
            ("-OO", "-X", f"pycache_prefix={cache}", "-X", "int_max_str_digits=0"),
            [False, cache, 2, 0],
        ),
    ):
        observed.unlink(missing_ok=True)
        run(*flags)
        assert [json.loads(line) for line in observed.read_text().splitlines()] == [
            policy
        ] * 3


@pytest.mark.medium
@pytest.mark.parametrize(
    "options",
    [{"isolated": True}, {"limits": esolangs.ExecutionLimits(max_output=1)}],
    ids=["isolated", "output-cap"],
)
def test_worker_uses_parent_string_paths_in_order(
    monkeypatch, tmp_path, options
) -> None:
    class ImportPath(str):
        def __repr__(self) -> str:
            return "unbound_path()"

        def __str__(self) -> str:
            return str(tmp_path)

    (tmp_path / "esolangs.py").write_text("raise RuntimeError('wrong import path')\n")
    package_root = str(Path(esolangs.__file__).resolve().parent.parent)
    monkeypatch.setattr(
        sys, "path", [tmp_path, ImportPath(package_root), str(tmp_path), *sys.path]
    )
    result = esolangs.run(REFERENCE, ",.", stdin="Q", **options)
    assert result.output == "Q"


@pytest.mark.parametrize("timeout", [0, float("inf")])
def test_refuses_an_invalid_deadline(timeout) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            REFERENCE,
            "",
            limits=esolangs.ExecutionLimits(execution_timeout=timeout),
            isolated=True,
        )


def test_decode_missing_result_and_notes() -> None:
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        _decode('{"output": "abc"}\n', expired=False)
    assert caught.value.partial_output == "abc"
    payload = {
        "error": "ProgramError",
        "args": ["bad"],
        "notes": ["row 1"],
        "cause": None,
        "suppress_context": False,
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


def test_bulk_transport_error_kills_and_reaps_child(monkeypatch) -> None:
    from esolangs.runtime import _isolated

    calls = []

    class Child:
        returncode = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def communicate(self, *_args, **_kwargs):
            calls.append("communicate")
            raise KeyboardInterrupt

        def kill(self):
            calls.append("kill")

        def wait(self):
            calls.append("wait")
            self.returncode = -1

        def poll(self):
            return self.returncode

    monkeypatch.setattr(
        _isolated.subprocess, "Popen", lambda *_args, **_kwargs: Child()
    )
    with pytest.raises(KeyboardInterrupt):
        _isolated.execute_isolated(REFERENCE, "").unwrap()
    assert calls == ["communicate", "kill", "wait"]


@pytest.mark.medium
@pytest.mark.skipif(
    not hasattr(signal, "pthread_kill"), reason="requires POSIX thread signals"
)
@pytest.mark.parametrize("phase", ["source", "stdin", "bulk", "streaming"])
def test_worker_wait_handles_sigint_sent_to_another_thread(phase) -> None:
    code = r"""
import signal
import subprocess
import sys
import threading
from io import StringIO
from time import monotonic

from esolangs import ExecutionLimits, Language
from esolangs.runtime import _acquire, _isolated

phase, language = sys.argv[1:]
started = []
children = []
release = threading.Event()
acquisition_finished = threading.Event()

def interrupt(target):
    assert target is not None and target != threading.main_thread().ident

    def send():
        started.append(monotonic())
        signal.pthread_kill(target, signal.SIGINT)

    sender = threading.Timer(0.05, send)
    sender.daemon = True
    sender.start()

class BlockedRead:
    def __init__(self, text):
        self.text = text

    def read(self):
        interrupt(threading.get_ident())
        release.wait()
        return self.text

parked = threading.Thread(target=release.wait, daemon=True)
parked.start()
BaseChild = subprocess.Popen
BaseQueue = _isolated.Queue
BaseThread = _acquire.Thread

class AcquiringThread(BaseThread):
    def run(self):
        try:
            super().run()
        finally:
            acquisition_finished.set()

class QuietChild(BaseChild):
    def __init__(self, argv, **kwargs):
        probe = "import sys, time; sys.stdin.readline(); time.sleep(4)"
        super().__init__([sys.executable, "-c", probe], **kwargs)
        children.append(self)

    def communicate(self, *args, **kwargs):
        if phase == "bulk" and (args or kwargs.get("input")):
            interrupt(parked.ident)
        return super().communicate(*args, **kwargs)

class ObservedQueue(BaseQueue):
    def get(self, *args, **kwargs):
        if not started and not hasattr(self, "signal_armed"):
            self.signal_armed = True
            interrupt(parked.ident)
        return super().get(*args, **kwargs)

_isolated.subprocess.Popen = QuietChild
_isolated.Queue = ObservedQueue
if phase == "source":
    _acquire.Thread = AcquiringThread
program = BlockedRead(",.") if phase == "source" else ",."
stdin = BlockedRead("A") if phase == "stdin" else StringIO("A")
limits = ExecutionLimits(
    total_timeout=3, max_output=1 if phase == "streaming" else None
)
api = Language(language)
try:
    api.execute(program, stdin=stdin, limits=limits)
except KeyboardInterrupt:
    assert len(started) == 1
    assert monotonic() - started[0] < 1.5, "SIGINT waited for the worker deadline"
    if phase == "source":
        assert stdin.tell() == 0
        release.set()
        assert acquisition_finished.wait(1.5), "source acquisition did not finish"
        assert stdin.tell() == 0, "cancelled source acquisition consumed stdin"
    if phase in {"source", "stdin"}:
        assert not children
    else:
        child, = children
        assert child.poll() == -signal.SIGKILL, "worker was not killed and reaped"
else:
    raise AssertionError("SIGINT did not interrupt execute")
finally:
    release.set()
    for child in children:
        if child.poll() is None:
            child.kill()
            child.wait()
if phase == "source":
    _isolated.subprocess.Popen = BaseChild
    _isolated.Queue = BaseQueue
    _acquire.Thread = BaseThread
    assert api.run(StringIO(",."), stdin=stdin, limits=limits).output == "A"
    assert stdin.tell() == 1
"""
    result = subprocess.run(
        [sys.executable, "-c", code, phase, REFERENCE],
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.medium
def test_bulk_worker_receives_a_request_larger_than_a_pipe_buffer(spawned) -> None:
    source = "_ignored_" * 20_000 + ",."
    assert esolangs.run(REFERENCE, source, stdin="A", isolated=True).output == "A"
    (child,) = spawned
    assert child.poll() == 0
    stdin = "A" + "é\ud800\U000103ff" * 8192
    limits = esolangs.ExecutionLimits(max_steps=2, preparation_timeout=3)
    result = esolangs.run(REFERENCE, ",.", stdin=stdin, limits=limits)
    assert (result.output, result.steps, result.input_reads) == ("A", 2, 1)
    assert [child.poll() for child in spawned] == [0, 0]


@pytest.mark.parametrize("streaming", [False, True])
def test_worker_reaps_if_transport_thread_start_is_interrupted(
    monkeypatch, spawned, streaming
) -> None:
    from esolangs.runtime import _isolated, _worker_pipe

    class InterruptedThread(Thread):
        def start(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(
        _isolated if streaming else _worker_pipe, "Thread", InterruptedThread
    )
    with pytest.raises(KeyboardInterrupt):
        _isolated._launch("{}", monotonic() + 4, max_output=1 if streaming else None)
    (child,) = spawned
    assert child.poll() is not None


def test_unknown_error_reconstructs_suggestions() -> None:
    payload = {
        "error": "UnknownLanguageError",
        "args": ["brainfuk", [REFERENCE]],
        "execution": None,
        "notes": [],
        "cause": None,
        "suppress_context": False,
        "output_limit": False,
    }
    with pytest.raises(esolangs.UnknownLanguageError) as caught:
        _decode(json.dumps(payload), expired=False)
    assert caught.value.language == "brainfuk"
    assert caught.value.suggestions == (REFERENCE,)


@pytest.mark.medium
@pytest.mark.parametrize("limit", [0, 1, 4097])
def test_output_limit_stops_an_infinite_writer_and_reaps(limit, spawned) -> None:
    with pytest.raises(esolangs.ExecutionCapError, match="output limit") as caught:
        esolangs.run(
            REFERENCE,
            "+[.]",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_output=limit),
        )
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
        lambda: esolangs.run(
            REFERENCE, "+[.]", limits=esolangs.ExecutionLimits(max_output=1)
        ),
        lambda: language.prepare("+[.]").run(
            limits=esolangs.ExecutionLimits(max_output=1)
        ),
    ):
        with pytest.raises(esolangs.ExecutionCapError) as caught:
            call()
        assert str(caught.value) == str(outcome.error)
        assert caught.value.bound == outcome.bound == "max_output"
        assert caught.value.partial_output == outcome.observation.output == "\x01"
    assert len(spawned) == 3
    with pytest.raises(esolangs.ArgumentError, match="max_memory must be a positive"):
        esolangs.run(REFERENCE, "+", limits=esolangs.ExecutionLimits(max_memory=0))


@pytest.mark.medium
def test_output_limit_beyond_the_decimal_rendering_limit_accepts_small_output() -> None:
    assert (
        esolangs.run(
            REFERENCE,
            "++.",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_output=10**5000),
        ).output
        == "\x02"
    )


@pytest.mark.medium
def test_capped_timeout_retains_output_and_reaps(spawned) -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs.run(
            REFERENCE,
            "+.[]",
            limits=esolangs.ExecutionLimits(execution_timeout=1, max_output=10),
            isolated=True,
        )
    assert caught.value.partial_output == "\x01"
    assert spawned[0].poll() is not None


@pytest.mark.parametrize("limit", [-1, True, 1.5, "1"])
def test_refuses_invalid_output_limits(limit) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_output"):
        esolangs.run(
            REFERENCE,
            "",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_output=limit),
        )


def test_capped_worker_splits_and_truncates_a_single_large_write(
    monkeypatch, capsys
) -> None:
    import io
    import sys

    def dump(*_args, io_factory, **_kwargs):
        output = io_factory("")
        output.print_str("λ" * 10_000)
        return output.getvalue()

    payload = encode_request(REFERENCE, "", "", max_output=8193)
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
        esolangs.run(
            REFERENCE,
            "+.,",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_output=2),
        )
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
            _bounded_output(child, "{}", monotonic() + 1).unwrap()
        assert caught.value.partial_output == "prefix"
        assert child.killed
        assert child.reaped


def test_broken_request_pipe_still_drains_worker_failure(protocol_child) -> None:
    from io import StringIO

    from esolangs.runtime._failure_wire import _failure_wire
    from esolangs.runtime._isolated import _bounded_output

    class ClosedInput(StringIO):
        def write(self, _text):
            raise BrokenPipeError

    error = esolangs.InterpreterLimitError("worker rejected request")
    child = protocol_child(
        ['{"output":"prefix"}\n', worker_dumps(_failure_wire(error))]
    )
    child.stdin = ClosedInput()
    with pytest.raises(
        esolangs.InterpreterLimitError, match="worker rejected request"
    ) as caught:
        _bounded_output(child, "{}", monotonic() + 1).unwrap()
    assert caught.value.partial_output == "prefix"
    assert caught.value.observation is None
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
        _bounded_output(child, "{}", monotonic() + 1).unwrap()
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
    from esolangs.runtime import _isolated, _worker_pipe
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

        def communicate(self, request=None):
            if request is None:
                calls.append(None)
            return json.dumps(
                {
                    "result": "",
                    "execution": encode_result(
                        ExecutionResult("", 0, 0, 0, completion=HALTED_REPORT)
                    ),
                }
            ), ""

    def spawn(*_args, **_kwargs):
        clock[0] += startup
        return Child()

    def bounded(_child, _request, deadline):
        calls.append(deadline - clock[0])
        return esolangs.ExecutionOutcome(
            "completed", ExecutionResult("", 0, 0, 0, completion=HALTED_REPORT)
        )

    wait_for_event = _worker_pipe.wait_for_event

    def record_wait(event, deadline, *, clock):
        calls.append(deadline - clock())
        return wait_for_event(event, deadline, clock=clock)

    monkeypatch.setattr(_isolated, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    monkeypatch.setattr(_isolated, "_bounded_output", bounded)
    monkeypatch.setattr(_worker_pipe, "wait_for_event", record_wait)
    if startup > 1:
        with pytest.raises(esolangs.ExecutionTimeoutError):
            _launch("{}", 1, max_output=max_output).unwrap()
        assert calls == ["kill", None]
    else:
        assert _launch("{}", 1, max_output=max_output).unwrap().output == ""
        assert calls == [pytest.approx(0.6)]


@pytest.mark.parametrize("completed_at", [2, 4, 5])
def test_bulk_deadline_uses_the_transports_completion_time(
    monkeypatch, completed_at
) -> None:
    from esolangs.runtime import _worker_pipe

    clock = [0.0]

    class Child:
        def communicate(self, request):
            assert request == "{}"
            clock[0] = completed_at
            return "output", ""

    def wait_for_event(event, deadline, *, clock):
        # Give the coordinator the result after transfer, even if it was late.
        assert event.wait(timeout=1)
        assert (deadline, clock()) == (4, completed_at)
        return True

    monkeypatch.setattr(_worker_pipe, "wait_for_event", wait_for_event)
    assert _worker_pipe.communicate(Child(), "{}", 4, clock=lambda: clock[0]) == (
        "output",
        completed_at >= 4,
    )


@pytest.mark.parametrize(
    ("preparation", "total", "startup", "bound"),
    [
        (2, 4, 0, None),
        (2, 4, 3, "preparation_timeout"),
        (2, 4, 5, "preparation_timeout"),
        (4, 2, 5, "total_timeout"),
        (2, 2, 5, "total_timeout"),
    ],
)
def test_worker_startup_reports_the_first_expired_deadline(
    monkeypatch, spawned, preparation, total, startup, bound
) -> None:
    from esolangs.runtime import _isolated

    displacement = 0
    spawn = _isolated.subprocess.Popen

    def spawn_with_delay(*args, **kwargs):
        nonlocal displacement
        child = spawn(*args, **kwargs)
        displacement = startup
        return child

    monkeypatch.setattr(_isolated, "monotonic", lambda: monotonic() + displacement)
    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn_with_delay)
    limits = esolangs.ExecutionLimits(
        preparation_timeout=preparation, total_timeout=total
    )
    outcome = esolangs.execute(REFERENCE, ",.", stdin="A", limits=limits)
    assert outcome.bound == bound
    if bound is None:
        assert outcome.unwrap().output == "A"
    else:
        assert isinstance(outcome.error, esolangs.ExecutionTimeoutError)
        assert outcome.error.observation is None
        assert outcome.observation == ExecutionResult("", None, None, None)
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


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
    from esolangs.runtime import _isolated, _raster_wire
    from esolangs.runtime._raster_wire import _raster_rows, _raster_transport

    image = esolangs.Raster(rows)
    runs = _raster_transport(image)
    assert runs is _raster_transport(image)
    with monkeypatch.context() as patch:

        def refuse_hash(_self):
            pytest.fail("worker transport hashed an image's pixels")

        patch.setattr(_raster_wire, "_BLOCK", 2)
        patch.setattr(esolangs.Raster, "__hash__", refuse_hash)
        distinct = esolangs.Raster(rows)
        checked = _raster_transport(distinct, lambda: False)
        assert checked == runs
        assert checked is _raster_transport(distinct)
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
                completion=HALTED_REPORT,
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
    payload = encode_request(
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
    request = encode_request(
        language,
        program.source,
        esolangs.encode_inputs(language, [0]),
        settings=program.settings,
        max_output=100,
        termination=True,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    ordinary = esolangs.run(
        REFERENCE, "+.", limits=esolangs.ExecutionLimits(max_steps=2)
    )
    _worker()
    assert (
        esolangs.run(REFERENCE, "+.", limits=esolangs.ExecutionLimits(max_steps=2))
        == ordinary
    )
    assert not hasattr(_execution_operations, "io_factory")
    assert not hasattr(vm, "io_factory")
    assert _decode(capsys.readouterr().out, expired=False).decision.halts is True
