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


def test_imported_helper_and_package_dependencies_are_fingerprinted(tmp_path):
    from scripts.screens._candidate_evidence import identity

    path = tmp_path / "candidate.py"
    path.write_text("from helper import build\n")
    helper = tmp_path / "helper.py"
    helper.write_text("from package import build\n")
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("from .leaf import build\n")
    leaf = package / "leaf.py"
    leaf.write_text("def build(table): return '.'\n")
    first = identity(f"{path}:build")
    leaf.write_text("def build(table): return '+'\n")
    second = identity(f"{path}:build")
    assert first["sha256"] == second["sha256"]
    assert first["dependencies"] != second["dependencies"]
    assert str(leaf) in first["dependencies"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rows", [{}]),
        ("rows", [True]),
        ("family", None),
        ("seed", False),
        ("checkout", []),
        ("candidate", {}),
        ("bounds", {"step_cap": True}),
        ("language", None),
    ],
)
def test_malformed_replay_rejected_before_execution(tmp_path, field, value):
    import json

    path = tmp_path / "case.json"
    record = {
        "schema": 1,
        "language": "brainfuck",
        "family": "random",
        "seed": 0,
        "checkout": {
            "commit": "fixture",
            "checkout": str(tmp_path),
            "dirty": False,
            "tracked_diff_sha256": "a" * 64,
            "untracked_sha256": "b" * 64,
        },
        "target": None,
        "table": "01",
        "rows": [0, 1],
        "candidate": {
            "spec": "fixture.py:build",
            "sha256": "a" * 64,
            "dependencies": {"fixture.py": "a" * 64},
        },
        "bounds": {"step_cap": 10, "timeout": 1, "generation_timeout": 1},
    }
    record[field] = value
    path.write_text(json.dumps(record))
    with (
        patch.object(candidate, "_run_case", side_effect=AssertionError("executed")),
        pytest.raises(SystemExit) as caught,
    ):
        candidate.main(["brainfuck", "fixture.py:build", "--replay", str(path)])
    assert caught.value.code == 2


def test_oversized_replay_read_is_bounded(tmp_path, monkeypatch):
    from scripts.screens import _candidate_evidence as evidence

    path = tmp_path / "case.json"
    path.write_bytes(b" " * 101)
    monkeypatch.setattr(evidence, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="exceeds"):
        evidence.read_json(path)


@pytest.mark.medium
@pytest.mark.parametrize("dynamic", [False, True])
def test_dependency_drift_checkout_drift_and_success_report(tmp_path, dynamic):
    import json

    path = tmp_path / "candidate.py"
    helper = tmp_path / "helper.py"
    path.write_text(
        "import importlib\nbuild = importlib.import_module('helper').build\n"
        if dynamic
        else "from helper import build\n"
    )
    helper.write_text("def build(table): return '+' * 48 + '.'\n")
    failures = tmp_path / "failures"
    assert candidate.main(options(path, failures)) == 1
    saved = next(failures.glob("*.json"))
    helper.write_text("from esolangs.tools.brainfuck import brainfuck as build\n")
    with pytest.raises(SystemExit):
        candidate.main([*options(path, failures), "--replay", str(saved)])
    report = tmp_path / "report.json"
    record = json.loads(saved.read_text())
    record["checkout"]["commit"] = "different"
    saved.write_text(json.dumps(record))
    replay_options = [
        *options(path, failures),
        "--replay",
        str(saved),
        "--allow-changed-candidate",
        "--report",
        str(report),
    ]
    with pytest.raises(SystemExit):
        candidate.main(replay_options)
    assert candidate.main([*replay_options, "--allow-changed-checkout"]) == 0
    result = json.loads(report.read_text())
    assert result["status"] == "complete"
    assert result["completed_cases"] == 1
    case = result["cases"][0]
    assert case["candidate"]["dependencies"]
    assert case["result"]["size_unit"] == "characters"
    assert all(row["matches"] for row in case["result"]["new_executions"])
    assert 0 < result["elapsed_seconds"] < result["wall_budget_seconds"]


@pytest.mark.medium
@pytest.mark.parametrize("change", ["candidate", "dependency", "checkout"])
def test_source_drift_during_screen_invalidates_success(tmp_path, monkeypatch, change):
    import json

    path = tmp_path / "candidate.py"
    helper = tmp_path / "helper.py"
    path.write_text("from esolangs.tools.brainfuck import brainfuck as build\n")
    helper.write_text("value = 1\n")
    original = candidate._run_case  # noqa: SLF001
    checkout = candidate.source_identity()

    def run(*args):
        result = original(*args)
        if change == "candidate":
            path.write_text(path.read_text() + "# changed\n")
        elif change == "dependency":
            import hashlib

            result["runtime_dependencies"][str(helper)] = hashlib.sha256(
                helper.read_bytes()
            ).hexdigest()
            helper.write_text("value = 2\n")
        else:
            monkeypatch.setattr(
                candidate, "source_identity", lambda: {**checkout, "commit": "changed"}
            )
        return result

    monkeypatch.setattr(candidate, "_run_case", run)
    report = tmp_path / "report.json"
    assert (
        candidate.main([*options(path, tmp_path / "failures"), "--report", str(report)])
        == 1
    )
    assert json.loads(report.read_text())["status"] == "source-changed"


def test_raster_measurements_keep_pixel_area_dimensions_and_scale():
    from esolangs.raster import Raster
    from scripts.screens._build import source_measurement

    image = Raster((((0, 0, 0), (255, 255, 255)),), scale=1)
    original = source_measurement("fixture", image)
    scaled = source_measurement("fixture", image.upscaled(3))
    assert original == {
        "size": 2,
        "unit": "pixels",
        "width": 2,
        "height": 1,
        "scale": 1,
    }
    assert scaled == {"size": 18, "unit": "pixels", "width": 6, "height": 3, "scale": 3}


@pytest.mark.medium
def test_dynamic_helper_edit_during_generation_invalidates_evidence(tmp_path):
    import json

    path = tmp_path / "candidate.py"
    path.write_text(
        "import importlib\nbuild = importlib.import_module('helper').build\n"
    )
    helper = tmp_path / "helper.py"
    helper.write_text(
        "from pathlib import Path\n"
        "from esolangs.tools.brainfuck import brainfuck\n"
        "def build(table):\n path = Path(__file__)\n"
        ' path.write_text(path.read_text() + "# changed\\n")\n'
        " return brainfuck(table)\n"
    )
    report = tmp_path / "report.json"
    assert (
        candidate.main([*options(path, tmp_path / "failures"), "--report", str(report)])
        == 1
    )
    evidence = json.loads(report.read_text())
    assert evidence["status"] == "source-changed"
    assert any(
        "dependencies changed" in case.get("error", {}).get("message", "")
        for case in evidence["cases"]
    )
