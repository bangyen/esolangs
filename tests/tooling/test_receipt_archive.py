"""Retain verification evidence when the producing worktree is removed."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify.receipts import AcceptanceRun, archive, digest, validate
from tests.tooling.receipt_support import _checkout, completed
from tests.tooling.script_support import REPO_ROOT, load


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def test_evidence_digest_reads_the_complete_file_without_a_snapshot(
    tmp_path, monkeypatch
):
    path = tmp_path / "evidence"
    payload = bytes(range(256)) * 2048 + b"tail"
    path.write_bytes(payload)

    def read_bytes(_path):
        pytest.fail("digest tried to load the whole file")

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert digest(path) == hashlib.sha256(payload).hexdigest()
    with pytest.raises(FileNotFoundError):
        digest(tmp_path / "missing")


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


def test_malformed_receipts_name_the_file_and_field(tmp_path) -> None:
    root = _checkout(tmp_path / "checkout")
    run, _ = completed(root)
    receipt, passed = run.finish(0)
    assert passed
    valid = json.loads(receipt.read_text(encoding="utf-8"))
    broken = {"checks": [{**valid["checks"][0], "evidence": []}]}
    for fields, expected in (
        ({}, "missing receipt field 'schema'"),
        ({**valid, "scope": []}, "invalid receipt field 'scope'"),
        ({**valid, **broken}, "invalid receipt field 'checks[0].evidence'"),
    ):
        receipt.write_text(json.dumps(fields), encoding="utf-8")
        for action in (
            lambda: validate(receipt, root, set()),
            lambda: archive(receipt, root, root),
        ):
            with pytest.raises(ValueError, match="receipt field") as error:
                action()
            assert str(receipt) in str(error.value)
            assert expected in str(error.value)
    assert not (root / "notes/verification/commits").exists()

    receipt.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPO_ROOT / "scripts/verify/receipts.py"),
            "--archive",
            str(receipt),
            str(root),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr.strip() == f"{receipt}: missing receipt field 'schema'"


def test_repeated_receipt_fields_cannot_replace_the_schema(tmp_path) -> None:
    root = _checkout(tmp_path / "checkout")
    run, _ = completed(root)
    receipt, passed = run.finish(0)
    assert passed
    original = receipt.read_text(encoding="utf-8")
    receipt.write_text('{"schema":999,' + original[1:], encoding="utf-8")
    for action in (
        lambda: validate(receipt, root, {"probe"}),
        lambda: archive(receipt, root, root),
    ):
        with pytest.raises(ValueError, match="duplicate field: schema") as error:
            action()
        assert str(receipt) in str(error.value)


def test_receipts_require_each_checks_log_and_checksum(tmp_path) -> None:
    root = _checkout(tmp_path / "checkout")
    run, log = completed(root)
    receipt, passed = run.finish(0)
    assert passed
    record = json.loads(receipt.read_text(encoding="utf-8"))
    path = record["checks"][0]["evidence"]["path"]
    log.unlink()
    for evidence, field in (({}, "path"), ({"path": path}, "sha256")):
        record["checks"][0]["evidence"] = evidence
        receipt.write_text(json.dumps(record), encoding="utf-8")
        for action in (
            lambda: validate(receipt, root, {"probe"}),
            lambda: archive(receipt, root, root),
        ):
            with pytest.raises(ValueError, match="missing receipt field") as error:
                action()
            assert str(receipt) in str(error.value)
            assert f"'checks[0].evidence.{field}'" in str(error.value)
    assert not (root / "notes/verification/commits").exists()


def test_receipt_steps_bind_their_own_output(tmp_path, monkeypatch) -> None:
    root = _checkout(tmp_path / "checkout")
    run = AcceptanceRun(root, [], {"default": 10.0})
    gate = load(REPO_ROOT / "scripts/verify/gate.py")
    monkeypatch.setattr(gate, "ROOT", root)
    monkeypatch.setattr(gate, "_ACTIVE_ACCEPTANCE", run)
    decoy = root / "notes/other-test.log"
    decoy.parent.mkdir()
    decoy.write_text("unrelated output\n", encoding="utf-8")
    output = "[log] notes/other-test.log\n1 passed\n"
    command = [sys.executable, "-c", f"print({output!r}, end='')"]
    failures, _, _ = gate._run_steps(
        [("probe", command, dict(os.environ))], stream=False
    )
    assert failures == []
    monkeypatch.setattr(
        gate,
        "run_bounded",
        lambda command, **_: subprocess.CompletedProcess(command, 0, output, ""),
    )
    assert gate._rerun_alone(["test_probe.py::test_probe"]) == (0, output)

    spooled, retry = (root / step["evidence"]["path"] for step in run.steps)
    assert spooled.parent == root / "notes/verification"
    assert retry.parent == root / "notes/verification/receipts/logs"
    assert (
        spooled.read_text(encoding="utf-8")
        == retry.read_text(encoding="utf-8")
        == output
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
    archived = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPO_ROOT / "scripts/verify/receipts.py"),
            "--archive",
            str(receipt),
            str(primary),
        ],
        cwd=source,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    saved = Path(archived.stdout.strip())
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
