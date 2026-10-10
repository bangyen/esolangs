"""Bound replay reads and fingerprint candidate import dependencies."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any

MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 256


def read_json(path: Path) -> Any:
    """Read at most eight MiB, including when the file grows during reading."""
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("evidence file exceeds eight MiB")
    return json.loads(data)


def identity(spec: str) -> dict[str, Any]:
    """Hash the candidate and its statically named local Python imports."""
    name, _, function = spec.rpartition(":")
    source = Path(name).resolve()
    if not function or not source.is_file():
        raise ValueError("candidate must be an existing FILE.py:FUNC")
    roots = [source.parent, Path(__file__).resolve().parents[2] / "src"]
    pending = [source]
    hashes: dict[str, str] = {}
    size = 0
    while pending:
        path = pending.pop().resolve()
        if str(path) in hashes:
            continue
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        size += len(data)
        if size > MAX_BYTES or len(hashes) >= MAX_FILES:
            raise ValueError("candidate dependencies exceed fingerprint limits")
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        for node in ast.walk(ast.parse(data, filename=str(path))):
            names: list[str] = []
            search = roots
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                names = [
                    prefix,
                    *[f"{prefix}.{alias.name}".strip(".") for alias in node.names],
                ]
                if node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    search = [base]
            for module in names:
                if not module:
                    continue
                for root in search:
                    target = root.joinpath(*module.split("."))
                    for dependency in (
                        target.with_suffix(".py"),
                        target / "__init__.py",
                    ):
                        if dependency.is_file():
                            pending.append(dependency)
                    for parent in target.parents:
                        if parent == root or root not in parent.parents:
                            break
                        init = parent / "__init__.py"
                        if init.is_file():
                            pending.append(init)
    return {
        "spec": f"{source}:{function}",
        "sha256": hashes[str(source)],
        "dependencies": hashes,
    }


def replay(path: Path, max_bits: int) -> dict[str, Any]:
    """Validate all fields consumed by candidate replay before execution."""
    record = read_json(path)
    if (
        not isinstance(record, dict)
        or type(record.get("schema")) is not int
        or record["schema"] != 1
    ):
        raise ValueError("invalid replay schema")
    for key in ("language", "family"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"invalid replay {key}")
    if type(record.get("seed")) is not int:
        raise ValueError("invalid replay seed")
    if record.get("target") is not None and not isinstance(record["target"], str):
        raise ValueError("invalid replay target")
    for key in ("candidate", "checkout"):
        if not isinstance(record.get(key), dict):
            raise ValueError(f"invalid replay {key}")
    checkout = record["checkout"]
    if (
        not all(
            isinstance(checkout.get(key), str) and checkout[key]
            for key in ("commit", "checkout")
        )
        or type(checkout.get("dirty")) is not bool
        or not all(
            _digest(checkout.get(key))
            for key in ("tracked_diff_sha256", "untracked_sha256")
        )
    ):
        raise ValueError("invalid replay checkout identity")
    candidate = record["candidate"]
    if not all(
        isinstance(candidate.get(key), str) and candidate[key]
        for key in ("spec", "sha256")
    ):
        raise ValueError("invalid replay candidate identity")
    if not _digest(candidate["sha256"]):
        raise ValueError("invalid replay candidate hash")
    dependencies = candidate.get("dependencies")
    if (
        not isinstance(dependencies, dict)
        or not dependencies
        or len(dependencies) > MAX_FILES
        or not all(
            isinstance(key, str) and key and _digest(value)
            for key, value in dependencies.items()
        )
    ):
        raise ValueError("invalid replay dependencies")
    runtime = record.get("runtime_dependencies", {})
    if (
        not isinstance(runtime, dict)
        or len(runtime) > MAX_FILES
        or not all(
            isinstance(key, str) and key and _digest(value)
            for key, value in runtime.items()
        )
    ):
        raise ValueError("invalid replay runtime dependencies")
    table = record.get("table")
    if (
        not isinstance(table, str)
        or not table
        or set(table) - {"0", "1"}
        or len(table) & (len(table) - 1)
        or len(table) > max_bits
    ):
        raise ValueError("invalid or oversized replay table")
    rows = record.get("rows")
    if (
        not isinstance(rows, list)
        or not rows
        or any(type(row) is not int or not 0 <= row < len(table) for row in rows)
        or len(set(rows)) != len(rows)
    ):
        raise ValueError("invalid replay rows")
    bounds = record.get("bounds")
    if (
        not isinstance(bounds, dict)
        or type(bounds.get("step_cap")) is not int
        or bounds["step_cap"] < 1
    ):
        raise ValueError("invalid replay bounds")
    for key in ("timeout", "generation_timeout"):
        value: Any = bounds.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("invalid replay bounds")
    return record


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def loaded_dependencies(spec: str) -> dict[str, str]:
    """Hash loaded Python modules under the candidate directory or repo source."""
    import sys

    roots = [
        Path(spec.rpartition(":")[0]).resolve().parent,
        Path(__file__).resolve().parents[2] / "src",
    ]
    paths = set()
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not isinstance(name, str):
            continue
        path = Path(name).resolve()
        if path.suffix == ".py" and any(path.is_relative_to(root) for root in roots):
            paths.add(path)
    if len(paths) > MAX_FILES:
        raise ValueError("loaded dependencies exceed fingerprint limits")
    hashes = {}
    size = 0
    for path in sorted(paths):
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        size += len(data)
        if size > MAX_BYTES:
            raise ValueError("loaded dependencies exceed fingerprint limits")
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
    return hashes


def dependencies_changed(hashes: dict[str, str]) -> bool:
    """Compare bounded runtime dependency bytes, treating missing files as drift."""
    size = 0
    for name, expected in hashes.items():
        try:
            with Path(name).open("rb") as stream:
                data = stream.read(MAX_BYTES + 1)
        except OSError:
            return True
        size += len(data)
        if size > MAX_BYTES or hashlib.sha256(data).hexdigest() != expected:
            return True
    return False
