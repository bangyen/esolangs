"""Diagnostic byte budgets preserve bounded evidence and reap noisy workers."""

import io
import os
import sys
import time

import pytest

from scripts import _benchmark_client as client
from scripts import _verify_process as processes
from scripts._bounded_log import MARKER, spool


def test_spool_keeps_complete_small_logs_and_bounded_overflow(tmp_path):
    path = tmp_path / "log"
    stops = []
    spool(io.BytesIO(b"complete"), path, 100, lambda: stops.append(True))
    assert path.read_bytes() == b"complete"
    assert not stops
    spool(io.BytesIO(b"x" * 10000), path, 100, lambda: stops.append(True))
    assert path.stat().st_size <= 100
    assert path.read_bytes().endswith(MARKER)
    assert stops == [True]


@pytest.mark.medium
@pytest.mark.parametrize("benchmark", [False, True])
def test_noisy_worker_stops_with_bounded_log_and_descendants(
    tmp_path, monkeypatch, benchmark
):
    marker = tmp_path / "tick"
    child = (
        "import time;from pathlib import Path\nwhile True:\n "
        + f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n time.sleep(.01)"
    )
    command = (
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        f'subprocess.Popen([sys.executable,"-c",{child!r}])\n'
        f"while not Path({str(marker)!r}).exists(): time.sleep(.01)\n"
        'print(\'{"phase":"generation"}\',flush=True)\n'
        'while True:\n sys.stderr.write("x" * 8192);sys.stderr.flush()\n'
    )
    if benchmark:
        monkeypatch.setattr(client, "MAX_LOG_BYTES", 4096)
        worker = client.Worker([sys.executable, "-c", command])
        with pytest.raises(RuntimeError, match="diagnostic byte limit"):
            worker.measure({"timeout": 1}, {}, 1)
        assert worker.process is None
        path = worker.log_path
    else:
        monkeypatch.setattr(processes, "MAX_LOG_BYTES", 4096)
        process = processes.start_logged(
            [sys.executable, "-c", command],
            "noisy",
            dict(os.environ),
            tmp_path,
            stream=False,
        )
        output, code = processes.wait_with_heartbeat(
            process, "noisy", time.monotonic(), 2, 0.1
        )
        assert code == 125
        assert "diagnostic byte limit" in output
        path = next((tmp_path / "notes/verification").glob("*.log"))
    assert path.stat().st_size <= 4096
    assert path.read_bytes().endswith(MARKER)
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before
