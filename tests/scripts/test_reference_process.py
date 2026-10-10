"""Reference deadlines and output caps stop descendants while preserving prefixes."""

import sys
import time

import pytest

from scripts import _reference_process as reference


def test_reference_preserves_output_input_and_exit():
    code, output, error, status = reference.run(
        [
            sys.executable,
            "-c",
            "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read());"
            'sys.stderr.write("detail");sys.exit(70)',
        ],
        b"prefix",
        1,
    )
    assert (code, output, error, status) == (70, b"prefix", b"detail", None)


@pytest.mark.medium
@pytest.mark.parametrize("overflow", [False, True])
def test_reference_bounds_stop_descendants_with_positive_control(tmp_path, overflow):
    marker = tmp_path / "tick"
    child = (
        "import time;from pathlib import Path\nwhile True:\n "
        + f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n time.sleep(.01)"
    )
    code = (
        "import subprocess,sys,time,os\nfrom pathlib import Path\n"
        f'subprocess.Popen([sys.executable,"-c",{child!r}], '
        'start_new_session=os.name == "posix")\n'
        f"while not Path({str(marker)!r}).exists(): time.sleep(.01)\n"
        'sys.stdout.write("prefix");sys.stdout.flush()\n'
        + (
            'while True:\n sys.stderr.write("x" * 8192);sys.stderr.flush()\n'
            if overflow
            else "time.sleep(10)"
        )
    )
    _exit, output, error, status = reference.run(
        [sys.executable, "-c", code], b"", 0.3, 4096
    )
    assert status == ("limit" if overflow else "timeout")
    assert output == b"prefix"
    assert len(output) + len(error) <= 4096
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before


@pytest.mark.medium
def test_differential_minimization_has_a_whole_process_deadline():
    import shlex

    import differential

    spec = differential.SPECS["brainfuck"]
    command = shlex.join([sys.executable, "-c", "import time;time.sleep(10)"])
    runner = differential.Runner(spec, command, 1)
    runner.minimize_seconds = 0.3
    case = differential.Case(
        "++++.",
        "abc",
        "fixture",
        differential.Outcome("halt", b"a"),
        differential.Outcome("halt", b"b"),
    )
    started = time.monotonic()
    assert runner.minimize(case) is case
    assert time.monotonic() - started < 2
    assert runner.tally["minimization/timeout"] == 1


@pytest.mark.medium
def test_campaign_deadline_stops_nested_reference_and_retains_partial_manifest(
    tmp_path,
):
    import json
    import shlex
    import subprocess
    from pathlib import Path

    marker = tmp_path / "tick"
    command = (
        "import time;from pathlib import Path\nwhile True:\n "
        f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n time.sleep(.01)"
    )
    template = shlex.join([sys.executable, "-c", command])
    script = Path(__file__).resolve().parents[2] / "scripts/differential.py"
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "brainfuck",
            "--ref",
            template,
            "--programs",
            "1",
            "--minimize-calls",
            "1",
            "--budget-seconds",
            "1",
            "--ref-timeout",
            "10",
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        timeout=4,
    )
    assert result.returncode == 124, result.stdout + result.stderr
    evidence = json.loads(report.read_text())
    assert evidence["status"] == "timeout"
    assert evidence["completed_cases"] < evidence["plan"]["tables"]
    assert marker.exists()
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before
