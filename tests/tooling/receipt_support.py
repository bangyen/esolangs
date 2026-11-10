"""Acceptance evidence must reject stale inputs, changed logs and empty scopes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify.receipts import AcceptanceRun, validate


def _checkout(tmp_path):
    tmp_path.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            timeout=10,
        )

    git("init", "-q")
    (tmp_path / ".gitignore").write_text("notes/\n")
    (tmp_path / "program.py").write_text("print(1)\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Receipt Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qm",
        "Create test input",
    )
    return tmp_path


def completed(root: Path, *, returncode=0):
    run = AcceptanceRun(root, ["--only", "probe"], {"default": 10.0})
    run.declare([("probe", ["python", "program.py"], {})])
    log = root / "notes" / "probe.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text("positive control executed\n")
    run.record("probe", 0.01, returncode, f"[log] {log}\n")
    return run, log


def check_matching_receipt_retains_exact_scope_and_bounds(checkout):
    run, _ = completed(checkout)
    run.capture_environment([sys.executable], dict(os.environ))
    assert run.environment["python_version"] == list(sys.version_info)
    assert run.environment_command[-1] == "--environment"
    path, passed = run.finish(0)
    assert passed
    validate(path, checkout, {"probe"})
    value = json.loads(path.read_text())
    assert value["scope"] == {"probe": ["python", "program.py"]}
    assert value["checks"][0]["deadline_seconds"] == 10
    assert value["environment"]["python"]
    assert value["revision"]
    with pytest.raises(ValueError, match="required scope"):
        validate(path, checkout, {"another probe"})


def check_source_changes_during_run_prevent_acceptance(checkout):
    run, _ = completed(checkout)
    (checkout / "program.py").write_text("print(2)\n")
    path, passed = run.finish(0)
    assert not passed
    assert json.loads(path.read_text())["changed_inputs"] == ["program.py"]
    with pytest.raises(ValueError, match="acceptance"):
        validate(path, checkout, {"probe"})


def check_receipt_cannot_be_reused_after_source_or_log_changes(checkout):
    run, log = completed(checkout)
    path, _ = run.finish(0)
    log.write_text("a different check\n")
    with pytest.raises(ValueError, match="log was changed"):
        validate(path, checkout, {"probe"})
    log.write_text("positive control executed\n")
    (checkout / "new.py").write_text("a new production input\n")
    with pytest.raises(ValueError, match="inputs do not match"):
        validate(path, checkout, {"probe"})


def check_zero_exit_cannot_hide_missing_or_failed_checks(checkout, mode):
    run = AcceptanceRun(checkout, [], {"default": 10.0})
    if mode != "no plan":
        run.declare([("probe", ["python", "program.py"], {})])
    if mode == "failed":
        run.record("probe", 0.1, 1, "failed positive control")
    path, passed = run.finish(0)
    assert not passed
    with pytest.raises(ValueError, match="acceptance"):
        validate(path, checkout, {"probe"})


def check_forged_pass_cannot_hide_a_failed_or_missing_check(checkout):
    run, _ = completed(checkout, returncode=1)
    path, _ = run.finish(0)
    value = json.loads(path.read_text())
    value["status"] = "passed"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="acceptance"):
        validate(path, checkout, {"probe"})


def check_retry_acceptance_requires_its_actual_successful_record(checkout):
    run, _ = completed(checkout, returncode=1)
    run.accepted_retries.add("probe")
    _, passed = run.finish(0)
    assert not passed
    run.record("probe retry", 0.01, 0, "passed", command=["python", "program.py"])
    path, passed = run.finish(0)
    assert passed
    validate(path, checkout, {"probe"})


def check_receipt_controls(tmp_path):
    """Exercise receipt reuse and rejection alongside the gate's log controls."""
    checks = [
        check_matching_receipt_retains_exact_scope_and_bounds,
        check_source_changes_during_run_prevent_acceptance,
        check_receipt_cannot_be_reused_after_source_or_log_changes,
        check_forged_pass_cannot_hide_a_failed_or_missing_check,
        check_retry_acceptance_requires_its_actual_successful_record,
    ]
    for index, check in enumerate(checks):
        check(_checkout(tmp_path / str(index)))
    for mode in ("no plan", "not run", "failed"):
        check_zero_exit_cannot_hide_missing_or_failed_checks(
            _checkout(tmp_path / mode), mode
        )
