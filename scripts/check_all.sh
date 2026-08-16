#!/bin/sh
# Run the local checks before a push.  This is a thin wrapper around
# scripts/verify.py, which runs every local check and skips the ones whose
# toolchains are missing (unicorn/RISC-V, uv, cargo).  The native qemu-riscv64
# and Lean jobs need Linux and run only in CI (see .github/workflows/ci.yml).
set -e

cd "$(dirname "$0")/.."

PY=${PY:-.venv/bin/python}
exec "$PY" scripts/verify.py
