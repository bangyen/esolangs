# Task runner for the project

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# Help
help:
    @just --list
    @echo ""
    @echo "  Four tiers, by what a test does rather than by a stopwatch"
    @echo "  (except the last, which is purely cost):"
    @echo "    fast   - unmarked; no interpreter run, no subprocess"
    @echo "    medium - runs a generated program, or drives the CLI/git"
    @echo "    slow   - the long tail, left to CI by a default 'just test'"
    @echo "    weekly - the two high-arity probes, 142.6s of the slow band's"
    @echo "             ~182s; even 'just test-full' skips them, and the"
    @echo "             weekly workflow is what runs them ('-m weekly' by hand)"
    @echo ""
    @echo "  Use 'just test-quick' for inner loop, 'just test-mid' before a commit,"
    @echo "  'just test-full' before a release."

# install tooling
install-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv >/dev/null 2>&1; then
        echo "Using uv..."
        uv pip install -e ".[dev]"
    else
        echo "Using pip..."
        python -m pip install -U pip
        pip install -e ".[dev]"
    fi
    # Enable the pre-push gate (scripts/verify.py) so every push runs the
    # full local check: lint, pytest, bandit, and the verify scripts.
    git config core.hooksPath .githooks

# lint python
# The formatter is ruff-format, run via pre-commit (and so via `just test`);
# `ruff check` here catches lint that formatting does not.
lint-python:
    {{PYTHON}} -m ruff check .
    {{PYTHON}} -m ruff format --check .
    {{PYTHON}} -m mypy

# lint all code
lint: lint-python
    @echo "All lint checks completed!"

# test (local check: lint, pytest, bandit, verify scripts)
# Scoped to the files this branch touched; widens to everything when the diff
# is unreadable or shared machinery moved.  Use `just test-full` to force the
# whole tree.  Pass --quiet to suppress successful step output.
test *args:
    {{PYTHON}} scripts/verify.py {{args}}

# every step over the whole tree, ignoring what this branch touched
test-full *args:
    {{PYTHON}} scripts/verify.py --full {{args}}

# tier 1 — inner loop: pre-commit + pytest, fast band only, quiet by default
test-quick *args:
    PYTEST_ADDOPTS="-m 'not slow and not medium'" {{PYTHON}} scripts/verify.py --quiet --only pre-commit,pytest {{args}}

# tier 2 — before a commit: everything but the long tail
test-mid *args:
    PYTEST_ADDOPTS="-m 'not slow'" {{PYTHON}} scripts/verify.py --only pytest {{args}}

# granular targets — each maps to one STEPS entry in scripts/verify.py (see verify.py --list)
# add --quiet to any of these for terse output (e.g. just test-py --quiet)
#
# these pass --only, so each runs its step in full — including the `slow`
# tests a default `just test` leaves to CI.  Prefix PYTEST_ADDOPTS="-m 'not
# slow'" to skip those.

test-py *args:
    {{PYTHON}} scripts/verify.py --only pytest {{args}}

test-line *args:
    {{PYTHON}} scripts/verify.py --only "Line interpreter suites" {{args}}

# lint + duplicate-code + bandit + dead definitions
test-lint *args:
    {{PYTHON}} scripts/verify.py --only pre-commit,"duplicate-code check (pylint)",bandit,"dead definitions" {{args}}

# security scan only
test-bandit *args:
    {{PYTHON}} scripts/verify.py --only bandit {{args}}

# mutation-test one interpreter: what its tests would NOT have caught
# (not part of `just test` -- it is a few minutes per language)
# `language` is quoted below: twelve of the sixty-five display names contain
# a space ("Point Break", "A Painter Ant", "Minsky Swap", ...), and unquoted
# they split into two arguments -- `just mutate "Point Break"` failed with
# `unrecognized arguments: Break`, for every one of the twelve.
mutate language *args:
    {{PYTHON}} scripts/mutate.py interpreter "{{language}}" {{args}}

# the same for one generator, named family/module after where it lives under
# src/esolangs/tools (e.g. just mutate-gen boolean/register).  A bare name
# works where only one family defines it; the families no longer share a
# module name, so in practice every bare name resolves.  Every suite in
# tests/tools runs; slow tests are deselected unless --slow is passed, since
# a mutation run pays the suite's cost once per mutant.
#
# The `core` family is the package root -- `just mutate-gen core/tui`,
# `core/vm`, `core/debug`, `core/cli`.  Those are the modules mutate_one
# cannot reach: it mutates a dependency-closed bundle, and they sit at the
# top of the stack rather than at a leaf.
mutate-gen module *args:
    {{PYTHON}} scripts/mutate.py generator {{module}} {{args}}

# The ledger obligations under tests/proofs are collected by pytest and gate
# every push. The proofs under deep/ are not, and the runner selects them by
# the band each one declares rather than by a list kept here: `verify` is what
# scripts/verify.py runs, `ci` what the workflow runs, `all` everything. ~2m20s,
# dominated by A Painter Ant at 1m20s, then linearity at 30s and Container at
# 16s. The runner keeps going after a failure and reports at the end, so
# linearity's standing Forþ finding does not hide the proofs after it.
# Use `python -m tests.proofs.deep --list` to see the bands.
# run every executable proof: the ledger obligations and all 7 deep proofs
proofs:
    {{PYTHON}} -m pytest tests/proofs -q
    {{PYTHON}} -m tests.proofs.deep all

# Not in `just test` or CI: what it guards moves only when APA's head, body,
# or routing does, so run it then. L2's foreign-leaf sweep at n=9 is 57s of
# the cost; the table enumeration is cheap.
# re-check the A Painter Ant uniform-in-n proof (15s, single-threaded)
apa-proof:
    {{PYTHON}} tests/proofs/deep/a_painter_ant.py

# clean generated: `find -delete` refuses a non-empty directory, so removal
# goes through `rm -rf`: bytecode, build metadata, verifier reports, and
# bytecode-only husk dirs (tools/boolean/, tools/text/, interpreters/line/,
# tests/compilers/).
clean:
    #!/usr/bin/env bash
    find . -path ./.venv -prune -o \( -name "__pycache__" -o -name "*.egg-info" \) -type d -print0 \
        | xargs -0 rm -rf
    find . -path ./.venv -prune -o -name "*.pyc" -type f -delete
    rm -rf build dist .coverage coverage.xml bandit-report.json .mypy_cache .ruff_cache .pytest_cache
    find src tests -mindepth 1 -type d -empty -delete
