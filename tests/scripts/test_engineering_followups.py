"""Preflight cleanup, timing cohorts, and reproducible archive evidence."""

import io
import json
import os
import subprocess
import sys
import tarfile
import time

import pytest

from scripts import _atomic, _verify_process, normalize_sdist, report_generator_timings
from scripts.pytest_durations import Recorder
from scripts.refresh_ci_timings import refresh


def test_preflight_reaps_descendants(tmp_path):
    marker = tmp_path / "marker"
    worker = (
        "from pathlib import Path; import time; time.sleep(1); "
        f"Path({str(marker)!r}).touch()"
    )
    command = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{worker!r}]); time.sleep(10)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        _verify_process.run_bounded([sys.executable, "-c", command], timeout=0.2)
    assert (
        _verify_process.run_bounded(
            [sys.executable, "-c", "print('ok')"], capture_output=True
        ).stdout.strip()
        == "ok"
    )
    time.sleep(1.1)
    assert not marker.exists()


def test_atomic_failure_preserves_file(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.write_text("previous")

    def fail(*_args):
        raise OSError("interrupted")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="interrupted"):
        _atomic.write_text(path, "new")
    assert path.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [path]


def test_mixed_timing_cohorts_preserve_fixture(tmp_path):
    runs = [tmp_path / "a", tmp_path / "b"]
    for index, run in enumerate(runs):
        recorder = Recorder(run / "timings.json")
        recorder.collected.add("test")
        recorder.finished.add("test")
        recorder.durations["test"] = 1
        recorder.pytest_sessionfinish(0)
        path = run / "timings.json.meta.json"
        metadata = json.loads(path.read_text())
        metadata["run"]["platform"] = str(index)
        path.write_text(json.dumps(metadata))
    output = tmp_path / "fixture"
    output.write_text("old")
    with pytest.raises(ValueError, match="mixed timing"):
        refresh(runs, ["test"], output, 1)
    assert output.read_text() == "old"


def test_generator_environment_change_is_not_slowdown():
    def run(duration, platform):
        return [
            {
                "language": "test",
                "truth_table": "01",
                "generation_ns_best": duration,
                "schema": 6,
                "provenance": {
                    "platform": platform,
                    "python": "3.14",
                    "machine": "test",
                    "harness": 1,
                },
            }
        ]

    before, previous, current = (
        run(20_000_000, "a"),
        run(40_000_000, "a"),
        run(40_000_000, "a"),
    )
    assert "Sustained slowdowns" in report_generator_timings.report(
        current, [before, previous]
    )
    assert "incompatible environments" in report_generator_timings.report(
        run(40_000_000, "b"), [before, previous]
    )


def test_sdist_normalization_preserves_payload(tmp_path):
    paths = [tmp_path / "one.tar.gz", tmp_path / "two.tar.gz"]
    for index, path in enumerate(paths):
        with tarfile.open(path, "w:gz") as archive:
            entry = tarfile.TarInfo("package/source.py")
            entry.size = 7
            entry.mtime = index + 100
            archive.addfile(entry, io.BytesIO(b"print()"))
        normalize_sdist.normalize(path, 42)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    with tarfile.open(paths[0]) as archive:
        assert archive.extractfile("package/source.py").read() == b"print()"
        assert archive.getmember("package/source.py").mtime == 42
