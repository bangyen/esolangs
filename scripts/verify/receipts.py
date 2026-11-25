"""Content-bound acceptance evidence for a concrete verification run."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    """Hash the complete artifact, refusing missing evidence."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout


def inputs(root: Path) -> dict[str, str | None]:
    """Fingerprint tracked and nonignored new files, including deletions."""
    names = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return {
        name: digest(root / name) if (root / name).is_file() else None
        for name in sorted(set(names.split("\0")) - {""})
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


def _successful(
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
        if rows[0]["returncode"] == 0:
            continue
        repeated = [row for row in checks if row["name"] == f"{name} retry"]
        if name not in retries or len(repeated) != 1 or repeated[0]["returncode"] != 0:
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
        row = {
            "name": name,
            "command": self.plan.get(name) if command is None else command,
            "seconds": seconds,
            "returncode": returncode,
            "deadline_seconds": self.bounds.get(
                name.removesuffix(" retry"), self.bounds["default"]
            ),
            "evidence": _log(self.root, output or ""),
        }
        with self.lock:
            self.steps.append(row)

    def finish(self, returncode: int | None) -> tuple[Path, bool]:
        """Write a unique receipt; changed inputs and vacuous runs cannot pass."""
        after = inputs(self.root)
        unchanged = self.before == after
        passed = unchanged and _successful(
            self.plan, self.steps, self.accepted_retries, returncode
        )
        value = {
            "schema": 1,
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


def validate(path: Path, root: Path, required: set[str]) -> None:
    """Refuse stale inputs, changed logs, missing scope and failed receipts."""
    value = json.loads(path.read_text())
    if (
        value["schema"] != 1
        or value["status"] != "passed"
        or not _successful(
            value["scope"],
            value["checks"],
            set(value["accepted_retries"]),
            value["returncode"],
        )
    ):
        raise ValueError("receipt does not establish acceptance")
    if not value["inputs_unchanged"] or value["inputs"] != inputs(root):
        raise ValueError("receipt inputs do not match this checkout")
    if not required <= value["scope"].keys():
        raise ValueError("receipt does not cover the required scope")
    checks = {row["name"]: row for row in value["checks"]}
    if not required <= checks.keys():
        raise ValueError("receipt is missing completed checks")
    for row in value["checks"]:
        evidence = row["evidence"]
        if "path" in evidence:
            log = (root / evidence["path"]).resolve()
            log.relative_to(root.resolve())
            if digest(log) != evidence["sha256"]:
                raise ValueError("receipt log was changed")


if __name__ == "__main__":
    if sys.argv[1:] != ["--environment"]:
        raise SystemExit("usage: receipts.py --environment")
    print(json.dumps(environment()))
