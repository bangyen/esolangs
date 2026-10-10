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
    # 5s, not 2s: supervise spawns a subprocess and reaps its tree, which on a
    # loaded Windows runner measured just over 2s.  The script under test
    # sleeps 10s, so this still proves the budget stopped it promptly.
    assert time.monotonic() - started < 5
    assert marker.exists()
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before


@pytest.mark.medium
@pytest.mark.parametrize("screen", ["steps", "resources"])
def test_small_real_screen_runs_under_its_plan(screen, tmp_path):
    import subprocess

    arguments = (
        ["brainfuck", "--cap", "1"]
        if screen == "steps"
        else [payload_language(), "--max-inputs", "1"]
    )
    script = Path(__file__).resolve().parents[2] / "scripts/screens" / f"{screen}.py"
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            *arguments,
            "--budget-seconds",
            "5",
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout.splitlines()[0])
    assert plan["step_bound"] < 100000
    assert plan["wall_budget_seconds"] == 5
    record = json.loads(report.read_text())
    assert record["status"] == "complete"
    assert record["completed_cases"] == plan["tables"]
    assert 0 < record["row_executions"] <= plan["row_executions"]
    resumed = subprocess.run(
        [
            sys.executable,
            str(script),
            *arguments,
            "--budget-seconds",
            "5",
            "--report",
            str(report),
            "--resume",
            str(report),
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    replay = json.loads(report.read_text())
    assert replay["status"] == "complete"
    assert all(
        bool(case.get("reused"))
        == (case["status"] in {"executed", "stepped", "refused"})
        for case in replay["cases"]
    )


def payload_language():
    return next(name for name, language in LANGUAGES.items() if language.payload)


@pytest.mark.parametrize(
    "name", ["transforms", "sharing", "ignored_input", "dead_code"]
)
def test_remaining_screen_previews_do_not_generate(name, monkeypatch, capsys):
    import importlib

    screen = importlib.import_module("scripts.screens." + name)
    monkeypatch.setattr(sys, "argv", [name, "brainfuck", "--dry-run"])
    screen.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["tables"] > 0
    assert plan["work_bound"] > 0


@pytest.mark.medium
@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("transforms", []),
        ("sharing", ["--sample", "1"]),
        ("ignored_input", []),
        ("dead_code", ["--limit", "1"]),
    ],
)
def test_remaining_small_screens_have_complete_manifests(tmp_path, name, extra):
    import subprocess

    script = Path(__file__).resolve().parents[2] / "scripts/screens" / (name + ".py")
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "brainfuck",
            *extra,
            "--budget-seconds",
            "5",
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(report.read_text())
    assert record["status"] == "complete"
    assert (
        record["completed_cases"] + record["skipped_cases"] == record["plan"]["tables"]
    )
    assert record["checkout"]["commit"]
    identifiers = [case["case_id"] for case in record["cases"]]
    assert len(set(identifiers)) == len(identifiers)
    assert set(identifiers) == set(record["plan"]["case_ids"])
    resumed = subprocess.run(
        [
            sys.executable,
            str(script),
            "brainfuck",
            *extra,
            "--budget-seconds",
            "5",
            "--report",
            str(report),
            "--resume",
            str(report),
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    replay = json.loads(report.read_text())
    for old, new in zip(record["cases"], replay["cases"], strict=True):
        assert new["case_id"] == old["case_id"]
        assert bool(new.get("reused")) == (
            old["status"] in {"measured", "executed", "refused"}
        )
    assert replay["row_executions"] == 0


@pytest.mark.medium
def test_successful_exit_without_case_ledger_is_incomplete(tmp_path, monkeypatch):
    script = tmp_path / "scripts/screens/partial.py"
    script.parent.mkdir(parents=True)
    script.write_text('print("partial output")\n')
    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", [str(script)])
    args = argparse.Namespace(
        budget_seconds=1, max_work=10, worker=False, dry_run=False, report=report
    )
    with pytest.raises(SystemExit) as caught:
        _budget.supervise(
            argparse.ArgumentParser(), args, script, {"tables": 1, "step_bound": 1}
        )
    assert caught.value.code == 1
    record = json.loads(report.read_text())
    assert record["status"] == "incomplete"
    assert record["completed_cases"] == 0
