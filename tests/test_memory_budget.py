"""Memory exhaustion is a worker failure, never a termination answer."""

import io
import sys
from pathlib import Path

import pytest

import esolangs
from esolangs import _isolated
from esolangs._evaluate import _evaluate
from esolangs._isolated import _decode, _worker
from tests.cli_support import call_both

_LINUX = sys.platform == "linux"
_BUDGET = 96 * 1024 * 1024


def _growing_template(doublings: int) -> str:
    return esolangs.generate("Underload", "01") + "(x)" + ":*" * doublings


@pytest.mark.medium
def test_memory_probe_template_reaches_execution() -> None:
    assert _evaluate("Underload", _growing_template(3), inputs=1, isolated=True) == "01"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "1", 1 << 63])
def test_invalid_memory_budget_precedes_source_reads(limit: object) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_memory"):
        esolangs.run("Underload", Path("missing"), isolated=True, max_memory=limit)


def test_memory_budget_requires_isolation() -> None:
    with pytest.raises(esolangs.ArgumentError, match="isolated"):
        esolangs.run("Underload", Path("missing"), max_memory=_BUDGET)


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_unsupported_platform_refuses_before_acquisition(monkeypatch, platform) -> None:
    monkeypatch.setattr(_isolated.sys, "platform", platform)
    with pytest.raises(esolangs.ArgumentError, match="Linux"):
        _evaluate(
            "Underload", Path("missing"), inputs=1, isolated=True, max_memory=_BUDGET
        )


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_budget_allows_answers_and_bound_language() -> None:
    bound = esolangs.Language("brainfuck")
    assert bound.run("+.", isolated=True, max_memory=_BUDGET, max_output=1) == "\x01"
    for language in ("brainfuck", "Vandevelo"):
        source = esolangs.generate(language, "0110")
        assert (
            _evaluate(language, source, inputs=2, isolated=True, max_memory=_BUDGET)
            == "0110"
        )


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_growing_state_fails_and_worker_is_reaped(spawned) -> None:
    source = "(A)S(x)" + ":*" * 29
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit") as caught:
        esolangs.run("Underload", source, isolated=True, timeout=10, max_memory=_BUDGET)
    assert caught.value.partial_output == "A"
    assert spawned[0].poll() is not None
    assert esolangs.run("Underload", "(ok)S", isolated=True, max_memory=_BUDGET) == "ok"


@pytest.mark.medium
@pytest.mark.skipif(not _LINUX, reason="Linux RLIMIT_AS only")
def test_memory_failure_during_evaluation_is_not_an_answer() -> None:
    with pytest.raises(esolangs.InterpreterLimitError, match="memory limit") as caught:
        _evaluate(
            "Underload",
            _growing_template(29),
            inputs=1,
            isolated=True,
            max_memory=_BUDGET,
        )
    assert "row 0" in " ".join(caught.value.__notes__)
    assert caught.value.partial_output == "0"


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


@pytest.mark.medium
@pytest.mark.parametrize("language", ["brainfuck", "Vandevelo"])
def test_evaluation_forwards_budget_without_changing_answers(
    monkeypatch, language
) -> None:
    # Exercise plumbing on every host; the Linux-only tests enforce a real cap.
    monkeypatch.setattr(_isolated.sys, "platform", "linux")
    calls = []
    target = esolangs if language == "brainfuck" else _isolated
    attribute = "_run_isolated" if language == "brainfuck" else "termination_isolated"
    runner = getattr(target, attribute)

    def capture(*args, **kwargs):
        calls.append(kwargs.pop("max_memory"))
        return runner(*args, **kwargs)

    monkeypatch.setattr(target, attribute, capture)
    bound = esolangs.Language(language)
    assert (
        _evaluate(
            bound.name,
            bound.generate("0110"),
            inputs=2,
            isolated=True,
            max_memory=_BUDGET,
        )
        == "0110"
    )
    assert calls == [_BUDGET] * 4


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
