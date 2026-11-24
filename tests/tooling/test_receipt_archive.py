"""Retain verification evidence when the producing worktree is removed."""

import json
import os
import subprocess

import pytest

from scripts.verify.receipts import AcceptanceRun, archive, validate
from tests.tooling.receipt_support import _checkout, completed


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def _commit(root, message):
    _git(
        root,
        "-c",
        "user.name=Receipt Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qam",
        message,
    )


def test_archive_retains_logs_and_pytest_sidecar_after_worktree_removal(tmp_path):
    primary = _checkout(tmp_path / "primary")
    source = tmp_path / "worktree"
    _git(primary, "worktree", "add", "--detach", str(source))
    (source / "program.py").write_text("print(2)\n")
    (source / "program-link.py").symlink_to("program.py")
    run = AcceptanceRun(source, [], {"default": 10.0})
    execution = source / "notes" / "execution.json"
    execution.parent.mkdir()
    node = "test_program.py::test_command"
    execution.write_text(
        json.dumps(
            {
                "schema": 1,
                "exitstatus": 0,
                "selection": {"collect_only": False},
                "called": [node],
                "selected": [node],
                "finished": [node],
            }
        )
    )
    run.declare([("pytest", ["pytest", "--verification-output", str(execution)], {})])
    run.record("pytest", 0.1, 0, "test command ran")
    receipt, passed = run.finish(0)
    assert passed
    with pytest.raises(ValueError, match="after committing"):
        archive(receipt, source, primary)

    _git(source, "add", "program-link.py")
    _commit(source, "Integrate verified program")
    commit = _git(source, "rev-parse", "HEAD")
    _git(primary, "merge", "--ff-only", commit)
    saved = archive(receipt, source, primary)
    assert (
        saved
        == primary
        / "notes"
        / "verification"
        / "commits"
        / commit
        / receipt.stem
        / "receipt.json"
    )
    _git(primary, "worktree", "remove", str(source))
    assert not source.exists()
    (primary / "program.py").write_text("print(3)\n")
    _commit(primary, "Change verified program")
    validate(saved, primary, {"pytest"})

    contents = saved.read_text()
    record = json.loads(contents)
    assert record["committed_revision"] == commit
    record["committed_revision"] = _git(primary, "rev-parse", "HEAD")
    saved.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="inputs do not match the recorded commit"):
        validate(saved, primary, {"pytest"})
    saved.write_text(contents)

    legacy = {**json.loads(contents), "schema": 1}
    legacy["inputs"] = {
        name: entry["sha256"] for name, entry in legacy["inputs"].items()
    }
    saved.write_text(json.dumps(legacy))
    validate(saved, primary, {"pytest"})
    saved.write_text(contents)

    row = record["checks"][0]
    log = saved.parent / row["evidence"]["path"]
    assert log.read_text() == "test command ran"
    (saved.parent / row["execution"]["path"]).write_text("{}")
    with pytest.raises(ValueError, match="execution evidence was changed"):
        validate(saved, primary, {"pytest"})


@pytest.mark.skipif(os.name != "posix", reason="POSIX executable bit")
def test_receipt_rejects_mode_only_changes(tmp_path):
    root = _checkout(tmp_path / "checkout")
    program = root / "program.py"
    program.chmod(0o755)
    _git(root, "add", "--chmod=+x", "program.py")
    _commit(root, "Make program executable")
    run, _ = completed(root)
    receipt, passed = run.finish(0)
    assert passed
    validate(receipt, root, {"probe"})
    validate(archive(receipt, root, root), root, {"probe"})

    program.chmod(0o644)
    invalid, passed = run.finish(0)
    assert not passed
    assert json.loads(invalid.read_text())["changed_inputs"] == ["program.py"]
    with pytest.raises(ValueError, match="inputs do not match this checkout"):
        validate(receipt, root, {"probe"})

    _git(root, "add", "--chmod=-x", "program.py")
    _commit(root, "Drop executable bit")
    with pytest.raises(ValueError, match="inputs do not match the recorded commit"):
        archive(receipt, root, root)
