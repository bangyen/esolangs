"""Candidate grids are priced by rectangular area."""

from unittest.mock import patch

import pytest

from scripts.screens import candidate
from scripts.screens._build import source_size


def test_shorter_text_with_larger_grid_is_reported_as_growth(capsys) -> None:
    old, new = "> @\n> @\n> @", ">      @\n>"
    with (
        patch.object(candidate, "resolve", side_effect=lambda name: name),
        patch.object(
            candidate,
            "_candidate_identity",
            return_value={"spec": "fixture.py:build", "sha256": "fixture"},
        ),
        patch.object(candidate, "source_identity", return_value={}),
        patch.object(candidate, "_tables", return_value=[("random", "00000000")]),
        patch("scripts.screens._build.describe", return_value={"state_model": "grid"}),
    ):
        result = {
            "old_size": source_size("fixture", old),
            "new_size": source_size("fixture", new),
            "old_artifact_sha256": "old",
            "new_artifact_sha256": "new",
            "new_executions": [{"matches": True, "commands": 1}],
            "old_executions": [{"matches": True, "commands": 1}],
        }
        with patch.object(candidate, "_run_case", return_value=result):
            assert candidate.main(["fixture", "fixture.py:build", "--n", "3", "3"]) == 0
    row = capsys.readouterr().out.splitlines()[-1].split()
    assert row[4] == "1"
    assert row[5] == "1.778/1.778"


@pytest.mark.parametrize(
    "options",
    [
        ["--rows", "0"],
        ["--count", "0"],
        ["--rows", "-1"],
        ["--n", "0", "1"],
        ["--n", "2", "1"],
    ],
)
def test_empty_screen_rejected_before_loading(options):
    with (
        patch.object(candidate, "_load", side_effect=AssertionError("loaded")),
        pytest.raises(SystemExit) as caught,
    ):
        candidate.main(["brainfuck", "unused.py:build", *options])
    assert caught.value.code == 2


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_invalid_timeout_rejected_before_loading(timeout):
    with (
        patch.object(candidate, "_load", side_effect=AssertionError("loaded")),
        pytest.raises(SystemExit) as caught,
    ):
        candidate.main(["brainfuck", "unused.py:build", "--timeout", timeout])
    assert caught.value.code == 2


def options(path, failures):
    return [
        "brainfuck",
        f"{path}:build",
        "--n",
        "1",
        "1",
        "--count",
        "1",
        "--rows",
        "2",
        "--step-cap",
        "10000",
        "--timeout",
        "2",
        "--generation-timeout",
        "2",
        "--budget-seconds",
        "5",
        "--failures",
        str(failures),
    ]


def test_dry_run_prices_work_without_importing_candidate(tmp_path, capsys):
    path = tmp_path / "candidate.py"
    marker = tmp_path / "imported"
    path.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    assert candidate.main([*options(path, tmp_path / "failures"), "--dry-run"]) == 0
    assert not marker.exists()
    import json

    plan = json.loads(capsys.readouterr().out)
    assert plan["tables"] == 2
    assert plan["row_executions"] == 8
    assert plan["step_bound"] == 80000


@pytest.mark.parametrize(
    "limit", [["--max-tables", "1"], ["--max-work", "1"], ["--max-table-bits", "1"]]
)
def test_work_limit_rejects_before_import(tmp_path, limit):
    with pytest.raises(SystemExit) as caught:
        candidate.main(
            [*options(tmp_path / "missing.py", tmp_path / "failures"), *limit]
        )
    assert caught.value.code == 2


@pytest.mark.medium
def test_real_candidate_failure_replays_and_accepts_an_explicit_fix(tmp_path):
    import json

    path = tmp_path / "candidate.py"
    path.write_text("def build(table):\n    return '+' * 48 + '.'\n")
    failures = tmp_path / "failures"
    assert candidate.main(options(path, failures)) == 1
    saved = next(failures.glob("*.json"))
    record = json.loads(saved.read_text())
    assert all(row["matches"] for row in record["result"]["old_executions"])
    assert any(not row["matches"] for row in record["result"]["new_executions"])
    replayed = tmp_path / "replayed"
    assert candidate.main([*options(path, replayed), "--replay", str(saved)]) == 1
    replay = json.loads(next(replayed.glob("*.json")).read_text())
    assert replay["result"] == record["result"]
    path.write_text("from esolangs.tools.brainfuck import brainfuck as build\n")
    with pytest.raises(SystemExit) as caught:
        candidate.main([*options(path, replayed), "--replay", str(saved)])
    assert caught.value.code == 2
    assert (
        candidate.main(
            [
                *options(path, tmp_path / "fixed"),
                "--replay",
                str(saved),
                "--allow-changed-candidate",
            ]
        )
        == 0
    )


@pytest.mark.medium
def test_hung_generation_saves_failure_and_stops_descendants(tmp_path):
    import json
    import time

    path = tmp_path / "candidate.py"
    marker = tmp_path / "tick"
    worker = (
        "import time; from pathlib import Path\nwhile True:\n "
        f"Path({str(marker)!r}).write_text(str(time.monotonic()))\n "
        "time.sleep(.01)\n"
    )
    path.write_text(
        "import subprocess,sys,time\ndef build(table):\n "
        f"subprocess.Popen([sys.executable,'-c',{worker!r}])\n "
        "time.sleep(10)\n return ''\n"
    )
    failures = tmp_path / "failures"
    started = time.monotonic()
    assert candidate.main([*options(path, failures), "--generation-timeout", ".3"]) == 1
    assert time.monotonic() - started < 3
    record = json.loads(next(failures.glob("*.json")).read_text())
    assert record["error"]["type"] == "ExecutionTimeoutError"
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before
