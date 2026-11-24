"""Content-bound acceptance evidence for a concrete verification run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple, TypedDict


class _Input(TypedDict):
    mode: str
    sha256: str


class _PytestExecution(NamedTuple):
    record: dict[str, Any]
    failed: set[str]
    passed: set[str]


def digest(path: Path) -> str:
    """Hash the complete artifact in bounded memory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _git(root: Path, *args: str) -> str:
    return os.fsdecode(_git_bytes(root, *args))


def _git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def file_fingerprint(path: Path, index_mode: str | None = None) -> _Input | None:
    """Hash a file or link with its Git mode, or return None for absent files."""
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    if stat.S_ISLNK(mode):
        target = os.fsencode(os.readlink(path))
        return {"mode": "120000", "sha256": hashlib.sha256(target).hexdigest()}
    if not stat.S_ISREG(mode):
        return None
    executable = (
        bool(mode & stat.S_IXUSR) if os.name == "posix" else index_mode == "100755"
    )
    return {"mode": "100755" if executable else "100644", "sha256": digest(path)}


def inputs(
    root: Path, *, exclude: frozenset[str] = frozenset()
) -> dict[str, _Input | None]:
    """Fingerprint Git modes and bytes in the checkout, including deletions."""
    names = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    # Git on Windows stores executable bits in the index, not on disk.
    modes: dict[str, str] = {}
    if os.name != "posix":
        for entry in _git(root, "ls-files", "--stage", "-z").split("\0"):
            if entry:
                header, name = entry.split("\t", 1)
                mode, _, stage = header.split()
                if stage == "0":
                    modes[name] = mode
    return {
        name: file_fingerprint(root / name, modes.get(name))
        for name in sorted(set(names.split("\0")) - {""} - exclude)
    }


def _commit_inputs(root: Path, commit: str) -> dict[str, _Input]:
    """Read Git modes and hash raw blobs at a full commit ID."""
    literal = ("--no-replace-objects",)
    try:
        resolved = _git(
            root,
            *literal,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{commit}^{{commit}}",
        ).strip()
    except subprocess.CalledProcessError as error:
        raise ValueError("archived receipt commit is unavailable") from error
    if resolved != commit:
        raise ValueError("archived receipt requires a full commit ID")
    entries: dict[str, tuple[str, bytes]] = {}
    tree = _git_bytes(root, *literal, "ls-tree", "--full-tree", "-r", "-z", commit)
    for entry in tree.split(b"\0"):
        if entry:
            header, name = entry.split(b"\t", 1)
            mode, kind, oid = header.split()
            if kind == b"blob":
                entries[os.fsdecode(name)] = (mode.decode("ascii"), oid)

    hashes = {}
    oids = dict.fromkeys(oid for _, oid in entries.values())
    # Spool the batch so large trees need only one blob in memory at a time.
    with tempfile.TemporaryFile() as blobs:
        subprocess.run(
            ["git", "-C", str(root), *literal, "cat-file", "--batch"],
            input=b"".join(oid + b"\n" for oid in oids),
            stdout=blobs,
            check=True,
            timeout=10,
        )
        blobs.seek(0)
        for oid in oids:
            blob_header = blobs.readline().split()
            if len(blob_header) != 3 or blob_header[:2] != [oid, b"blob"]:
                raise ValueError("archived receipt blob is unavailable")
            size = int(blob_header[2])
            data = blobs.read(size)
            if len(data) != size or blobs.read(1) != b"\n":
                raise ValueError("archived receipt blob is incomplete")
            hashes[oid] = hashlib.sha256(data).hexdigest()
    return {
        name: {"mode": mode, "sha256": hashes[oid]}
        for name, (mode, oid) in entries.items()
    }


def _log(root: Path, output: str) -> dict[str, str]:
    for line in output.splitlines():
        if line.startswith("[log] "):
            path = Path(line[6:].strip())
            if not path.is_absolute():
                path = root / path
            relative = path.resolve().relative_to(root.resolve())
            return {"path": str(relative), "sha256": digest(path)}
    directory = root / "notes" / "verification" / "receipts" / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.log"
    path.write_text(output)
    return {"path": str(path.relative_to(root)), "sha256": digest(path)}


def _execution(
    root: Path, command: list[str] | None, returncode: int
) -> dict[str, Any] | None:
    """Bind the reports produced at the invocation's declared destination."""
    if command is None or "--verification-output" not in command:
        return None
    try:
        path = command[command.index("--verification-output") + 1]
    except IndexError:
        return None
    execution = _read_execution(root, path, returncode)
    return None if execution is None else execution.record


def _read_execution(root: Path, file: str, returncode: int) -> _PytestExecution | None:
    """Read completed pytest reports from their bound path."""
    try:
        path = (root / file).resolve()
        relative = path.relative_to(root.resolve())
        contents = path.read_bytes()
        data = json.loads(contents)
        selected, called, finished = (
            set(data[key]) for key in ("selected", "called", "finished")
        )
        failed = set(data.get("failed_calls", []))
        # Earlier archives did not record passing calls.
        passed = set(data.get("passed_calls", []))
        selection = data["selection"]
        if (
            data["schema"] != 1
            or data["exitstatus"] != returncode
            or selection["collect_only"]
            or not called
            or not called <= selected
            or not failed | passed <= called
            or (returncode == 0 and (failed or ("passed_calls" in data and not passed)))
            or finished != selected
        ):
            return None
    except (OSError, KeyError, TypeError, ValueError):
        return None
    record = {
        "path": str(relative),
        "sha256": hashlib.sha256(contents).hexdigest(),
        "selection": selection,
        "selected": len(selected),
        "called": len(called),
    }
    return _PytestExecution(record, failed, passed)


def _bound_execution(root: Path, row: dict[str, Any]) -> _PytestExecution | None:
    record = row.get("execution")
    if record is None:
        return None
    execution = _read_execution(root, record["path"], row["returncode"])
    return execution if execution is not None and execution.record == record else None


def _pytest_retry_covers(
    root: Path, checks: list[dict[str, Any]], ids: list[str] | None = None
) -> bool:
    """Require a passing retry report for each failed call in the first run."""
    original = [row for row in checks if row["name"] == "pytest"]
    retries = [row for row in checks if row["name"] == "pytest retry"]
    if len(original) != 1 or len(retries) != 1 or retries[0]["returncode"] != 0:
        return False
    failed = _bound_execution(root, original[0])
    retry = _bound_execution(root, retries[0])
    return bool(
        failed is not None
        and retry is not None
        and failed.failed
        and (ids is None or failed.failed == set(ids))
        and failed.failed <= retry.passed
    )


def _successful(
    root: Path,
    plan: dict[str, list[str]],
    checks: list[dict[str, Any]],
    retries: set[str],
    returncode: int | None,
) -> bool:
    if returncode != 0 or not plan:
        return False
    for name, command in plan.items():
        rows = [row for row in checks if row["name"] == name]
        if len(rows) != 1 or rows[0]["command"] != command:
            return False
        if name == "pytest" and rows[0].get("execution") is None:
            return False
        if rows[0]["returncode"] == 0:
            continue
        repeated = [row for row in checks if row["name"] == f"{name} retry"]
        if name not in retries or len(repeated) != 1 or repeated[0]["returncode"] != 0:
            return False
        if name == "pytest" and not _pytest_retry_covers(root, checks):
            return False
    return True


def environment() -> dict[str, Any]:
    """Describe the interpreter and dependency environment executing this code."""
    return {
        "python": sys.version,
        "python_version": list(sys.version_info),
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "packages": {
            distribution.metadata["Name"]: distribution.version
            for distribution in importlib.metadata.distributions()
        },
        "options": {
            name: os.environ[name]
            for name in (
                "PYTEST_ADDOPTS",
                "PYTHONHASHSEED",
                "VERIFY_FULL",
                "UV_PYTHON",
                "VIRTUAL_ENV",
                "UV_PROJECT_ENVIRONMENT",
            )
            if name in os.environ
        },
    }


class AcceptanceRun:
    """Capture exact inputs, check scope, bounds, environment and outcomes."""

    def __init__(self, root: Path, argv: list[str], bounds: dict[str, float]) -> None:
        """Snapshot the checkout and verification environment before checks."""
        self.root = root
        self.started = time.time()
        self.before = inputs(root)
        self.revision = _git(root, "rev-parse", "HEAD").strip()
        self.argv = argv
        self.bounds = bounds
        self.plan: dict[str, list[str]] = {}
        self.steps: list[dict[str, Any]] = []
        self.accepted_retries: set[str] = set()
        self.lock = threading.Lock()
        self.controller_environment = environment()
        self.environment = self.controller_environment
        self.environment_command: list[str] | None = None

    def capture_environment(self, command: list[str], env: dict[str, str]) -> None:
        """Probe the actual check interpreter after dependency synchronization."""
        probe = [*command, str(Path(__file__).resolve()), "--environment"]
        result = subprocess.run(
            probe,
            cwd=self.root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.environment = json.loads(result.stdout)
        self.environment_command = probe

    def declare(self, plan: list[tuple[str, list[str], dict[str, str]]]) -> None:
        """Retain the resolved commands, before any check starts."""
        self.plan = {name: command for name, command, _ in plan}

    def record(
        self,
        name: str,
        seconds: float,
        returncode: int,
        output: str | None,
        *,
        command: list[str] | None = None,
    ) -> None:
        """Attach a completed check and the hash of its complete log."""
        resolved_command = self.plan.get(name) if command is None else command
        row: dict[str, Any] = {
            "name": name,
            "command": resolved_command,
            "seconds": seconds,
            "returncode": returncode,
            "deadline_seconds": self.bounds.get(
                name.removesuffix(" retry"), self.bounds["default"]
            ),
            "evidence": _log(self.root, output or ""),
        }
        if name in {"pytest", "pytest retry"}:
            row["execution"] = _execution(self.root, resolved_command, returncode)
        with self.lock:
            self.steps.append(row)

    def pytest_retry_covers(self, ids: list[str]) -> bool:
        """Confirm that the diagnosed tests failed and passed on retry."""
        return _pytest_retry_covers(self.root, self.steps, ids)

    def finish(self, returncode: int | None) -> tuple[Path, bool]:
        """Write a unique receipt; changed inputs and vacuous runs cannot pass."""
        after = inputs(self.root)
        unchanged = self.before == after
        passed = unchanged and _successful(
            self.root, self.plan, self.steps, self.accepted_retries, returncode
        )
        value = {
            "schema": 2,
            "revision": self.revision,
            "argv": self.argv,
            "started": self.started,
            "seconds": time.time() - self.started,
            "environment": self.environment,
            "environment_command": self.environment_command,
            "controller_environment": self.controller_environment,
            "inputs": self.before,
            "inputs_unchanged": unchanged,
            "changed_inputs": sorted(
                name
                for name in self.before.keys() | after.keys()
                if name not in self.before
                or name not in after
                or self.before[name] != after[name]
            ),
            "scope": self.plan,
            "bounds": self.bounds,
            "checks": self.steps,
            "accepted_retries": sorted(self.accepted_retries),
            "returncode": returncode,
            "status": "passed" if passed else "unverified",
        }
        directory = self.root / "notes" / "verification" / "receipts"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
        return path, passed


def _validate_receipt(
    value: dict[str, Any], root: Path, evidence_root: Path, required: set[str]
) -> None:
    schema = value["schema"]
    if (
        schema not in (1, 2)
        or value["status"] != "passed"
        or not _successful(
            evidence_root,
            value["scope"],
            value["checks"],
            set(value["accepted_retries"]),
            value["returncode"],
        )
    ):
        raise ValueError("receipt does not establish acceptance")
    expected = value["inputs"]
    commit = value.get("committed_revision")
    actual: Mapping[str, _Input | None]
    if commit is None:
        actual = inputs(root)
        mismatch = "receipt inputs do not match this checkout"
    else:
        # A deleted path was still in the index when the gate ran.
        expected = {
            name: digest for name, digest in expected.items() if digest is not None
        }
        actual = _commit_inputs(root, commit)
        mismatch = "receipt inputs do not match the recorded commit"
    observed = (
        {name: entry["sha256"] if entry else None for name, entry in actual.items()}
        if schema == 1
        else actual
    )
    if not value["inputs_unchanged"] or expected != observed:
        raise ValueError(mismatch)
    if not required <= value["scope"].keys():
        raise ValueError("receipt does not cover the required scope")
    checks = {row["name"]: row for row in value["checks"]}
    if not required <= checks.keys():
        raise ValueError("receipt is missing completed checks")
    for row in value["checks"]:
        if (
            row.get("execution") is not None
            and _bound_execution(evidence_root, row) is None
        ):
            raise ValueError("pytest execution evidence was changed")
        evidence = row["evidence"]
        if "path" in evidence:
            log = _evidence_path(evidence_root, evidence["path"])
            if digest(log) != evidence["sha256"]:
                raise ValueError("receipt log was changed")


def _evidence_path(root: Path, relative: str) -> Path:
    """Resolve a bound evidence file within its receipt's evidence root."""
    if Path(relative).is_absolute():
        raise ValueError("receipt evidence paths must be relative")
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def validate(path: Path, root: Path, required: set[str]) -> None:
    """Verify evidence and inputs against the live checkout or recorded commit."""
    value = json.loads(path.read_text())
    evidence_root = path.parent if "committed_revision" in value else root
    _validate_receipt(value, root, evidence_root, required)


def archive(path: Path, root: Path, primary: Path) -> Path:
    """Publish a verified receipt and its evidence under the current commit."""
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("archive verification after committing the checked files")
    common = ("rev-parse", "--path-format=absolute", "--git-common-dir")
    if _git(root, *common).strip() != _git(primary, *common).strip():
        raise ValueError("verification archive must stay in the same repository")
    commit = _git(root, "rev-parse", "HEAD").strip()
    value = json.loads(path.read_text())
    if "committed_revision" in value:
        raise ValueError("receipt is already archived")
    value["committed_revision"] = commit
    _validate_receipt(value, root, root, set())

    parent = primary.resolve() / "notes" / "verification" / "commits" / commit
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / path.stem
    if destination.exists():
        raise FileExistsError(f"receipt archive already exists: {destination}")
    with tempfile.TemporaryDirectory(prefix=".archive-", dir=parent) as scratch:
        bundle = Path(scratch)
        for row in value["checks"]:
            for evidence in (row["evidence"], row.get("execution")):
                if evidence is None or "path" not in evidence:
                    continue
                original = _evidence_path(root, evidence["path"])
                copy = _evidence_path(bundle, evidence["path"])
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, copy)
        _validate_receipt(value, root, bundle, set())
        (bundle / "receipt.json").write_text(
            json.dumps(value, sort_keys=True, indent=2) + "\n"
        )
        bundle.rename(destination)
    return destination / "receipt.json"


def main() -> int:
    """Print the check environment or archive the current commit's receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--environment", action="store_true")
    command.add_argument(
        "--archive", nargs=2, type=Path, metavar=("RECEIPT", "PRIMARY")
    )
    args = parser.parse_args()
    if args.environment:
        print(json.dumps(environment()))
    else:
        try:
            path, primary = args.archive
            print(archive(path, Path.cwd(), primary))
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
