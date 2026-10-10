"""Preflight cleanup, timing cohorts, and reproducible archive evidence."""

import os
import subprocess
import sys
import time

import pytest

from scripts import _verify_process


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
