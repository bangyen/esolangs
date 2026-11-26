"""Memory exhaustion is a worker failure, never a termination answer."""

import io
import json
import sys

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.runtime import _worker_main
from esolangs.runtime._request_wire import encode_request
from esolangs.runtime._worker_main import _worker
from tests.support.cli_support import call_both
from tests.support.reference import REFERENCE
from tests.support.vm_support import _BUDGET, _LINUX
from tests.support.worker_response import _decode


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_cli_budget_runs(tmp_path, capsys) -> None:
    path = tmp_path / "source.bf"
    path.write_text("+.")
    output, _ = call_both(
        [
            "run",
            "--isolated",
            "--max-memory",
            str(_BUDGET),
            "--max-steps",
            "2",
            REFERENCE,
            str(path),
        ],
        capsys,
    )
    assert output == "\x01"


@pytest.mark.parametrize(
    ("error", "message"),
    [(MemoryError, "memory limit"), (OSError, "cannot enforce memory limit")],
)
def test_worker_memory_failure_retains_protocol(
    monkeypatch, capsys, error, message
) -> None:
    def reject(_limit: int) -> None:
        raise error("limit unavailable")

    monkeypatch.setattr(_worker_main, "_limit_memory", reject)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps(encode_request(REFERENCE, "", "", max_memory=1))),
    )
    _worker()
    expected = (
        esolangs.ExecutionCapError
        if error is MemoryError
        else esolangs.InterpreterLimitError
    )
    with pytest.raises(expected, match=message) as caught:
        _decode(capsys.readouterr().out, expired=False)
    assert caught.value.observation is None
    # Only the cap running out is a budget; failing to install it is not.
    assert getattr(caught.value, "bound", None) == (
        "max_memory" if error is MemoryError else None
    )


def test_cli_invalid_budget_precedes_path_reads(capsys) -> None:
    command = "run"
    options = ["--isolated"]
    with pytest.raises(SystemExit, match=r"^2$"):
        call_both(
            [command, *options, "--max-memory", "0", REFERENCE, "missing"], capsys
        )
    assert "cannot read" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("hard", "requested", "ceiling"), [(-1, 200, 200), (100, 200, 100), (300, 200, 200)]
)
def test_memory_ceiling_preserves_inherited_hard_limit(
    monkeypatch, hard, requested, ceiling
) -> None:
    from types import SimpleNamespace

    from esolangs.runtime._worker_main import _limit_memory

    calls = []
    resource = SimpleNamespace(
        RLIMIT_AS=9,
        RLIM_INFINITY=-1,
        getrlimit=lambda _kind: (hard, hard),
        setrlimit=lambda kind, limits: calls.append((kind, limits)),
    )
    monkeypatch.setitem(sys.modules, "resource", resource)
    _limit_memory(requested)
    assert calls == [(9, (ceiling, hard))]


def test_worker_retains_the_uncapped_memory_failure_evidence(
    monkeypatch, capsys
) -> None:
    """Uncapped allocation failure retains the native diagnostic and counters."""

    def explode(_runner, _program, io_port) -> None:
        io_port.print_char(chr(io_port.input_char()))
        raise MemoryError

    monkeypatch.setattr(_execution_runtime, "invoke", explode)
    native = esolangs.run(REFERENCE, "+", stdin="A")
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps(encode_request(REFERENCE, "+", "A"))),
    )
    _worker()
    with pytest.raises(
        esolangs.InterpreterLimitError, match="ran out of memory"
    ) as caught:
        _decode(capsys.readouterr().out, expired=False)
    # No max_memory was passed, so no caller budget ran out.
    assert not isinstance(caught.value, esolangs.ExecutionBudgetError)
    assert caught.value.partial_output == "A"
    assert caught.value.observation == native.observation
    assert caught.value.__notes__ == native.error.__notes__


def test_successful_worker_budget_retains_output_protocol(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(_worker_main, "_limit_memory", calls.append)
    request = encode_request(REFERENCE, "+.", "", max_memory=_BUDGET, max_steps=2)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    _worker()
    assert calls == [_BUDGET]
    assert _decode(capsys.readouterr().out, expired=False).output == "\x01"
