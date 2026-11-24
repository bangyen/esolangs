"""Generator lines and branch arms that no test reaches, against a baseline.

A scan runs every band (fast, medium and slow) under branch coverage, or
reads current coverage previously saved with ``--data``. It lists the generator
lines and branch arms that never executed. Entries are keyed by source text,
so unrelated edits do not churn ``deadcode_known.toml``; a scan exits 1 on any
entry the baseline lacks.  ``--update`` rewrites the baseline after triage:
each kept entry is reachable only past the tested arities or is a guard.

A whole-tree run took 574 s wall on 2026-10-21; the weekly workflow runs it
and fails on drift.  Named languages scan only their generators, under their
package tests and the registry tests matching their names (the selection
``mutants.py`` uses): 7-33 s each for Befunge, Minifuck, Line and Underload,
whose entries matched the whole-tree run's exactly.  Not always: Circuit
Diagram's took 388 s and reported 3 ``bundled_banks.py`` entries other
languages' tests reach, so confirm a scoped entry with a whole-tree run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mutants import registry_keyword
from verify import coverage as evidence
from verify.pytest_evidence import OUTPUT_OPTION, PLUGIN
from verify.receipts import digest

from esolangs.registry import LANGUAGES as REGISTRY
from esolangs.registry import resolve

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "esolangs" / "languages"
KNOWN = Path(__file__).parent / "baselines/deadcode_known.toml"


def _collect(data: Path, packages: list[str]) -> list[str]:
    """Run the suite, or ``packages``' tests, under branch coverage into ``data``."""
    env = {**os.environ, "COVERAGE_FILE": str(data)}
    env.pop("PYTEST_ADDOPTS", None)
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "", "-n", "4"]
    cmd += ["--cov", "--cov-branch", "--cov-report="]
    if packages:
        cmd += [f"src/esolangs/languages/{p}" for p in packages]
        cmd += [
            "tests",
            "-k",
            " or ".join(f"({registry_keyword(p)})" for p in packages),
        ]
        print(f"scanning {', '.join(packages)} under coverage", flush=True)
    else:
        # A first run otherwise sits silent for minutes.
        print(
            "scanning every band under coverage, about 10 min; "
            "name a language to scan one, --data FILE to keep the run",
            flush=True,
        )
    try:
        with tempfile.TemporaryDirectory(prefix="deadcode-execution-") as temporary:
            execution = Path(temporary) / "pytest.json"
            subprocess.run(
                [*cmd, "-p", PLUGIN, OUTPUT_OPTION, str(execution)],
                cwd=ROOT,
                env=env,
                check=True,
            )
            return evidence.completed(execution)
    except subprocess.CalledProcessError:
        # A later --data run must not accept this incomplete collection.
        data.unlink(missing_ok=True)
        raise


def _combine(data: Path, shards: list[Path], state: str) -> list[str]:
    """Combine private, verified copies of a complete coverage partition."""
    with tempfile.TemporaryDirectory(prefix="deadcode-shards-") as directory:
        staged, ordered = _verified_shards(Path(directory), shards, state)
        subprocess.run(
            [sys.executable, "-m", "coverage", "combine", "--keep", *map(str, staged)],
            cwd=ROOT,
            env={**os.environ, "COVERAGE_FILE": str(data)},
            check=True,
        )
    return ordered


def _verified_shards(
    directory: Path, shards: list[Path], state: str
) -> tuple[list[Path], list[str]]:
    """Verify the staged bytes and return their complete test selection."""
    staged: list[Path] = []
    indices: set[int] = set()
    nodes: set[str] = set()
    catalogue = None
    for number, shard in enumerate(shards):
        snapshot = directory / f".coverage.{number}"
        shutil.copyfile(shard, snapshot)
        selection = evidence.read(shard, state, snapshot=snapshot)
        index = selection.get("shard")
        selected = selection.get("nodes")
        if (
            type(index) is not int
            or not 0 <= index < len(shards)
            or index in indices
            or selection.get("shards") != len(shards)
            or not isinstance(selected, list)
            or not selected
            or any(not isinstance(node, str) for node in selected)
            or not nodes.isdisjoint(selected)
        ):
            raise ValueError(f"invalid or overlapping coverage shard {shard}")
        collected = selection.get("collected")
        if not isinstance(collected, str) or catalogue not in (None, collected):
            raise ValueError(f"coverage shard {shard} has a different test collection")
        catalogue = collected
        indices.add(index)
        nodes.update(selected)
        staged.append(snapshot)
    ordered = sorted(nodes)
    if evidence.fingerprint(ordered) != catalogue:
        raise ValueError("coverage shards do not cover the full test collection")
    return staged, ordered


def _saved_report(
    data: Path, packages: list[str], shards: list[Path]
) -> dict[str, set[str]]:
    """Read only coverage bound to this checkout and requested test scope."""
    outputs = (data, *shards)
    state = evidence.checkout(ROOT, *outputs)
    if shards or not data.exists():
        with tempfile.TemporaryDirectory(prefix=".coverage.", dir=data.parent) as stage:
            staged = Path(stage) / ".coverage"
            nodes = (
                _combine(staged, shards, state)
                if shards
                else _collect(staged, packages)
            )
            if evidence.checkout(ROOT, *outputs) != state:
                raise ValueError("checkout inputs changed during coverage collection")
            evidence.publish(
                staged, data, state, {"packages": packages, "nodes": nodes}
            )
    before = digest(data)
    selection = evidence.read(data, state)
    if selection.get("packages") != packages or not selection.get("nodes"):
        raise ValueError(
            f"coverage in {data} was collected for a different test selection"
        )
    found = _entries(_report(data, packages))
    if digest(data) != before or evidence.checkout(ROOT, *outputs) != state:
        raise ValueError("coverage inputs changed while preparing the report")
    return found


def _report(data: Path, packages: list[str]) -> dict[str, dict[str, Any]]:
    """Return coverage's JSON ``files`` table for generator sources."""
    include = ",".join(
        f"*/languages/{p}/generator.py,*/languages/{p}/generator/**"
        for p in packages or ["*"]
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cov.json"
        cmd = [sys.executable, "-m", "coverage", "json", "-q", "-o", str(out)]
        cmd += ["--data-file", str(data), "--include", include]
        subprocess.run(cmd, cwd=ROOT, check=True)
        report = json.loads(out.read_text(encoding="utf-8"))
    if report["meta"]["branch_coverage"] is not True:
        raise ValueError("generator coverage must include branch data")
    files: dict[str, dict[str, Any]] = report["files"]
    expected = {
        path.resolve()
        for package in packages or ["*"]
        for pattern in (f"{package}/generator.py", f"{package}/generator/**/*.py")
        for path in LANGUAGES.glob(pattern)
        if path.is_file()
    }
    missing = sorted(expected - {(ROOT / name).resolve() for name in files})
    if missing:
        preview = ", ".join(str(path.relative_to(LANGUAGES)) for path in missing[:3])
        ellipsis = ", ..." if len(missing) > 3 else ""
        raise ValueError(
            f"coverage is missing {len(missing)} generator source files: "
            f"{preview}{ellipsis}"
        )
    return files


def _text(lines: list[str], n: int) -> str:
    return lines[n - 1].strip() if 0 < n <= len(lines) else "<exit>"


def _entries(files: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Map each generator file to its unreached lines and arms, as source text."""
    found: dict[str, set[str]] = defaultdict(set)
    for name, info in files.items():
        path = Path(name) if Path(name).is_absolute() else ROOT / name
        rel = path.resolve().relative_to(LANGUAGES).as_posix()
        lines = path.read_text().splitlines()
        keys = [f"line: {_text(lines, n)}" for n in info["missing_lines"]]
        keys += [
            f"arm: {_text(lines, a)} -> {_text(lines, b)}"
            for a, b in info["missing_branches"]
        ]
        seen: Counter[str] = Counter()
        for key in keys:
            # Repeats are numbered, so a second unreached `return None` is new.
            seen[key] += 1
            found[rel].add(key if seen[key] == 1 else f"{key} #{seen[key]}")
    return found


def _load() -> dict[str, set[str]]:
    if not KNOWN.exists():
        return {}
    return {k: set(v) for k, v in tomllib.loads(KNOWN.read_text()).items()}


def _dump(found: dict[str, set[str]]) -> None:
    out = ["# Unreached generator code, triaged: see scripts/deadcode.py.", ""]
    for rel in sorted(found):
        out.append(f"{json.dumps(rel)} = [")
        out += [f"    {json.dumps(e)}," for e in sorted(found[rel])]
        out += ["]", ""]
    KNOWN.write_text("\n".join(out))


def main() -> int:
    """Scan, then report entries the baseline lacks (exit 1) or rewrite it."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--data",
        type=Path,
        help=".coverage file and receipt: read them, or collect if missing",
    )
    parser.add_argument("--combine-data", nargs="+", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("languages", nargs="*", help="scan only these")
    args = parser.parse_args()
    try:
        packages = sorted(
            {REGISTRY[resolve(n)].id.replace("-", "_") for n in args.languages}
        )
    except ValueError as exc:
        parser.error(str(exc))
    if packages and args.update:
        parser.error("--update rewrites the whole-tree baseline: name no languages")
    shards = [path.resolve() for path in args.combine_data or ()]
    if shards and (args.data is None or packages or args.data.resolve() in shards):
        parser.error(
            "--combine-data requires a distinct --data destination and no languages"
        )
    try:
        if args.data is None:
            with tempfile.TemporaryDirectory(prefix="deadcode-") as temporary:
                found = _saved_report(Path(temporary) / ".coverage", packages, [])
        else:
            found = _saved_report(args.data.resolve(), packages, shards)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    if args.update:
        _dump(found)
        print(f"{sum(map(len, found.values()))} entries in {len(found)} files")
        return 0
    known = _load()
    if packages:
        known = {k: v for k, v in known.items() if k.split("/")[0] in packages}
    new = {
        rel: es
        for rel in sorted(found)
        if (es := sorted(found[rel] - known.get(rel, set())))
    }
    gone = sum(len(es - found.get(rel, set())) for rel, es in known.items())
    for rel, es in new.items():
        print(rel)
        print("\n".join(f"  {e}" for e in es))
    print(f"{sum(map(len, new.values()))} new, {gone} now reached")
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
