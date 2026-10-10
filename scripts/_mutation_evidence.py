"""Identify the source and tests actually supplied to a mutation harness."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
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


def validate(path: Path, kind: str, target: str, expected: dict[str, Any]) -> None:
    """Refuse incomplete, inconsistent or stale weekly completion evidence."""
    with path.open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("mutation score exceeds one MiB")
    record = json.loads(data)
    if (
        not isinstance(record, dict)
        or type(record.get("schema")) is not int
        or record["schema"] != 1
    ):
        raise ValueError("invalid mutation score schema")
    if record.get("kind") != kind or record.get("target") != target:
        raise ValueError("mutation score target changed")
    killed, total = record.get("killed"), record.get("total")
    if (
        type(killed) is not int
        or type(total) is not int
        or not 0 <= killed <= total
        or total < 1
    ):
        raise ValueError("invalid mutation score counts")
    survivors = record.get("survivors")
    if (
        not isinstance(survivors, list)
        or not all(isinstance(item, str) and item for item in survivors)
        or len(set(survivors)) != len(survivors)
        or len(survivors) != total - killed
    ):
        raise ValueError("invalid mutation survivors")
    evidence = record.get("provenance")
    if not isinstance(evidence, dict) or any(
        not expected.get(key) or evidence.get(key) != expected[key]
        for key in ("checkout", "python", "platform", "mutmut")
    ):
        raise ValueError("mutation score provenance changed")
    for key in ("source_sha256", "tests_sha256"):
        hashes = evidence.get(key)
        if (
            not isinstance(hashes, dict)
            or not hashes
            or not all(
                isinstance(name, str) and name and _digest(value)
                for name, value in hashes.items()
            )
        ):
            raise ValueError("mutation score lacks harness hashes")
    if not _digest(evidence.get("configuration_sha256")):
        raise ValueError("invalid mutation configuration hash")
    limits = evidence.get("limits")
    if (
        not isinstance(limits, dict)
        or type(limits.get("workers")) is not int
        or limits["workers"] < 1
    ):
        raise ValueError("invalid mutation limits")
    for key in ("per_test_alarm_seconds", "baseline_seconds"):
        value: Any = limits.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid mutation limits")


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )
