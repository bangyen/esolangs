"""Preflight cleanup, timing cohorts, and reproducible archive evidence."""

import io
import json
import os
import subprocess
import sys
import tarfile
import time

import pytest

from scripts import _verify_process, normalize_sdist, report_generator_timings
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
        _verify_process.write_text(path, "new")
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


def test_provenance_deadline_kills_git_probe(monkeypatch):
    from scripts import benchmark

    def hung_probe(_command, **kwargs):
        return _verify_process.run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"], **kwargs
        )

    monkeypatch.setattr(benchmark, "run_bounded", hung_probe)
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        benchmark.source_identity(timeout=0.2)
    assert time.monotonic() - started < 2


def test_worker_failure_keeps_full_log_and_bounded_note():
    from scripts._benchmark_client import Worker

    command = (
        "import sys; sys.stderr.write('START' + 'x'*100000 + 'END'); sys.stderr.flush()"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError, match="without evidence") as caught:
        worker.measure({"timeout": 1}, {}, 2)
    assert worker.process is None
    assert worker.log_path.read_text() == "START" + "x" * 100000 + "END"
    note = caught.value.__notes__[0]
    assert "[log]" in note
    assert note.endswith("END")
    assert len(note) < 34000


def test_interrupted_timing_publication_preserves_completed_pair(tmp_path, monkeypatch):
    from scripts import pytest_durations, refresh_ci_timings

    recorder = Recorder(tmp_path / "timings.json")
    recorder.collected.add("test")
    recorder.finished.add("test")
    recorder.durations["test"] = 1
    recorder.pytest_sessionfinish(0)
    original = pytest_durations.write_text

    def interrupted(path, text):
        if path.name.endswith("meta.json"):
            raise OSError("interrupted")
        original(path, text)

    monkeypatch.setattr(pytest_durations, "write_text", interrupted)
    recorder.durations["test"] = 2
    with pytest.raises(OSError, match="interrupted"):
        recorder.pytest_sessionfinish(0)
    assert refresh_ci_timings.load_run(tmp_path, {"test"}) == {"test": 1}
