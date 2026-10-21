"""Generator lines and branch arms that no test reaches, against a baseline.

A scan runs every band (fast, medium and slow) under branch coverage, or
reads ``--data`` when it exists, and lists the generator lines and branch
arms that never executed.  Entries are keyed by source text, not line number,
so unrelated edits do not churn ``deadcode_known.toml``; a scan exits 1 on any
entry the baseline lacks.  ``--update`` rewrites the baseline after triage:
each kept entry is reachable only past the tested arities or is a guard.

A whole-tree run takes about as long as ``just test-full`` plus coverage
overhead; give it 600 s.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "esolangs" / "languages"
KNOWN = Path(__file__).with_name("deadcode_known.toml")


def _collect(data: Path) -> None:
    """Run the whole suite under branch coverage into ``data``."""
    env = {**os.environ, "COVERAGE_FILE": str(data)}
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "", "-n", "4"]
    cmd += ["--cov", "--cov-branch", "--cov-report="]
    subprocess.run(cmd, cwd=ROOT, env=env, check=False)


def _report(data: Path) -> dict[str, dict[str, Any]]:
    """Return coverage's JSON ``files`` table for generator sources."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cov.json"
        cmd = [sys.executable, "-m", "coverage", "json", "-q", "-o", str(out)]
        cmd += [
            "--data-file",
            str(data),
            "--include",
            "*/languages/*/generator.py,*/languages/*/generator/**",
        ]
        subprocess.run(cmd, cwd=ROOT, check=True)
        files: dict[str, dict[str, Any]] = json.loads(out.read_text())["files"]
    return files


def _entries(files: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Map each generator file to its unreached lines and arms, as source text."""
    found: dict[str, set[str]] = defaultdict(set)
    for name, info in files.items():
        path = Path(name) if Path(name).is_absolute() else ROOT / name
        rel = path.resolve().relative_to(LANGUAGES).as_posix()
        lines = path.read_text().splitlines()

        def text(n: int, lines: list[str] = lines) -> str:
            return lines[n - 1].strip() if 0 < n <= len(lines) else "<exit>"

        keys = [f"line: {text(n)}" for n in info["missing_lines"]]
        keys += [f"arm: {text(a)} -> {text(b)}" for a, b in info["missing_branches"]]
        seen: dict[str, int] = defaultdict(int)
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
        description="Unreached generator code vs a baseline."
    )
    parser.add_argument(
        "--data",
        type=Path,
        help=".coverage file: read it, or collect into it if missing",
    )
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args()
    data = args.data or Path(tempfile.mkdtemp()) / ".coverage"
    if not data.exists():
        _collect(data)
    found = _entries(_report(data))
    if args.update:
        _dump(found)
        print(f"{sum(map(len, found.values()))} entries in {len(found)} files")
        return 0
    known = _load()
    new = {rel: sorted(found[rel] - known.get(rel, set())) for rel in sorted(found)}
    new = {rel: es for rel, es in new.items() if es}
    gone = sum(len(es - found.get(rel, set())) for rel, es in known.items())
    for rel, es in new.items():
        print(rel)
        print("\n".join(f"  {e}" for e in es))
    print(f"{sum(map(len, new.values()))} new, {gone} now reached")
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
