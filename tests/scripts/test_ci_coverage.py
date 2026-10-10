"""Coverage shards retain branch evidence and cannot fail open."""

import os
import subprocess
import sys
from pathlib import Path

import coverage
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_combining_shards_retains_every_branch(tmp_path):
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


def test_coverage_gate_requires_success_and_both_artifacts():
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
    assert "coverage report --fail-under=97" in commands
    assert "check_diff_coverage.py --partial --strict" in commands


def test_failure_log_uploads_are_unconditional_and_unique():
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
