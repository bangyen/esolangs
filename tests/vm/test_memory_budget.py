"""Memory exhaustion is a worker failure, never a termination answer."""

import io
import sys

import pytest

import esolangs
from esolangs import _isolated
from esolangs._isolated import _decode, _worker
from tests.support.cli_support import call_both

_LINUX = sys.platform == "linux"
_BUDGET = 96 * 1024 * 1024


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_cli_budget_runs(tmp_path, capsys) -> None:
    path = tmp_path / "source.bf"
    path.write_text("+.")
    output, _ = call_both(
        ["run", "--isolated", "--max-memory", str(_BUDGET), "brainfuck", str(path)],
        capsys,
    )
    assert output == "\x01"


def test_worker_memory_failure_retains_protocol(monkeypatch, capsys) -> None:
    def reject(_limit: int) -> None:
        raise MemoryError

    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(_isolated, "_limit_memory", reject)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"program":"", "raster":false, "max_memory":1}')
    )
    _worker()
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit"):
        _decode(capsys.readouterr().out, expired=False)


def test_cli_invalid_budget_precedes_path_reads(capsys) -> None:
    command = "run"
    options = ["--isolated"]
    with pytest.raises(SystemExit, match=r"^2$"):
        call_both(
            [command, *options, "--max-memory", "0", "brainfuck", "missing"], capsys
        )
    assert "cannot read" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("hard", "requested", "ceiling"), [(-1, 200, 200), (100, 200, 100), (300, 200, 200)]
)
def test_memory_ceiling_preserves_inherited_hard_limit(
    monkeypatch, hard, requested, ceiling
) -> None:
    from types import SimpleNamespace

    from esolangs._isolated import _limit_memory

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


def test_worker_cannot_silently_drop_an_unenforceable_limit(
    monkeypatch, capsys
) -> None:
    def reject(_limit: int) -> None:
        raise OSError("limit unavailable")

    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(_isolated, "_limit_memory", reject)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"program":"", "raster":false, "max_memory":1}')
    )
    _worker()
    with pytest.raises(
        esolangs.InterpreterLimitError, match="cannot enforce memory limit"
    ):
        _decode(capsys.readouterr().out, expired=False)


def test_worker_reports_a_translated_memory_error_as_the_cap(
    monkeypatch, capsys
) -> None:
    """``run`` turns MemoryError into its own error; the worker must see through it."""

    def explode(*_args: object, **_kwargs: object) -> None:
        raise MemoryError

    # The worker installs a streaming ScriptedIO; undo it for the next test.
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(esolangs, "_run", explode)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            '{"language":"brainfuck","program":"+","raster":false,'
            '"stdin":"","seed":null}'
        ),
    )
    _worker()
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit"):
        _decode(capsys.readouterr().out, expired=False)


def test_successful_worker_budget_retains_output_protocol(monkeypatch, capsys) -> None:
    import json

    calls = []
    monkeypatch.setattr(esolangs, "ScriptedIO", esolangs.ScriptedIO)
    monkeypatch.setattr(_isolated, "_limit_memory", calls.append)
    request = {
        "program": "+.",
        "raster": False,
        "language": "brainfuck",
        "stdin": "",
        "seed": None,
        "max_memory": _BUDGET,
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    _worker()
    assert calls == [_BUDGET]
    assert _decode(capsys.readouterr().out, expired=False) == "\x01"
