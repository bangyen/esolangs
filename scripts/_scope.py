r"""Work out which files a branch touched, so checks can skip what it."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Changing any of these changes.
# reports, so touching one.
SHARED_INTERPRETER = (
    "interpreters/io.py",
    "interpreters/memory.py",
    "interpreters/brackets.py",
    "exceptions.py",
    "vm.py",
    "registry.py",
)

# The checking machinery itself.
# does, so it can never be.
SHARED_TOOLING = (
    "scripts/verify.py",
    "scripts/_scope.py",
    "scripts/check_diff_coverage.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "justfile",
)


def changed_files() -> list[str]:
    r"""Return the repo-relative paths this branch changed, or [] if."""
    names: list[str] = []
    for args in (
        ["diff", "--name-only", "origin/main...HEAD"],
        ["diff", "--name-only", "HEAD~1"],
    ):
        got = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=ROOT, check=False
        )
        if got.returncode == 0 and got.stdout.strip():
            names = got.stdout.split()
            break

    # Uncommitted edits are part of.
    # committed diff resolved, so.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            # A rename is reported as "R.
            # that exists to be checked, so.
            path = line[3:].strip().split(" -> ")[-1]
            if path:
                names.append(path)

    # A file that is both committed.
    # in both queries.
    # wasteful -- mypy rejects the.
    # is deduplicated while keeping.
    return list(dict.fromkeys(names))


def widens_to_everything(changed: list[str]) -> str | None:
    r"""Return why *changed* forces a full run, or ``None`` if scoping is."""
    if not changed:
        return "no diff available"
    if any(f.endswith(SHARED_INTERPRETER) for f in changed):
        return "shared interpreter machinery changed"
    if any(f.endswith(SHARED_TOOLING) for f in changed):
        return "verification tooling changed"
    return None
