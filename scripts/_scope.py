"""Work out which files a branch touched, so checks can skip what it did not.

The full local stack takes ~97s, and most of that is spent re-proving things
the current branch cannot have broken: a change to one tape interpreter does
not need the native cross-checks for the other languages re-run.  This module
supplies the shared "what changed?" query that ``verify.py`` and
``verify_differential.py`` scope themselves with.

The rule is deliberately conservative.  Scoping is only ever an optimisation:
when the answer is unclear -- no diff available, a detached HEAD, no
``origin/main`` -- the caller is told to run *everything*, because a check that
is skipped by accident is a check that silently stops guarding.  Touching the
shared machinery in ``_SHARED`` (or the checking machinery itself) also widens
the sweep back to the full set, since either can change how every interpreter
reads, steps, or reports.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Changing any of these changes how *every* interpreter reads, steps, or
# reports, so touching one sweeps the whole registry rather than nothing.
SHARED_INTERPRETER = (
    "interpreters/io.py",
    "interpreters/memory.py",
    "interpreters/brackets.py",
    "exceptions.py",
    "vm.py",
    "registry.py",
)

# The checking machinery itself.  A change here can alter what every step
# does, so it can never be validated by a scoped run of that same machinery.
SHARED_TOOLING = (
    "scripts/verify.py",
    "scripts/_scope.py",
    "scripts/verify_differential.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "justfile",
)


def changed_files() -> list[str]:
    """Return the repo-relative paths this branch changed, or [] if unknown.

    Prefers the branch's own diff against ``origin/main``; falls back to the
    last commit when there is no such ref (a fresh clone, a detached HEAD).
    Uncommitted work counts too -- the point is to check the tree in hand, not
    only what has been committed.  An empty list means "could not tell", which
    callers must read as "run everything".
    """
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

    # Uncommitted edits are part of the tree being checked whether or not the
    # committed diff resolved, so they are collected even when neither ref did.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            # A rename is reported as "R  old -> new"; the new path is the one
            # that exists to be checked, so a rename never scopes itself out.
            path = line[3:].strip().split(" -> ")[-1]
            if path:
                names.append(path)

    # A file that is both committed on the branch and dirty in the tree appears
    # in both queries.  Passing the same path to a checker twice is not merely
    # wasteful -- mypy rejects the repeat as a duplicate module -- so the list
    # is deduplicated while keeping its order stable for readable output.
    return list(dict.fromkeys(names))


def widens_to_everything(changed: list[str]) -> str | None:
    """Return why *changed* forces a full run, or ``None`` if scoping is safe."""
    if not changed:
        return "no diff available"
    if any(f.endswith(SHARED_INTERPRETER) for f in changed):
        return "shared interpreter machinery changed"
    if any(f.endswith(SHARED_TOOLING) for f in changed):
        return "verification tooling changed"
    return None
