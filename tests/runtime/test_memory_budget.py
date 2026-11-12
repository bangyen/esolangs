"""Memory exhaustion is a worker failure, never a termination answer."""

import io
import json
import sys

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.runtime import _isolated
from esolangs.runtime._isolated import _worker
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

    monkeypatch.setattr(_isolated, "_limit_memory", reject)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(_isolated._request_wire(REFERENCE, "", "", max_memory=1))
        ),
    )
    _worker()
    with pytest.raises(esolangs.InterpreterLimitError, match=message) as caught:
        _decode(capsys.readouterr().out, expired=False)
    assert caught.value.observation is None


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

    from esolangs.runtime._isolated import _limit_memory

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


def test_worker_reports_a_translated_memory_error_as_the_cap(
    monkeypatch, capsys
) -> None:
    """``run`` turns MemoryError into its own error; the worker must see through it."""

    def explode(*_args: object, **_kwargs: object) -> None:
        raise MemoryError

    monkeypatch.setattr(_execution_runtime, "invoke", explode)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps(_isolated._request_wire(REFERENCE, "+", ""))),
    )
    _worker()
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit"):
        _decode(capsys.readouterr().out, expired=False)


def test_successful_worker_budget_retains_output_protocol(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(_isolated, "_limit_memory", calls.append)
    request = _isolated._request_wire(
        REFERENCE, "+.", "", max_memory=_BUDGET, max_steps=2
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    _worker()
    assert calls == [_BUDGET]
    assert _decode(capsys.readouterr().out, expired=False).output == "\x01"
