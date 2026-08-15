#!/bin/sh
# Run the local-checkable subset of CI before a push.  Every step that fails
# here would fail the GitHub workflow, so this catches it before the push.
#
# Not run: the RISC-V assembly job (needs gcc-riscv64 + qemu/unicorn) and the
# Lean job (needs elan + mathlib).  See .github/workflows/ci.yml.
set -e

cd "$(dirname "$0")/.."

PY=${PY:-.venv/bin/python}
CARGO=${CARGO:-cargo}

echo "== pre-commit =="
"$PY" -m pre_commit run --all-files

echo "== pytest =="
"$PY" -m pytest -q

echo "== bandit =="
uv run --with bandit bandit -r src -q

echo "== cargo fmt + test =="
"$CARGO" fmt --manifest-path extra/rust/Cargo.toml --check
"$CARGO" test --manifest-path extra/rust/Cargo.toml

echo "== verify scripts (no RISC-V toolchain or network required) =="
PYTHONPATH=src "$PY" scripts/verify_extra_generators.py

echo "check_all: all checks passed"
