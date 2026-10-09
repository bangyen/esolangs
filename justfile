# Task runner for the project

# Keep uv's cache inside the checkout by default.  Sandboxed worktrees cannot
# necessarily write ~/.cache, and a documented `just test-quick` should not
# need permission outside the repository.  An explicit UV_CACHE_DIR still wins.
export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", justfile_directory() + "/.cache/uv")

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# show the first-contribution workflow and all commands
help:
    @echo "Start here:"
    @echo "  just install-dev  Install dependencies and enable the pre-push gate"
    @echo "  just test-quick   Fast feedback while editing"
    @echo "  just test-mid     Fast + medium tests"
    @echo "  just test         Required checks before committing (branch-scoped)"
    @echo "  just test-full    Whole-tree checks, including slow tests, before release"
    @echo ""
    @echo 'New language: just new-language "Name" --category tape_based'
    @echo 'Then: just check-language "Name"; when ready: just finish-language "Name"'
    @echo "Guide: docs/CONTRIBUTING.md"
    @echo "Slow tests also run in CI; weekly probes run in the weekly workflow."
    @echo ""
    @just --list

# install tooling
install-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv >/dev/null 2>&1; then
        echo "Using uv..."
        uv sync --group dev
    else
        echo "Using pip..."
        # `--group` (PEP 735 dependency groups) needs pip 25.1.
        python -m pip install -U pip
        pip install -e . --group dev
    fi
    # Enable the pre-push gate (scripts/verify.py) so every push runs the
    # full local check: lint, pytest, bandit, and the verify scripts.
    git config core.hooksPath .githooks

# The formatter is ruff-format, run via pre-commit (and so via `just test`);
# `ruff check` here catches lint that formatting does not.
# lint python
lint-python:
    {{PYTHON}} -m ruff check .
    {{PYTHON}} -m ruff format --check .
    {{PYTHON}} -m mypy

# lint all code
lint: lint-python
    @echo "All lint checks completed!"

# Scoped to the files this branch touched; widens to everything when the diff
# is unreadable or shared machinery moved.  Use `just test-full` to force the
# whole tree.  Pass --quiet to suppress successful step output.
# test (local check: lint, pytest, bandit, verify scripts)
test *args:
    {{PYTHON}} scripts/verify.py {{args}}

# every step over the whole tree, ignoring what this branch touched
test-full *args:
    {{PYTHON}} scripts/verify.py --full {{args}}

# inner loop: pre-commit + pytest, fast band only, quiet by default
test-quick *args:
    PYTEST_ADDOPTS="-m 'not slow and not medium and not weekly' -n 8" {{PYTHON}} scripts/verify.py --quiet --only pre-commit,pytest {{args}}

# pytest fast and medium bands only; use just test before a commit
test-mid *args:
    PYTEST_ADDOPTS="-m 'not slow and not weekly'" {{PYTHON}} scripts/verify.py --only pytest {{args}}

# granular targets — each maps to one STEPS entry in scripts/verify.py (see verify.py --list)
# add --quiet to any of these for terse output (e.g. just test-py --quiet)
#
# these pass --only, so each runs its step in full — including the `slow`
# tests a default `just test` leaves to CI.  Prefix PYTEST_ADDOPTS="-m 'not
# slow'" to skip those.

# pytest only, in full -- including the `slow` band
test-py *args:
    {{PYTHON}} scripts/verify.py --only pytest {{args}}

# lint + duplicate-code + bandit + dead definitions
test-lint *args:
    {{PYTHON}} scripts/verify.py --only pre-commit,"duplicate-code check (pylint)",bandit,"dead definitions" {{args}}

# security scan only
test-bandit *args:
    {{PYTHON}} scripts/verify.py --only bandit {{args}}

# emit repeatable generator size/time/command evidence as JSON
benchmark language table *args:
    {{PYTHON}} scripts/benchmark.py "{{language}}" "{{table}}" {{args}}

# Every language on 2-, 3- and 4-input tables, compared exactly against
# tests/fixtures/generator_sizes.json.  Pass --update to re-record a change
# so the diff carries it.  Also a `just test` step ("generator size baseline").
# check emitted sizes and step counts against the committed baseline
sizes *args:
    {{PYTHON}} scripts/check_generator_sizes.py {{args}}

# Merge downloaded artifacts, one complete CI run per directory.
refresh-ci-timings *args:
    {{PYTHON}} scripts/refresh_ci_timings.py --serial-node tests/proofs/test_brainfuck_preserving.py::test_preserving_certificate {{args}}

# create interpreter, generator and test stubs; pass e.g. --category tape_based
new-language name *args:
    {{PYTHON}} scripts/new_language.py start "{{name}}" {{args}}

# list every integration step a language still lacks
check-language name:
    {{PYTHON}} scripts/new_language.py check "{{name}}"

# regenerate examples, docs and size baselines, then run the full gate
finish-language name:
    {{PYTHON}} scripts/new_language.py finish "{{name}}"

# delete a language everywhere check looks, then list prose mentions left
remove-language name:
    {{PYTHON}} scripts/new_language.py remove "{{name}}"

# Not part of `just test`: a few minutes per language.
# `language` is quoted: display names like "A Painter Ant" contain spaces,
# and unquoted they split into two arguments.
# mutation-test one interpreter: what its tests would NOT have caught
mutate language *args:
    {{PYTHON}} scripts/mutate.py interpreter "{{language}}" {{args}}

# `module` is family/module, e.g. tools/register or core/vm; pass --slow to
# include slow tests.
# the same for one generator
mutate-gen module *args:
    {{PYTHON}} scripts/mutate.py generator {{module}} {{args}}

# `python -m tests.proofs.deep --list` shows which proofs CI and verify run.
# run every executable proof: the ledger obligations and the deep proofs
proofs:
    {{PYTHON}} -m pytest tests/proofs -q
    {{PYTHON}} -m tests.proofs.deep all

# compile the standalone complexity notes; PDFs are ignored generated files
proofs-pdf:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v tectonic >/dev/null 2>&1 || {
        echo "tectonic is required (brew install tectonic)" >&2
        exit 1
    }
    tectonic --outdir docs/proofs docs/proofs/polynomial.tex

# Not in `just test` or CI; run it when A Painter Ant's generator changes.
# re-check the A Painter Ant uniform-in-n proof
apa-proof:
    {{PYTHON}} tests/proofs/deep/a_painter_ant.py

# clean generated files
clean:
    #!/usr/bin/env bash
    find . \( -path ./.venv -o -path ./.worktrees \) -prune -o \( -name "__pycache__" -o -name "*.egg-info" \) -type d -print0 \
        | xargs -0 rm -rf
    find . \( -path ./.venv -o -path ./.worktrees \) -prune -o -name "*.pyc" -type f -delete
    rm -rf build dist .coverage coverage.xml bandit-report.json .mypy_cache .ruff_cache .pytest_cache
    find src tests -mindepth 1 -type d -empty -delete
