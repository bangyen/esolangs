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
    @echo "  lint-lean    - Lint Lean files with lean linter"
    @echo "  lint         - Run all linting targets"
    @echo "  test         - Local check, scoped to this branch; slow/differential left to CI"
    @echo "  test-full    - Every check incl. the differential, whole tree"
    @echo "  test-quick   - Fast dev loop: pre-commit + pytest (skip slow) (~6s pytest)"
    @echo "  test-py      - pytest only (~16s, 3325 tests, -n auto; skip slow with -m 'not slow')"
    @echo "  test-differential - interpreter vs native differential corpora (~51s)"
    @echo "  test-unicorn - RISC-V assembly under unicorn (~10s)"
    @echo "  test-line    - extra/line suites via uv, incl. slow (~13s)"
    @echo "  test-anchor  - ztoalc anchor table check (~3.2s)"
    @echo "  mutate LANG  - mutation-test one interpreter (e.g. just mutate Qoibl)"
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

# Lint helpers.  Each target fails loudly when its tool is present and the
# code is unclean, and skips cleanly (exit 0) when the tool is missing, so a
# local `just lint` degrades gracefully without silently swallowing failures.

# lint lean
lint-lean:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v lake >/dev/null 2>&1; then
        (cd extra/lean/esolangs && lake build)
    else
        echo "skip: lake (Lean 4) not found"
    fi

# lint all code
lint: lint-python lint-lean
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

# fast dev loop: pre-commit + pytest (skip slow) (skips 32s differential + 10s unicorn) — quiet by default
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

test-unicorn *args:
    {{PYTHON}} scripts/verify.py --only "RISC-V assembly under unicorn (compilers + cross-checks)" {{args}}

test-differential *args:
    {{PYTHON}} scripts/verify.py --only "interpreter vs native differential corpora" {{args}}

test-lint *args:
    {{PYTHON}} scripts/verify.py --only pre-commit,"docstring check","duplicate-code check (pylint)",bandit {{args}}

test-bandit *args:
    {{PYTHON}} scripts/verify.py --only bandit {{args}}

test-docstring *args:
    {{PYTHON}} scripts/verify.py --only "docstring check" {{args}}

# mutation-test one interpreter: what its tests would NOT have caught
# (not part of `just test` -- it is a few minutes per language)
mutate language *args:
    {{PYTHON}} scripts/mutate_one.py {{language}} {{args}}

# clean generated
clean:
    #!/usr/bin/env bash
    find . \( -name "*.pyc" -o -name "__pycache__" -o -name "*.egg-info" -o -name "*.o" -o -name "*.so" -o -name "*.dylib" -o -name "*.exe" \) -delete 2>/dev/null || true
