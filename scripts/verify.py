"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types)
2. pytest (the test suite)
3. unicorn-based round-trips (RISC-V assembly compilers, RISC-V cross-check
   generators, and -- if a RISC-V 123 binary can be built -- the 123
   differential across RISC-V and the simulator)

The native qemu-riscv64 checks need Linux, so they run only in CI (see
.github/workflows/ci.yml).

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
        "duplicate-code check",
        [*PY, "scripts/check_duplicates.py"],
    ),
    (
        "single-interpreter installer",
        [*PY, "scripts/verify_install_one.py"],
    ),
]


def _build_riscv_123() -> str | None:
    if shutil.which("riscv64-elf-gcc") is None:
        return None
    rv = subprocess.run(
        [
            "riscv64-elf-gcc",
            "-nostdlib",
            "-static",
            "-march=rv64i",
            "-mabi=lp64",
            "-o",
            "/tmp/123-riscv",
            "extra/assembly/123-riscv.s",
        ],
        capture_output=True,
    )
    return "/tmp/123-riscv" if rv.returncode == 0 else None


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
        result = subprocess.run(cmd, env=env)
        ok = result.returncode == 0
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name}")

    if have_unicorn and have_riscv_gcc:
        rv = _build_riscv_123()
        if rv is None:
            print("[skip] 123 differential: riscv64-elf-gcc or build failed")
        else:
            cmd = [
                *PY,
                "scripts/verify_123_differential.py",
                rv,
                "Hi",
                "Hello, World!",
            ]
            result = subprocess.run(cmd, env=env)
            ok = result.returncode == 0
            failures += not ok
            print(f"[{'ok' if ok else 'FAIL'}] 123 differential (unicorn)")
    else:
        print("[skip] 123 differential: requires unicorn and a RISC-V compiler")

    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
