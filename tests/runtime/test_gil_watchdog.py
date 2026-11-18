"""A test stuck inside one GIL-holding operation is still stopped and named."""

import os
import subprocess
import sys

import pytest

from tests.tooling.script_support import REPO_ROOT

_STUCK = """
import pytest

@pytest.mark.timeout(1)
def test_stuck():
    # One bigint power holds the GIL for minutes; the thread timeout cannot act.
    assert pow(3, 3 * 10**8)

def test_free():
    pass
"""


@pytest.mark.medium
def test_a_gil_held_hang_crashes_its_worker_by_name(tmp_path) -> None:
    (tmp_path / "test_stuck.py").write_text(_STUCK)
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.support.gil_watchdog",
            "-o",
            "gil_watchdog_grace=1",
            "--timeout-method=thread",
            "-n",
            "2",
            "--dist",
            "worksteal",
            str(tmp_path / "test_stuck.py"),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        check=False,
        capture_output=True,
        text=True,
        # Without the watchdog the session outlives this cap.
        timeout=50,
    )
    assert "crashed while running 'test_stuck.py::test_stuck'" in done.stdout
    assert "1 failed, 1 passed" in done.stdout
    assert "in test_stuck" in done.stdout + done.stderr
