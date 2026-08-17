"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types) and pytest (the test suite)
2. bandit (via uv), cargo fmt/test (the Rust cross-checks), and the
   interpreter-vs-native differential corpora
3. unicorn-based round-trips (RISC-V assembly compilers, RISC-V cross-check
   generators, and the differential corpora) — skipped when unicorn or the
   RISC-V cross-compiler is missing

The native qemu-riscv64 checks need Linux, so they run only in CI (see
.github/workflows/ci.yml).  ``scripts/check_all.sh`` is a thin wrapper around
this script.

Usage:
    python scripts/verify.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

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
        "cargo test",
        ["cargo", "test", "--manifest-path", "extra/rust/Cargo.toml"],
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


def main() -> int:
    """Compile and run every example, reporting failures."""
    import importlib.util
    import os

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    have_unicorn = importlib.util.find_spec("unicorn") is not None
    have_riscv_gcc = (
        shutil.which("riscv64-elf-gcc") is not None
        or shutil.which("riscv64-linux-gnu-gcc") is not None
    )

    failures = 0
    for name, cmd in STEPS:
        if not have_unicorn and "unicorn" in name:
            print(f"[skip] {name}: unicorn not installed (pip install unicorn)")
            continue
        if not have_riscv_gcc and "assembly" in name:
            print(f"[skip] {name}: RISC-V cross-compiler not installed")
            continue
        if shutil.which("uv") is None and "bandit" in name:
            print(f"[skip] {name}: uv not installed")
            continue
        if shutil.which("cargo") is None and "cargo" in name:
            print(f"[skip] {name}: Rust toolchain (cargo) not installed")
            continue
        result = subprocess.run(cmd, env=env)
        ok = result.returncode == 0
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name}")

    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
