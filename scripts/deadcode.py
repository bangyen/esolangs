"""Generator lines and branch arms that no test reaches, against a baseline.

A scan runs every band (fast, medium and slow) under branch coverage, or
reads ``--data`` when it exists, and lists the generator lines and branch
arms that never executed.  Entries are keyed by source text, not line number,
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
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mutants import registry_keyword

from esolangs.registry import LANGUAGES as REGISTRY
from esolangs.registry import resolve

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "esolangs" / "languages"
KNOWN = Path(__file__).parent / "baselines/deadcode_known.toml"


def _collect(data: Path, packages: list[str]) -> None:
    """Run the suite, or ``packages``' tests, under branch coverage into ``data``."""
    env = {**os.environ, "COVERAGE_FILE": str(data)}
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
    subprocess.run(cmd, cwd=ROOT, env=env, check=False)


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
        files: dict[str, dict[str, Any]] = json.loads(out.read_text())["files"]
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
        help=".coverage file: read it, or collect into it if missing",
    )
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument("languages", nargs="*", help="scan only these")
    args = parser.parse_args()
    try:
        packages = [REGISTRY[resolve(n)].id.replace("-", "_") for n in args.languages]
    except ValueError as exc:
        parser.error(str(exc))
    if packages and args.update:
        parser.error("--update rewrites the whole-tree baseline: name no languages")
    data = args.data or Path(tempfile.mkdtemp()) / ".coverage"
    if not data.exists():
        _collect(data, packages)
    found = _entries(_report(data, packages))
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
