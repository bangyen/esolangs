"""Mutation baselines and probes cannot overrun the remaining sweep budget."""

import json
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts import mutants
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf")])
def test_invalid_budget_is_rejected_before_opening_output(tmp_path, capsys, budget):
    out = tmp_path / "out.jsonl"
    with pytest.raises(ValueError, match="--budget must be positive and finite"):
        mutants.sweep(["test"], out, 1, budget)
    with pytest.raises(SystemExit) as caught:
        mutants.main(["test", "--out", str(out), "--budget", str(budget)])
    assert caught.value.code == 2
    assert "--budget must be positive and finite" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_count_is_rejected_before_opening_output(tmp_path, capsys, count):
    out = tmp_path / "out.jsonl"
    message = "--per-language must be positive"
    with pytest.raises(ValueError, match=message):
        mutants.candidates("test", count)
    with pytest.raises(ValueError, match=message):
        mutants.sweep(["test"], out, count, 10)
    with pytest.raises(SystemExit) as caught:
        mutants.main(["test", "--out", str(out), "--per-language", str(count)])
    assert caught.value.code == 2
    assert message in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize(
    ("registered", "message"),
    [
        (False, "no registered language has this package"),
        (True, "no compiling generator mutants"),
    ],
)
def test_all_packages_are_checked_before_any_baseline_or_output(
    tmp_path, monkeypatch, capsys, registered, message
):
    from esolangs.registry import LANGUAGES

    first = LANGUAGES[REFERENCE].id.replace("-", "_")
    second = (
        next(
            lang.id.replace("-", "_")
            for lang in LANGUAGES.values()
            if not lang.has_backend and not mutants.generator_files(lang.id)
        )
        if registered
        else "no_such_mutation_package"
    )
    packages = [first, second]
    out = tmp_path / "existing.jsonl"
    out.write_text("previous\n")
    monkeypatch.setattr(mutants, "_run", lambda *_: pytest.fail("ran a baseline"))
    monkeypatch.setattr(mutants, "_in_worktree", lambda: True)

    with pytest.raises(ValueError, match=message):
        mutants.sweep(packages, out, 1, 10)
    with pytest.raises(SystemExit) as caught:
        mutants.main([*packages, "--out", str(out), "--per-language", "1"])
    assert caught.value.code == 2
    assert f"{second}: {message}" in capsys.readouterr().err
    assert out.read_text() == "previous\n"
    assert list(tmp_path.iterdir()) == [out]


def test_preflight_uses_the_sweep_budget(tmp_path, monkeypatch, capsys):
    clock = iter([0, 11])
    monkeypatch.setattr(mutants, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(mutants, "_pytest", lambda _: [])
    monkeypatch.setattr(mutants, "candidates", lambda *_: [object()])
    monkeypatch.setattr(mutants, "_run", lambda *_: pytest.fail("ran a baseline"))
    out = tmp_path / "out.jsonl"
    assert mutants.sweep(["test"], out, 1, 10) == 124
    assert "global budget spent during preflight" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("overlap", ["report", "baseline symlink", "report hardlink"])
def test_mutation_outputs_cannot_replace_source(tmp_path, monkeypatch, capsys, overlap):
    languages = tmp_path / "src" / "esolangs" / "languages"
    source = languages / "probe" / "generator.py"
    source.parent.mkdir(parents=True)
    original = b"NUMBER = 2\n"
    source.write_bytes(original)
    report = tmp_path / "out.jsonl"
    log = tmp_path / "out-probe-baseline.log"
    if overlap == "report":
        report = source
    elif overlap == "report hardlink":
        report.hardlink_to(source)
    else:
        try:
            log.symlink_to(source)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
    monkeypatch.setattr(mutants, "ROOT", tmp_path)
    monkeypatch.setattr(mutants, "LANGUAGES", languages)
    monkeypatch.setattr(mutants, "_pytest", lambda _: [])
    monkeypatch.setattr(mutants, "_in_worktree", lambda: True)
    monkeypatch.setattr(mutants, "_run", lambda *_: pytest.fail("ran a baseline"))

    with pytest.raises(SystemExit) as caught:
        mutants.main(["probe", "--out", str(report), "--per-language", "1"])
    assert caught.value.code == 2
    diagnostic = capsys.readouterr().err
    assert f"would overwrite source {source.resolve()}" in diagnostic
    assert str(log if overlap == "baseline symlink" else report) in diagnostic
    assert source.read_bytes() == original
    if overlap == "baseline symlink":
        assert log.is_symlink()
        assert not report.exists()


@pytest.mark.parametrize("duration_only", [False, True])
def test_an_inconclusive_verdict_fails_a_sweep(
    tmp_path, monkeypatch, capsys, duration_only
):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    mutant = {"file": "source.py", "line": 1, "col": 8, "old": "1", "new": "2"}
    outcome = ("killed", "duration") if duration_only else ("inconclusive", "")
    results = iter([("survived", "baseline"), outcome])
    monkeypatch.setattr(mutants, "ROOT", tmp_path)
    monkeypatch.setattr(mutants, "_pytest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(mutants, "_run", lambda *_args: next(results))
    monkeypatch.setattr(mutants, "candidates", lambda *_args: [mutant])
    monkeypatch.setattr(mutants, "_duration_flips", lambda _: ["test::slow"])
    out = tmp_path / "out.jsonl"

    assert mutants.sweep(["test"], out, 1, 10) == 1
    record = json.loads(out.read_text())
    assert record["status"] == "inconclusive"
    assert record.get("duration_flips") == (["test::slow"] if duration_only else None)
    assert "inconclusive" in capsys.readouterr().err
    assert source.read_text() == "value = 1\n"


@pytest.mark.parametrize("cutoff", ["probe", "global", "streak"])
def test_sweep_budget_clips_probes_and_restores_source(
    tmp_path, monkeypatch, capsys, cutoff
):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    mutant = {"file": "source.py", "line": 1, "col": 8, "old": "1", "new": "2"}
    clock = iter(
        [0, 0, 0, 0, 1, 2, 11] if cutoff == "global" else [0, 0, 0, 0, 1, 2, 2, 2, 2]
    )
    monkeypatch.setattr(mutants, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(mutants, "ROOT", tmp_path)
    monkeypatch.setattr(mutants, "_pytest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(mutants, "_clear_bytecode", lambda: None)
    count = {"probe": 1, "global": 2, "streak": 4}[cutoff]
    monkeypatch.setattr(mutants, "candidates", lambda *_args: [mutant] * count)
    limits = []

    def run(command, timeout, _termination):
        limits.append(timeout)
        if len(limits) == 1:
            assert "-x" not in command
            return "survived", "baseline"
        assert "-x" in command
        assert source.read_text() == "value = 2\n"
        return ("survived", "") if cutoff == "global" else ("timeout", "")

    monkeypatch.setattr(mutants, "_run", run)
    out = tmp_path / "out.jsonl"
    assert mutants.sweep(["test"], out, count, 10) == 124
    assert "mutation sweep incomplete" in capsys.readouterr().err
    completed = 3 if cutoff == "streak" else 1
    assert limits == [10, *([8] * completed)]
    status = "survived" if cutoff == "global" else "timeout"
    assert [json.loads(row)["status"] for row in out.read_text().splitlines()] == [
        status
    ] * completed
    assert source.read_text() == "value = 1\n"
    assert (tmp_path / "out-test-baseline.log").read_text() == "baseline"


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX termination signals")
def test_sigterm_stops_the_worker_and_preserves_the_original_bytes(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"value = 1 + 2\r\n")
    ready = tmp_path / "worker-pid"
    worker = """
import os
import time
from pathlib import Path

assert Path("source.py").read_bytes() == b"value = 1 - 2\\r\\n"
Path("worker-pid").write_text(str(os.getpid()))
time.sleep(10)
"""
    driver = f"""
import sys
from pathlib import Path

from scripts import mutants

mutants.ROOT = Path(sys.argv[1])
mutants._pytest = lambda _: [sys.executable, "-c", {worker!r}]
mutants.candidates = lambda *_: [
    {{"file": "source.py", "line": 1, "col": 10, "old": "+", "new": "-"}}
]
run = mutants._run
mutants._run = lambda command, timeout, termination: (
    run(command, timeout, termination) if "-x" in command else ("survived", "")
)
sys.exit(mutants.sweep(["sample"], mutants.ROOT / "out.jsonl", 1, 15))
"""
    with subprocess.Popen(
        [sys.executable, "-c", driver, str(tmp_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            deadline = time.monotonic() + 5
            pid = ""
            while process.poll() is None and time.monotonic() < deadline:
                if ready.is_file() and (pid := ready.read_text()):
                    break
                time.sleep(0.02)
            assert pid, "mutation worker did not reach the changed source"
            process.send_signal(signal.SIGTERM)
            output = process.communicate(timeout=5)
            assert process.returncode == 128 + signal.SIGTERM, output
        finally:
            if process.poll() is None:
                process.kill()
    assert source.read_bytes() == b"value = 1 + 2\r\n"
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid), 0)
