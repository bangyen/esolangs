"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types)
2. pytest (the test suite)
3. unicorn-based round-trips (assembly compilers, x86 reference
   generators, and -- if a RISC-V 123 binary can be built -- the 123
   differential across x86, RISC-V, and the simulator)

The native x86 link/run and qemu-riscv64 checks need Linux, so they run
only in CI (see .github/workflows/ci.yml).

Usage:
    python scripts/verify.py
"""

import shutil
import subprocess
import sys

STEPS = [
    ("pre-commit", [sys.executable, "-m", "pre_commit", "run", "--all-files"]),
    ("pytest", [sys.executable, "-m", "pytest", "-q"]),
    (
        "assembly compilers (unicorn)",
        [sys.executable, "scripts/verify_asm_compilers.py"],
    ),
    (
        "x86 reference generators (unicorn)",
        [sys.executable, "scripts/verify_x86_generators.py"],
    ),
]


def _build_riscv_123():
    if shutil.which("riscv64-elf-gcc") is None:
        return None
    if shutil.which("nasm") is None:
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


def main():
    import importlib.util
    import os

    env = dict(os.environ, PYTHONPATH="src")
    have_unicorn = importlib.util.find_spec("unicorn") is not None
    have_nasm = shutil.which("nasm") is not None

    failures = 0
    for name, cmd in STEPS:
        if not have_unicorn and "unicorn" in name:
            print(f"[skip] {name}: unicorn not installed (pip install unicorn)")
            continue
        if not have_nasm and "assembly" in name:
            print(f"[skip] {name}: nasm not installed")
            continue
        result = subprocess.run(cmd, env=env)
        ok = result.returncode == 0
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name}")

    if have_unicorn and have_nasm:
        rv = _build_riscv_123()
        if rv is None:
            print("[skip] 123 differential: riscv64-elf-gcc or build failed")
        else:
            cmd = [
                sys.executable,
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
        print("[skip] 123 differential: requires unicorn and nasm")

    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
