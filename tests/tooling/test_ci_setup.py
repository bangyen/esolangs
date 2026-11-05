"""CI setup honors the requested interpreter and wheel-install isolation."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / ".github/actions/setup/action.yml"


@pytest.mark.parametrize(
    ("version", "sync"),
    [("3.12", True), ("3.13", True), ("3.14", True), ("3.15", True), ("3.15", False)],
)
def test_setup_uses_the_job_interpreter_and_can_skip_dev_dependencies(
    tmp_path, version, *, sync
):
    action = yaml.safe_load(ACTION.read_text())
    assert action["runs"]["using"] == "composite"
    steps = action["runs"]["steps"]
    assert action["inputs"]["python-version"]["required"] is True
    provider = next(
        step for step in steps if "actions/setup-python@" in step.get("uses", "")
    )
    assert provider["if"] == "inputs.python-version != '3.15'"
    assert provider["with"]["python-version"] == "${{ inputs.python-version }}"
    calls = tmp_path / "calls"
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$CALLS"\n')
    uv.chmod(0o755)
    for step in steps:
        if "run" not in step:
            continue
        assert step["shell"] == "bash"
        if step["if"] == "inputs.python-version == '3.15'":
            if version != "3.15":
                continue
        else:
            assert step["if"] == "inputs.sync == 'true'"
            assert step["env"]["PYTHON_VERSION"] == "${{ inputs.python-version }}"
            if not sync:
                continue
        env = {
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
            "CALLS": str(calls),
            "PYTHON_VERSION": version,
        }
        subprocess.run(["bash", "-e", "-c", step["run"]], env=env, check=True)
    expected = ["python", "install", "3.15.0"] if version == "3.15" else []
    if sync:
        expected += ["sync", "--group", "dev", "--python", version]
    assert (calls.read_text().splitlines() if calls.exists() else []) == expected


def test_local_setup_has_a_checkout_and_preserves_wheel_isolation():
    seen = 0
    for filename in ("ci.yml", "weekly.yml", "release.yml"):
        workflow = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
        assert workflow["env"]["UV_NO_SYNC"] == "1"
        for name, job in workflow["jobs"].items():
            for i, step in enumerate(job["steps"]):
                if step.get("uses") != "./.github/actions/setup":
                    continue
                seen += 1
                commands = " ".join(str(s.get("run", "")) for s in job["steps"])
                if any(
                    trigger in commands
                    for trigger in (
                        "scripts/ci/shard.py shard",
                        "checks/check_shard_manifests.py",
                        "scripts/verify/gate.py",
                        "python -m pytest",
                    )
                ):
                    checkout = next(
                        s
                        for s in job["steps"][:i]
                        if s.get("uses", "").startswith("actions/checkout@")
                    )
                    assert checkout["with"]["fetch-depth"] == 0
                assert any(
                    s.get("uses", "").startswith("actions/checkout@")
                    for s in job["steps"][:i]
                )
                assert step["with"].get("sync", "true") == (
                    "false" if name in {"distribution", "check-version"} else "true"
                )
    assert seen > 0
