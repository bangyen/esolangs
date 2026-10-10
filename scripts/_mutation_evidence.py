"""Identify the source and tests actually supplied to a mutation harness."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text
from benchmark import source_identity


def provenance(project: Path | None = None) -> dict[str, Any]:
    """Record checkout, runtime, mutmut version and copied harness input hashes."""
    try:
        version = importlib.metadata.version("mutmut")
    except importlib.metadata.PackageNotFoundError:
        version = None
    result = {
        "checkout": source_identity(),
        "python": sys.version,
        "platform": platform.platform(),
        "mutmut": version,
    }
    if project is not None:
        sources: dict[str, str] = {}
        tests: dict[str, str] = {}
        for path in sorted(project.rglob("*.py")):
            relative = path.relative_to(project)
            if "mutants" in relative.parts or "__pycache__" in relative.parts:
                continue
            target = tests if relative.parts[0] == "tests" else sources
            target[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        result.update(
            {
                "source_sha256": sources,
                "tests_sha256": tests,
                "configuration_sha256": hashlib.sha256(
                    (project / "pyproject.toml").read_bytes()
                ).hexdigest(),
            }
        )
    return result


def publish(path: Path, score: dict[str, Any], evidence: dict[str, Any]) -> None:
    """Atomically write completed scores only with a known mutmut version."""
    if not evidence.get("mutmut"):
        raise ValueError("mutation evidence lacks mutmut version")
    write_text(
        path,
        json.dumps(
            {"schema": 1, **score, "provenance": evidence}, indent=2, sort_keys=True
        )
        + "\n",
    )
