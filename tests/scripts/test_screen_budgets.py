"""Screen previews price work; whole-process budgets stop generation and children."""

import argparse
import json
import sys
import time
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from scripts.screens import _budget, resources, steps


@pytest.mark.parametrize("screen", [steps, resources])
def test_dry_run_prices_without_generation(screen, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["screen", "brainfuck" if screen is steps else payload_language(), "--dry-run"],
    )
    if screen is steps:
        monkeypatch.setattr(steps, "screen", lambda *_args: pytest.fail("generated"))
    else:
        monkeypatch.setattr(resources, "audit", lambda *_args: pytest.fail("generated"))
    screen.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["languages"] == 1
    assert plan["tables"] > 0
    assert plan["row_executions"] > plan["tables"]
    assert plan["step_bound"] > plan["row_executions"]


@pytest.mark.parametrize("screen", [steps, resources])
def test_work_cap_rejects_before_generation(screen, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "screen",
            "brainfuck" if screen is steps else payload_language(),
            "--dry-run",
            "--max-work",
            "1",
        ],
    )
    with pytest.raises(SystemExit) as caught:
        screen.main()
    assert caught.value.code == 2


@pytest.mark.medium
def test_screen_wall_budget_stops_generation_and_descendants(tmp_path, monkeypatch):
    marker = tmp_path / "tick"
    child = (
        "import time;from pathlib import Path\nwhile True:\n "
        + f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n time.sleep(.01)"
    )
    script = tmp_path / "scripts/screens/hung.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import subprocess,sys,time\n"
        + f'subprocess.Popen([sys.executable,"-c",{child!r}])\ntime.sleep(10)\n'
    )
    monkeypatch.setattr(sys, "argv", [str(script)])
    args = argparse.Namespace(
        budget_seconds=0.3, max_work=10, worker=False, dry_run=False
    )
    started = time.monotonic()
    with pytest.raises(SystemExit) as caught:
        _budget.supervise(argparse.ArgumentParser(), args, script, {"step_bound": 1})
    assert caught.value.code == 124
    assert time.monotonic() - started < 2
    assert marker.exists()
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before


@pytest.mark.medium
@pytest.mark.parametrize("screen", ["steps", "resources"])
def test_small_real_screen_runs_under_its_plan(screen):
    import subprocess

    arguments = (
        ["brainfuck", "--cap", "1"]
        if screen == "steps"
        else [payload_language(), "--max-inputs", "1"]
    )
    script = Path(__file__).resolve().parents[2] / "scripts/screens" / f"{screen}.py"
    result = subprocess.run(
        [sys.executable, str(script), *arguments, "--budget-seconds", "5"],
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout.splitlines()[0])
    assert plan["step_bound"] < 100000
    assert plan["wall_budget_seconds"] == 5


def payload_language():
    return next(name for name, language in LANGUAGES.items() if language.payload)
