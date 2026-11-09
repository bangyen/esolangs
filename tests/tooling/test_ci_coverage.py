"""Coverage shards retain branch evidence and cannot fail open."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import coverage
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_combining_shards_retains_every_branch(tmp_path) -> None:
    source = tmp_path / "branch.py"
    source.write_text(
        "def pick(value):\n    if value:\n        return 1\n    return 0\n"
    )
    paths = [tmp_path / f".coverage.shard-{i}" for i in range(2)]
    expected = set()
    for index, path in enumerate(paths):
        driver = tmp_path / f"driver-{index}.py"
        driver.write_text(f"from branch import pick\npick({bool(index)!r})\n")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--data-file",
                str(path),
                str(driver),
            ],
            check=True,
            cwd=tmp_path,
            capture_output=True,
        )
        data = coverage.CoverageData(basename=str(path))
        data.read()
        expected.update(data.arcs(str(source)))
    subprocess.run(
        [sys.executable, "-m", "coverage", "combine", *map(str, paths)],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        env={**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")},
    )
    combined = coverage.CoverageData(basename=str(tmp_path / ".coverage"))
    combined.read()
    assert set(combined.arcs(str(source))) == expected
    assert (2, 3) in expected
    assert (2, 4) in expected


def test_coverage_gate_requires_success_and_both_artifacts(tmp_path) -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    shard = jobs["coverage-tests"]
    assert shard["strategy"]["matrix"]["shard"] == [0, 1]
    assert "--cov-branch" in next(
        step["run"]
        for step in shard["steps"]
        if step.get("name") == "Test one coverage shard"
    )
    gate = jobs["coverage"]
    assert gate["needs"] == "coverage-tests"
    assert gate["if"] == "always()"
    assert gate["steps"][0]["run"] == 'test "$SHARD_RESULT" = success'
    commands = "\n".join(step.get("run", "") for step in gate["steps"])
    assert "test -f .coverage.shard-0" in commands
    assert "test -f .coverage.shard-1" in commands
    assert "coverage report --fail-under=98" in commands

    jobs = yaml.safe_load((ROOT / ".github/workflows/weekly.yml").read_text())["jobs"]
    versions = jobs["slow"]["strategy"]["matrix"]["python-version"]
    assert sorted([*versions, "3.14"]) == ["3.12", "3.13", "3.14", "3.15"]
    full = jobs["slow"]
    assert full["timeout-minutes"] == 45
    assert full["strategy"]["matrix"]["shard"] == [0, 1]
    full_command = next(
        step["run"]
        for step in full["steps"]
        if step.get("name") == "Test one full-suite shard"
    )
    assert '--marker ""' in full_command
    assert "--exclude-node" not in full_command
    assert "--shards 2" in full_command
    assert "--manifest notes/ci/weekly.shard.json" in full_command
    assert "-p scripts.ci.shard --duration-output" in full_command
    census = jobs["shard-completeness"]
    assert census["needs"] == "slow"
    assert census["if"] == "always()"
    assert census["steps"][0]["run"] == 'test "$RESULT" = success'
    assert census["strategy"]["matrix"]["python-version"] == versions
    assert census["steps"][-1]["run"].endswith('--marker "" --shards 2')
    upload = next(
        step["with"]
        for step in full["steps"]
        if "actions/upload-artifact@" in step.get("uses", "")
        and "weekly.shard.json" in step["with"]["path"]
    )
    download = next(
        step["with"]
        for step in census["steps"]
        if "actions/download-artifact@" in step.get("uses", "")
    )
    assert (
        upload["name"]
        == "test-durations-${{ matrix.python-version }}-${{ matrix.shard }}"
    )
    assert download["pattern"] == "test-durations-${{ matrix.python-version }}-*"
    assert upload["if-no-files-found"] == "error"
    scan = jobs["deadcode-scan"]
    assert scan["strategy"]["matrix"]["shard"] == [0, 1, 2, 3]
    command = next(
        step["run"]
        for step in scan["steps"]
        if step.get("name") == "Scan one deadcode shard"
    )
    assert '--marker ""' in command
    assert "--exclude-node" not in command
    assert "--cov-branch" in command
    assert "--duration-output notes/ci/test-durations.json" in command
    arguments = shlex.split(command.split(" -- ", 1)[1])
    timings = tmp_path / "durations.json"
    arguments[arguments.index("--duration-output") + 1] = str(timings)
    arguments[arguments.index("-n") + 1] = "0"
    probe = tmp_path / "test_probe.py"
    probe.write_text("def test_probe():\n    assert True\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *arguments,
            "--collect-only",
            "-o",
            "addopts=",
            str(probe),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")},
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(timings.with_suffix(".json.meta.json").read_text())
    assert receipt["exitstatus"] == 0
    assert len(receipt["collected"]) == 1
    gate = jobs["deadcode"]
    assert gate["needs"] == "deadcode-scan"
    assert gate["steps"][0]["run"] == 'test "$SHARD_RESULT" = success'
    commands = "\n".join(step.get("run", "") for step in gate["steps"])
    for shard in scan["strategy"]["matrix"]["shard"]:
        assert f"test -f .coverage.deadcode-{shard}" in commands


def test_failure_log_uploads_are_unconditional_and_unique() -> None:
    for name in ("ci.yml", "weekly.yml", "release.yml"):
        jobs = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())["jobs"]
        for job in jobs.values():
            uploads = [
                step
                for step in job["steps"]
                if "actions/upload-artifact@" in step.get("uses", "")
            ]
            names = [step["with"]["name"] for step in uploads]
            assert len(names) == len(set(names))
            for upload in uploads:
                if "notes/benchmarks" in upload["with"]["path"]:
                    assert upload["if"] == "always()"
                    assert "notes/verification" in upload["with"]["path"]
