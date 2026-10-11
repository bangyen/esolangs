"""Work out which files a branch touched, so checks can skip what it did not.

The rule is deliberately conservative: when the diff cannot be read, or the
shared machinery moved, the caller is told to run *everything* -- a check that
is skipped by accident is a check that silently stops guarding.
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Changing any of these changes how *every* interpreter reads, steps, or
# reports, so touching one sweeps the whole registry rather than nothing.
SHARED_INTERPRETER = (
    "interpreters/io.py",
    "interpreters/memory.py",
    "interpreters/brackets.py",
    "exceptions.py",
    "vm.py",
    "raster/__init__.py",
    "raster/png.py",
    "raster/scale.py",
    "registry/__init__.py",
    "registry/_slug.py",
    "registry/_table.py",
    "registry/_contracts.py",
    "registry/_language.py",
)

# The checking machinery itself.  A change here can alter what every step
# does, so it can never be validated by a scoped run of that same machinery.
SHARED_TOOLING = (
    "scripts/verify/gate.py",
    "scripts/verify/scope.py",
    "checks/check_diff_coverage.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "justfile",
)


def diff_paths(root: Path, *args: str) -> list[str] | None:
    """Return exact changed paths, or None when Git cannot establish the diff."""
    try:
        got = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", *args],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if got.returncode != 0:
        return None
    return [os.fsdecode(name) for name in got.stdout.split(b"\0") if name]


def changed_files() -> list[str]:
    """Return the repo-relative paths this branch changed, or [] if unknown.

    Prefers local ``main`` so unpushed integrated work is not attributed
    to this branch; tries ``origin/main`` and the last commit if absent.
    Uncommitted work counts too -- the point is to check the tree in hand, not
    only what has been committed.  An empty list means "could not tell", which
    callers must read as "run everything".
    """
    names: list[str] = []
    known = False
    for ref in ("main...HEAD", "origin/main...HEAD", "HEAD~1"):
        paths = diff_paths(ROOT, ref)
        if paths is not None:
            names = paths
            known = True
            break
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        cwd=ROOT,
        check=False,
        timeout=60,
    )
    if not known or status.returncode != 0:
        return []
    records = iter(status.stdout.split(b"\0"))
    for record in records:
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            return []
        names.append(os.fsdecode(record[3:]))
        if b"R" in record[:2] or b"C" in record[:2]:
            original = next(records, b"")
            if not original:
                return []
            names.append(os.fsdecode(original))
    # Committed-and-dirty paths repeat; mypy rejects duplicate modules.
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


TOOLING_INTEGRATIONS = {
    "tests/scripts/test_ci_coverage.py": (
        ("test_combining_shards_retains_every_branch",),
        (
            ".github/workflows/",
            "scripts/ci/shard.py",
            "checks/check_diff_coverage.py",
        ),
    ),
}


def local_tooling_deselections(changed: list[str]) -> list[str]:
    """Defer unrelated tooling integrations to the unchanged CI test bands."""
    if not changed or any(
        path in SHARED_TOOLING
        or path
        in {
            "uv.lock",
            ".coveragerc",
            "tests/conftest.py",
            "tests/__init__.py",
            "tests/scripts/script_support.py",
            "setup.cfg",
            "pytest.ini",
            "tox.ini",
        }
        or path.startswith("tests/fixtures/")
        or (path.startswith("tests/scripts/") and Path(path).name == "conftest.py")
        for path in changed
    ):
        return []
    return [
        f"--deselect={suite}::{test}"
        for suite, (tests, dependencies) in TOOLING_INTEGRATIONS.items()
        if not any(
            path == suite
            or path.startswith((*dependencies, "tests/scripts/__init__.py"))
            for path in changed
        )
        for test in tests
    ]
