"""Check a checkout is set up to contribute; print the fix for each gap.

Runs without ``just`` (``python scripts/doctor.py``): the justfile needs
just 1.37, and an older one cannot parse it at all, so ``just doctor`` is
unreachable exactly when the version check matters.  Exits 1 on any gap.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# [group] and [doc] parse from 1.27; groups list in source order from 1.30,
# and [doc] overrides the recipe comment from 1.37 (just --changelog).
JUST_MIN = (1, 37)


def _output(*cmd: str) -> str | None:
    """Return ``cmd``'s stdout, or None when it is missing or fails."""
    if shutil.which(cmd[0]) is None:
        return None
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return done.stdout.strip() if done.returncode == 0 else None


def _just_found() -> str | None:
    if shutil.which("just") is None:
        return "just not found: install just >= 1.37, or run the scripts directly"
    return None


def _just() -> str | None:
    found = _output("just", "--version")
    if found is None:
        return None  # absent is _just_found's note; old is the failure
    match = re.search(r"(\d+)\.(\d+)", found)
    if match is None or tuple(map(int, match.groups())) < JUST_MIN:
        return f"{found} is older than 1.37, which the justfile needs: upgrade just"
    return None


def _uv() -> str | None:
    if shutil.which("uv") is None:
        return "uv not found: install uv, or use `pip install -e . --group dev`"
    return None


def _dev_deps() -> str | None:
    missing = [
        name
        for name in ("pytest", "xdist", "mypy", "pylint")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        return f"dev dependencies missing ({', '.join(missing)}): just install-dev"
    return None


def _hooks() -> str | None:
    # Relative (what install-dev sets) or absolute: a worktree may point at
    # the primary checkout's hooks, which run just the same.
    configured = _output("git", "config", "core.hooksPath")
    if configured is None or not (ROOT / configured / "pre-push").is_file():
        return "pre-push gate not enabled: git config core.hooksPath .githooks"
    return None


def _checkout() -> str | None:
    spec = importlib.util.find_spec("esolangs")
    here = ROOT / "src" / "esolangs" / "__init__.py"
    if spec is None or spec.origin is None:
        return "esolangs is not importable: just install-dev"
    if Path(spec.origin).resolve() != here:
        return (
            f"esolangs resolves to {spec.origin}, not this checkout: "
            "run through `uv run` or `just`"
        )
    return None


CHECKS: dict[str, Callable[[], str | None]] = {
    "just on PATH": _just_found,
    "just version": _just,
    "uv": _uv,
    "dev dependencies": _dev_deps,
    "pre-push hook": _hooks,
    "esolangs import": _checkout,
}
# The scripts run without just, and install-dev falls back to pip: a missing
# tool is advice; a just too old to parse the justfile is a gap.
ADVISORY = frozenset({"just on PATH", "uv"})


def main(argv: list[str] | None = None) -> int:
    """Print one line per check; return 1 if any found a gap."""
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args(argv)
    gaps = 0
    for name, check in CHECKS.items():
        problem = check()
        if problem is None:
            print(f"[ok] {name}")
        elif name in ADVISORY:
            print(f"[note] {name}: {problem}")
        else:
            gaps += 1
            print(f"[FAIL] {name}: {problem}")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
