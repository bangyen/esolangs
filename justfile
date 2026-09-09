# Task runner for the project

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# Tool paths
HOMEBREW_BIN := "/opt/homebrew/bin"
LLVM_BIN := `command -v brew >/dev/null 2>&1 && echo "$(brew --prefix llvm)/bin" || echo ""`

# Help
help:
    @echo "Available targets:"
    @echo "  lint-python  - Lint Python files with Ruff and MyPy"
    @echo "  lint         - Run all linting targets"
    @echo "  test         - Local check, scoped to this branch; slow tests left to CI"
    @echo "  test-full    - Every check, whole tree"
    @echo "  test-quick   - Fast dev loop: pre-commit + pytest (skip slow) (~6s pytest)"
    @echo "  test-py      - pytest only (~16s, 3325 tests, -n auto; skip slow with -m 'not slow')"
    @echo "  test-line    - extra/line suites with pytest only (~3s)"
    @echo "  test-anchor  - ztoalc anchor table check (~3.2s)"
    @echo "  mutate LANG  - mutation-test one interpreter (e.g. just mutate Qoibl)"
    @echo "  mutate-gen MOD - mutation-test one generator (e.g. just mutate-gen text/streetcode)"
    @echo "  install-dev  - Install development dependencies"
    @echo "  clean        - Clean up generated files"
    @echo ""
    @echo "  Use 'just test-quick' for inner loop, 'just test-full' before a release."

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

# fast dev loop: pre-commit + pytest (skip slow) — quiet by default
test-quick *args:
    PYTEST_ADDOPTS="-m 'not slow'" {{PYTHON}} scripts/verify.py --quiet --only pre-commit,pytest {{args}}

# granular targets — each maps to one STEPS entry in scripts/verify.py (see verify.py --list)
# add --quiet to any of these for terse output (e.g. just test-py --quiet)
#
# these pass --only, so each runs its step in full — including the `slow`
# tests a default `just test` leaves to CI.  Prefix PYTEST_ADDOPTS="-m 'not
# slow'" to skip those.

test-py *args:
    {{PYTHON}} scripts/verify.py --only pytest {{args}}

test-line *args:
    {{PYTHON}} scripts/verify.py --only "extra/line suites (uv)" {{args}}

test-anchor *args:
    {{PYTHON}} scripts/verify.py --only "ztoalc anchor table is reproducible" {{args}}

test-lint *args:
    {{PYTHON}} scripts/verify.py --only pre-commit,"docstring check","duplicate-code check (pylint)",bandit {{args}}

test-bandit *args:
    {{PYTHON}} scripts/verify.py --only bandit {{args}}

test-docstring *args:
    {{PYTHON}} scripts/verify.py --only "docstring check" {{args}}

# mutation-test one interpreter: what its tests would NOT have caught
# (not part of `just test` -- it is a few minutes per language)
# `language` is quoted below: twelve of the sixty-nine display names contain
# a space ("Point Break", "A Painter Ant", "Minsky Swap", ...), and unquoted
# they split into two arguments -- `just mutate "Point Break"` failed with
# `unrecognized arguments: Break`, for every one of the twelve.
mutate language *args:
    {{PYTHON}} scripts/mutate_one.py "{{language}}" {{args}}

# the same for one generator, named family/module after where it lives under
# src/esolangs/tools (e.g. just mutate-gen boolean/register, just mutate-gen
# text/streetcode).  A bare name works where only one family defines it, but
# eight -- helpers, laserfuck, other, register, stack, streetcode,
# super_snusp, tape -- exist in both and are refused unqualified.  Every
# suite in tests/tools runs; slow tests are deselected unless --slow is
# passed, since a mutation run pays the suite's cost once per mutant.
mutate-gen module *args:
    {{PYTHON}} scripts/mutate_generator.py {{module}} {{args}}

# clean generated
clean:
    #!/usr/bin/env bash
    find . \( -name "*.pyc" -o -name "__pycache__" -o -name "*.egg-info" -o -name "*.o" -o -name "*.so" -o -name "*.dylib" -o -name "*.exe" \) -delete 2>/dev/null || true
