# Task runner for the project

# Keep uv's cache inside the checkout by default.  Sandboxed worktrees cannot
# necessarily write ~/.cache, and a documented `just test-quick` should not
# need permission outside the repository.  An explicit UV_CACHE_DIR still wins.
export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", justfile_directory() + "/.cache/uv")

# Keep Pylint's statistics writable in sandboxed worktrees too.
export PYLINTHOME := env_var_or_default("PYLINTHOME", justfile_directory() + "/.cache/pylint")

# Byte-compile dependencies when uv creates the venv.  A fresh worktree's venv
# otherwise compiles sympy on first import -- ~1.3 s of CPU charged to
# whichever 1 s fast-band test touches it first, which then failed once per
# worktree.  Only then: on an existing venv it re-checks all 3276 files and
# prints a line on every `uv run` (0.06 s -> 0.22 s).
export UV_COMPILE_BYTECODE := env_var_or_default("UV_COMPILE_BYTECODE", if path_exists(justfile_directory() + "/.venv") == "true" { "0" } else { "1" })

# Auto-detect uv - falls back to plain python if not available
PYTHON := `command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python"`

# show the first-contribution workflow and all commands
[group('start')]
help:
    @echo "Start here:"
    @echo "  just install-dev  Install dependencies and enable the pre-push gate"
    @echo "  just doctor       Diagnose the setup (python scripts/doctor.py without just)"
    @echo "  just test-quick   Fast feedback while editing"
    @echo "  just test-mid     Fast + medium tests"
    @echo "  just test         Required checks before committing (branch-scoped)"
    @echo "  just test-full    Whole-tree checks, including slow tests, before release"
    @echo "  just test-full-parallel  The same gate on every core (idle machine only)"
    @echo ""
    @echo 'New language: just new-language "Name" --category <one it lists>'
    @echo 'Then: just check-language "Name" and just bounds "Name";'
    @echo 'when ready: just finish-language "Name"'
    @echo "Guide: docs/CONTRIBUTING.md; what each script does: scripts/README.md"
    @echo "Slow tests also run in CI; weekly probes run in the weekly workflow."
    @echo ""
    @just --list --unsorted

# check just, uv, dev dependencies and the pre-push hook; print each fix
[group('start')]
[no-exit-message]
doctor:
    {{PYTHON}} scripts/doctor.py

# install tooling
[group('start')]
install-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v uv >/dev/null 2>&1; then
        echo "Using uv..."
        uv sync --group dev --compile-bytecode
    else
        echo "Using pip..."
        # `--group` (PEP 735 dependency groups) needs pip 25.1.
        python -m pip install -U pip
        pip install -e . --group dev
    fi
    # Enable the pre-push gate (scripts/verify/gate.py) so every push runs the
    # local check: lint, types, and pytest.
    git config core.hooksPath .githooks
    {{PYTHON}} scripts/doctor.py

# Scoped to the files this branch touched; widens to everything when the diff
# is unreadable or shared machinery moved.  Use `just test-full` to force the
# whole tree.  Pass --quiet to suppress successful step output.
[group('test')]
[doc('required checks before a commit: lint, types, pytest (branch-scoped)')]
[no-exit-message]
test *args:
    {{PYTHON}} scripts/verify/gate.py {{args}}

# local checks over the whole tree, including slow tests
[group('test')]
[no-exit-message]
test-full *args:
    {{PYTHON}} scripts/verify/gate.py --full {{args}}

# The release gate is deliberate, not the inner loop, so it may take the box:
# on a quiet machine the committed measurement (pyproject.toml's worker note)
# is 85.6s at `-n auto` against 126.9s at four.  Not the default because >4
# workers starve the fast band's subprocess tests past their starved ceiling
# when the box is also loaded -- see the test-quick note.
[group('test')]
[doc('test-full on every core; idle machine only')]
[no-exit-message]
test-full-parallel *args:
    PYTEST_ADDOPTS="-n auto" {{PYTHON}} scripts/verify/gate.py --full {{args}}

# inner loop: pre-commit + pytest, fast band only, quiet by default.
# Four workers, the pytest config's default: this box also runs sessions in
# parallel, and at eight workers the subprocess-heavy fast tests starve past
# the band's starved wall ceiling (3.5-4.1s vs the 3s limit) and fail
# spuriously.  Measured here: eight failed at load 35, four passed at 36, for
# about 6s more wall.
[group('test')]
[doc('inner loop: pre-commit + fast pytest band, quiet')]
[no-exit-message]
test-quick *args:
    PYTEST_ADDOPTS="-m 'not slow and not medium and not weekly'" {{PYTHON}} scripts/verify/gate.py --quiet --only pre-commit,pytest {{args}}

# pytest fast and medium bands only; use just test before a commit
[group('test')]
[no-exit-message]
test-mid *args:
    PYTEST_ADDOPTS="-m 'not slow and not weekly'" {{PYTHON}} scripts/verify/gate.py --only pytest {{args}}

# granular targets — each maps to one STEPS entry in scripts/verify/gate.py (see gate.py --list)
# add --quiet to any of these for terse output (e.g. just test-py --quiet)
#
# these pass --only, so each runs its step in full — including the `slow`
# tests a default `just test` leaves to CI.  Prefix PYTEST_ADDOPTS="-m 'not
# slow'" to skip those.

# pytest only, in full -- including the `slow` band
[group('test')]
[no-exit-message]
test-py *args:
    {{PYTHON}} scripts/verify/gate.py --only pytest {{args}}

# named tests or node ids, serial, any band (`-p no:xdist` breaks addopts' -n)
[group('test')]
[no-exit-message]
[positional-arguments]
test-one +nodes:
    {{PYTHON}} -m pytest -q -n 0 -m "" "$@"

# lint + duplicate-code + dead definitions
[group('test')]
[no-exit-message]
test-lint *args:
    {{PYTHON}} scripts/verify/gate.py --only pre-commit,"duplicate-code check (pylint)","dead definitions" {{args}}

# CI's changed-line coverage gate (--partial --strict), reading the
# .coverage a `pytest --cov --cov-branch` run left behind
[group('test')]
[doc("CI's changed-line coverage gate, over an existing .coverage")]
[no-exit-message]
test-diff-coverage *args:
    {{PYTHON}} scripts/verify/gate.py --only "diff coverage" {{args}}

# create interpreter, generator and test stubs; asks the category unless --category
[group('languages')]
[no-exit-message]
new-language name *args:
    {{PYTHON}} scripts/new_language.py start "{{name}}" {{args}}

# list every integration step a language still lacks
[group('languages')]
[no-exit-message]
check-language name:
    {{PYTHON}} scripts/new_language.py check "{{name}}"

# regenerate examples, docs and size baselines, then run the full gate
[group('languages')]
[no-exit-message]
finish-language name:
    {{PYTHON}} scripts/new_language.py finish "{{name}}"

# worst steps and bits per arity, and a [proof_status] section to paste
[group('languages')]
[no-exit-message]
bounds name *args:
    {{PYTHON}} scripts/new_language.py bounds "{{name}}" {{args}}

# delete a language everywhere check looks, then list prose mentions left
[group('languages')]
[no-exit-message]
remove-language name:
    {{PYTHON}} scripts/new_language.py remove "{{name}}"

# regenerate the generated README and docs sections
[group('languages')]
[no-exit-message]
docs:
    {{PYTHON}} scripts/docs/generate.py docs

# regenerate the committed example programs; pass a set name to limit it
[group('languages')]
[no-exit-message]
examples *args:
    {{PYTHON}} scripts/docs/generate.py examples {{args}}

# measure one generated program: size, commands, answers (--json for all of it)
[group('evidence')]
[no-exit-message]
benchmark language table *args:
    {{PYTHON}} scripts/benchmark.py "{{language}}" "{{table}}" {{args}}

# Every language on 2-, 3- and 4-input tables, compared exactly against the
# [generator_sizes] section of each package's language.toml.  Pass --update
# to re-record a change so the diff carries it.  Also checked in CI.
# check emitted sizes and step counts against the committed baseline
[group('evidence')]
[no-exit-message]
sizes *args:
    {{PYTHON}} checks/check_generator_sizes.py {{args}}

# A refactor's evidence: step traces against a git revision (default main)
# over samples, wiki examples, generated rows and random programs.  Pass
# --mutant <file> as the positive control, --ignore-views for renamed views,
# --speed to fail a copy more than 10% slower.
# diff an interpreter's step-by-step behaviour against another revision
[group('evidence')]
[no-exit-message]
tracediff language *args:
    {{PYTHON}} scripts/tracediff.py "{{language}}" {{args}}

# A generator refactor's evidence: every table through n=3, at several widths
# and balanced, byte-identical to a git revision (default main).  Pass
# --mutant <file> as the positive control, --speed to fail a tree more than
# 10% slower.
# diff a generator's programs against another revision
[group('evidence')]
[no-exit-message]
gendiff language *args:
    {{PYTHON}} scripts/gendiff.py "{{language}}" {{args}}

# generator code no test reaches, vs scripts/baselines/deadcode_known.toml; languages narrow it
[group('maintenance')]
[no-exit-message]
deadcode *args:
    {{PYTHON}} scripts/deadcode.py {{args}}

# generator Decisions: figures, ranked by package commits since each was written
[group('maintenance')]
[no-exit-message]
stale-figures *args:
    {{PYTHON}} scripts/stale_figures.py {{args}}

# seeded generator mutants against their tests (sweep in a worktree)
[group('maintenance')]
[no-exit-message]
mutants *args:
    {{PYTHON}} scripts/mutants.py {{args}}

# Merge downloaded artifacts, one complete CI run per directory.
[group('maintenance')]
[doc('merge downloaded CI timing artifacts, one run per directory')]
[no-exit-message]
refresh-ci-timings *args:
    {{PYTHON}} scripts/ci/shard.py refresh {{args}}

# `python -m tests.proofs.deep --list` shows which proofs CI and verify run.
# run every executable proof: the ledger obligations and the deep proofs
[group('evidence')]
proofs:
    {{PYTHON}} -m pytest tests/proofs -q
    {{PYTHON}} -m tests.proofs.deep all

# clean generated files
[group('maintenance')]
clean:
    #!/usr/bin/env bash
    find . \( -path ./.venv -o -path ./.claude \) -prune -o \( -name "__pycache__" -o -name "*.egg-info" \) -type d -print0 \
        | xargs -0 rm -rf
    find . \( -path ./.venv -o -path ./.claude \) -prune -o -name "*.pyc" -type f -delete
    rm -rf build dist .coverage coverage.xml .mypy_cache .ruff_cache .pytest_cache
    find src tests -mindepth 1 -type d -empty -delete
