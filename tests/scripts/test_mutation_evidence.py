"""Mutation scores identify the harness inputs; weekly limits reap workers."""

import json
import subprocess
import sys
import time

import pytest

from scripts import _mutation_evidence as evidence
from scripts import mutate_weekly as weekly


def test_report_hashes_actual_source_tests_and_tool_version(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "source.py").write_text("value = 1\n")
    (tmp_path / "tests/test_source.py").write_text("assert 1\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    monkeypatch.setattr(evidence, "source_identity", lambda: {"commit": "fixture"})
    monkeypatch.setattr(evidence.importlib.metadata, "version", lambda _name: "3.8.0")
    first = evidence.provenance(tmp_path)
    (tmp_path / "source.py").write_text("value = 2\n")
    second = evidence.provenance(tmp_path)
    assert first["source_sha256"] != second["source_sha256"]
    assert first["tests_sha256"] == second["tests_sha256"]
    path = tmp_path / "score.json"
    evidence.publish(path, {"killed": 1, "total": 2}, second)
    record = json.loads(path.read_text())
    assert record["provenance"]["mutmut"] == "3.8.0"
    assert record["provenance"]["checkout"]["commit"] == "fixture"
    with pytest.raises(ValueError, match="mutmut version"):
        evidence.publish(path, {}, {"mutmut": None})
    assert json.loads(path.read_text()) == record


@pytest.mark.medium
@pytest.mark.parametrize("interrupted", [False, True])
def test_weekly_supervisor_reaps_on_timeout_or_interruption(
    tmp_path, monkeypatch, interrupted
):
    marker = tmp_path / "tick"
    worker = (
        "import time; from pathlib import Path\nwhile True:\n "
        f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n "
        "time.sleep(.01)\n"
    )
    command = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{worker!r}]); time.sleep(10)"
    )
    original = subprocess.Popen

    def spawn(_command, **kwargs):
        process = original([sys.executable, "-c", command], **kwargs)
        if interrupted:
            wait = process.wait
            first = True

            def interrupt(*args, **kwargs):
                nonlocal first
                if first:
                    first = False
                    deadline = time.monotonic() + 1
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    raise KeyboardInterrupt
                return wait(*args, **kwargs)

            process.wait = interrupt
        return process

    monkeypatch.setattr(weekly.subprocess, "Popen", spawn)
    monkeypatch.setattr(weekly, "provenance", lambda: {"mutmut": "fixture"})
    monkeypatch.setattr(weekly, "SECONDS_PER_TARGET", 0.3)
    output = tmp_path / "evidence"
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            weekly.run_target("interpreter", "fixture", output)
    else:
        assert not weekly.run_target("interpreter", "fixture", output)
    assert json.loads((output / "status.json").read_text())["status"] == (
        "interrupted" if interrupted else "timeout"
    )
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before


def score_fixture():
    provenance = {
        "checkout": {"commit": "fixture"},
        "python": "fixture",
        "platform": "fixture",
        "mutmut": "3.8.0",
        "source_sha256": {"source.py": "a" * 64},
        "tests_sha256": {"tests/test_source.py": "b" * 64},
        "configuration_sha256": "c" * 64,
        "limits": {"workers": 2, "per_test_alarm_seconds": 1, "baseline_seconds": 0.1},
    }
    return {
        "schema": 1,
        "kind": "interpreter",
        "target": "fixture",
        "killed": 1,
        "total": 2,
        "survivors": ["source.x_mutant_1"],
        "provenance": provenance,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", True),
        ("kind", "generator"),
        ("target", "other"),
        ("killed", 3),
        ("total", 0),
        ("total", True),
        ("survivors", [1]),
        ("survivors", ["a", "b"]),
        ("provenance", {}),
    ],
)
def test_score_validation_rejects_inconsistent_evidence(tmp_path, field, value):
    record = score_fixture()
    expected = dict(record["provenance"])
    record[field] = value
    path = tmp_path / "score.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="mutation"):
        evidence.validate(path, "interpreter", "fixture", expected)


@pytest.mark.parametrize("valid", [True, False])
def test_weekly_requires_valid_score_even_after_successful_exit(
    tmp_path, monkeypatch, valid
):
    record = score_fixture()
    expected = dict(record["provenance"])
    if not valid:
        record["provenance"] = {**expected, "mutmut": "different"}
    output = tmp_path / "output"

    class Process:
        def wait(self, timeout):  # noqa: ARG002
            (output / "score.json").write_text(json.dumps(record))
            return 0

    monkeypatch.setattr(weekly, "provenance", lambda: expected)
    monkeypatch.setattr(weekly.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    assert weekly.run_target("interpreter", "fixture", output) is valid
    status = json.loads((output / "status.json").read_text())
    assert status["status"] == ("complete" if valid else "failed")
    assert bool(status["validation_error"]) is not valid
