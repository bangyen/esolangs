"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types) and pytest (the test suite)
2. bandit (via uv), cargo fmt/test (the Rust cross-checks), the ``extra/line``
   suites (via uv, which supplies the image libraries the package itself does
   not depend on), and the interpreter-vs-native differential corpora
3. unicorn-based round-trips (RISC-V assembly compilers, RISC-V cross-check
   generators, and the differential corpora) — skipped when unicorn or the
   RISC-V cross-compiler is missing

The native qemu-riscv64 checks need Linux, so they run only in CI (see
.github/workflows/ci.yml).  ``scripts/check_all.sh`` is a thin wrapper around
this script.

Usage:
    python scripts/verify.py [--only STEPS] [--skip STEPS] [--list]
    python scripts/verify.py --only pytest,"cargo test"   # comma-separated STEPS names
    python scripts/verify.py --only pre-commit,pytest --skip bandit
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]


def python_cmd() -> list[str]:
    """Return the project's Python command.

    ``verify.py`` may be run with the system interpreter (e.g. plain
    ``python scripts/verify.py``), which does not have the project's dev
    dependencies.  Prefer the local venv, then ``uv run python`` (the uv
    workflow the justfile uses), and only fall back to the running
    interpreter.
    """
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.exists():
        return [str(venv)]
    if shutil.which("uv") is not None:
        return ["uv", "run", "python"]
    return [sys.executable]


PY = python_cmd()

STEPS = [
    ("pre-commit", [*PY, "-m", "pre_commit", "run", "--all-files"]),
    ("pytest", [*PY, "-m", "pytest", "-q"]),
    ("bandit", ["uv", "run", "--with", "bandit", "bandit", "-r", "src", "-q"]),
    (
        "cargo fmt",
        ["cargo", "fmt", "--manifest-path", "extra/rust/Cargo.toml", "--check"],
    ),
    (
        "cargo build",
        ["cargo", "build", "--manifest-path", "extra/rust/Cargo.toml"],
    ),
    (
        "cargo test",
        ["cargo", "test", "--manifest-path", "extra/rust/Cargo.toml"],
    ),
    (
        # Run from extra/line: its modules import each other as flat top-level
        # names, and it needs image libraries the package does not depend on,
        # so they are supplied ad hoc rather than from the project env.
        "extra/line suites (uv)",
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--directory",
            "extra/line",
            "--with",
            "pillow",
            "--with",
            "numpy",
            "--with",
            "scipy",
            "--with",
            "scikit-image",
            "--with",
            "pytest",
            "--with",
            "pytest-xdist",
            "pytest",
            ".",
            "-q",
        ],
    ),
    (
        "ztoalc anchor table is reproducible",
        [*PY, "scripts/make_ztoalc_table.py", "--check"],
    ),
    (
        "RISC-V assembly under unicorn (compilers + cross-checks)",
        [*PY, "scripts/verify_riscv_unicorn.py"],
    ),
    (
        "extra cross-check generators",
        [*PY, "scripts/verify_extra_generators.py"],
    ),
    (
        "interpreter vs native differential corpora",
        [*PY, "scripts/verify_differential.py"],
    ),
    (
        "docstring check",
        [*PY, "scripts/check_docstrings.py"],
    ),
    (
        "duplicate-code check",
        [*PY, "scripts/check_duplicates.py"],
    ),
    (
        "single-interpreter installer",
        [*PY, "scripts/verify_install_one.py"],
    ),
]


def _parse_only_skip() -> tuple[set[str] | None, set[str] | None, bool, bool]:
    parser = argparse.ArgumentParser(description="Run the local verification stack")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="comma-separated subset of STEPS names to run (e.g. --only pytest,bandit)",
    )
    parser.add_argument(
        "--skip",
        type=str,
        default=None,
        help="comma-separated STEPS names to skip",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available STEPS names and exit",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress successful step output (only failures, [ok] and timing)",
    )
    args = parser.parse_args()
    if args.list:
        for name, _ in STEPS:
            print(name)
        sys.exit(0)
    only = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None
    skip = {s.strip() for s in args.skip.split(",") if s.strip()} if args.skip else None
    return only, skip, False, args.quiet


def main() -> int:
    """Compile and run every example, reporting failures."""
    import importlib.util
    import os

    only, skip, _, quiet = _parse_only_skip()

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    have_unicorn = importlib.util.find_spec("unicorn") is not None
    have_riscv_gcc = (
        shutil.which("riscv64-elf-gcc") is not None
        or shutil.which("riscv64-linux-gnu-gcc") is not None
    )

    failures = 0
    timings: list[tuple[str, float]] = []
    for name, cmd in STEPS:
        if only is not None and name not in only:
            continue
        if skip is not None and name in skip:
            print(f"[skip] {name}: filtered via --skip")
            continue
        if not have_unicorn and "unicorn" in name:
            print(f"[skip] {name}: unicorn not installed (pip install unicorn)")
            continue
        if not have_riscv_gcc and "assembly" in name:
            print(f"[skip] {name}: RISC-V cross-compiler not installed")
            continue
        if shutil.which("uv") is None and ("bandit" in name or "(uv)" in name):
            print(f"[skip] {name}: uv not installed")
            continue
        if shutil.which("cargo") is None and "cargo" in name:
            print(f"[skip] {name}: Rust toolchain (cargo) not installed")
            continue
        start = time.time()
        result: subprocess.CompletedProcess[Any]
        if quiet:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if result.returncode != 0 and result.stdout:
                print(result.stdout, end="")
        else:
            result = subprocess.run(cmd, env=env)
        elapsed = time.time() - start
        timings.append((name, elapsed))
        ok = result.returncode == 0
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name} ({elapsed:.1f}s)")

    if timings:
        print("-" * 40)
        for name, elapsed in timings:
            print(f"{elapsed:5.1f}s  {name}")
        total = sum(t for _, t in timings)
        print(f"{total:5.1f}s  TOTAL")
    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
