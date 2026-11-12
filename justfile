# Task runner for the project

# Keep uv's cache inside the checkout by default.  Sandboxed worktrees cannot
# necessarily write ~/.cache, and a documented `just test-quick` should not
# need permission outside the repository.  An explicit UV_CACHE_DIR still wins.
export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", justfile_directory() + "/.cache/uv")

# Byte-compile dependencies when uv creates the venv.  A fresh worktree's venv
# avoids charging first-import compilation to a fast-band test.
# On an existing venv, skip the repeated bytecode scan.
export UV_COMPILE_BYTECODE := env_var_or_default("UV_COMPILE_BYTECODE", if path_exists(justfile_directory() + "/.venv") == "true" { "0" } else { "1" })

PYTHON := "uv run python"

# show the first-contribution workflow and all commands
[group('start')]
help:
    @echo "Start here:"
    @echo "  just install-dev  Install dependencies and enable the pre-push gate"
    @echo "  just test-quick   Fast feedback while editing"
    @echo "  just test-mid     Fast + medium tests"
    @echo "  just test         Required checks before committing (branch-scoped)"
    @echo "  just test-full    Whole-tree checks, including slow tests, before release"
    @echo ""
    @echo 'New language: just new-language "Name" --category <one it lists>'
    @echo 'Then: just check-language "Name" and just bounds "Name";'
    @echo 'when ready: just finish-language "Name"'
    @echo "Guide: docs/CONTRIBUTING.md; what each script does: scripts/README.md"
    @echo "Slow tests also run in CI; weekly probes run in the weekly workflow."
    @echo ""
    @just --list --unsorted

# install tooling
[group('start')]
install-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    uv sync --group dev --compile-bytecode
    # Enable the pre-push gate (scripts/verify/gate.py) so every push runs the
    # local check: lint, types, and pytest.
    git config core.hooksPath .githooks

# Scoped to the files this branch touched; widens to everything when the diff
# is unreadable or shared machinery moved.  Use `just test-full` to force the
# whole tree.  Pass --quiet to suppress successful step output.
[group('test')]
[doc('required checks before a commit: lint, types, pytest (branch-scoped)')]
[no-exit-message]
[positional-arguments]
test *args:
    {{PYTHON}} scripts/verify/gate.py "$@"

# local checks over the whole tree, including slow tests
[group('test')]
[no-exit-message]
[positional-arguments]
test-full *args:
    {{PYTHON}} scripts/verify/gate.py --full "$@"

# inner loop: pre-commit + pytest, fast band only, quiet by default.
# Four workers, the pytest config's default: this box also runs sessions in
# parallel, and at eight workers the subprocess-heavy fast tests starve past
# the band's starved wall ceiling (3.5-4.1s vs the 3s limit) and fail
# spuriously.  Measured here: eight failed at load 35, four passed at 36, for
# about 6s more wall.
[group('test')]
[doc('inner loop: pre-commit + fast pytest band, quiet')]
[no-exit-message]
[positional-arguments]
test-quick *args:
    VERIFY_PYTEST_MARKS="not slow and not medium and not weekly" {{PYTHON}} scripts/verify/gate.py --quiet --skip "mypy (src + scripts)" "$@"

# pytest fast and medium bands only; use just test before a commit
[group('test')]
[no-exit-message]
[positional-arguments]
test-mid *args:
    PYTEST_ADDOPTS="-m 'not slow and not weekly'" {{PYTHON}} scripts/verify/gate.py --only pytest "$@"

# controlled performance checks: one worker, no coverage, unchanged band limits
[group('test')]
[no-exit-message]
[positional-arguments]
test-costs *args:
    {{PYTHON}} -m pytest -q -n 0 -m "not slow and not weekly" --check-cost-bands -p scripts.ci.shard --duration-output notes/benchmarks/test-costs.json "$@"

# granular targets — each maps to one STEPS entry in scripts/verify/gate.py (see gate.py --list)
# add --quiet to any of these for terse output (e.g. just test-py --quiet)
#
# these pass --only, so each runs its step in full — including the `slow`
# tests a default `just test` leaves to CI.  Prefix PYTEST_ADDOPTS="-m 'not
# slow'" to skip those.

# pytest only, in full -- including the `slow` band
[group('test')]
[no-exit-message]
[positional-arguments]
test-py *args:
    {{PYTHON}} scripts/verify/gate.py --only pytest "$@"

# named tests or node ids, serial, any band (`-p no:xdist` breaks addopts' -n)
[group('test')]
[no-exit-message]
[positional-arguments]
test-one +nodes:
    {{PYTHON}} -m pytest -q -n 0 -m "" "$@"

# create interpreter, generator and test stubs; requires --category
[group('languages')]
[no-exit-message]
[positional-arguments]
new-language name *args:
    {{PYTHON}} scripts/new_language.py start "$@"

# list every integration step a language still lacks
[group('languages')]
[no-exit-message]
[positional-arguments]
check-language name:
    {{PYTHON}} scripts/new_language.py check "$@"

# regenerate examples, docs and size baselines, then run the full gate
[group('languages')]
[no-exit-message]
[positional-arguments]
finish-language name:
    {{PYTHON}} scripts/new_language.py finish "$@"

# measured worst steps and bits per arity, with witnesses
[group('languages')]
[no-exit-message]
[positional-arguments]
bounds name *args:
    {{PYTHON}} scripts/new_language.py bounds "$@"

# regenerate the generated README and docs sections
[group('languages')]
[no-exit-message]
docs:
    {{PYTHON}} scripts/docs/generate.py anchors
    {{PYTHON}} scripts/docs/generate.py docs

# regenerate the committed example programs; pass a set name to limit it
[group('languages')]
[no-exit-message]
[positional-arguments]
examples *args:
    {{PYTHON}} scripts/docs/generate.py examples "$@"

# measure one generated program: size, commands, answers (--json for all of it)
[group('evidence')]
[no-exit-message]
[positional-arguments]
benchmark language table *args:
    {{PYTHON}} scripts/benchmark.py "$@"

# Every language on 2-, 3- and 4-input tables, compared exactly against the
# [generator_sizes] section of each package's language.toml.  Pass --update
# to re-record a change so the diff carries it.  Also checked in CI.
# check emitted sizes and step counts against the committed baseline
[group('evidence')]
[no-exit-message]
[positional-arguments]
sizes *args:
    {{PYTHON}} checks/check_generator_sizes.py "$@"

# A refactor's evidence: step traces against a git revision (default main)
# over samples, wiki examples, generated rows and random programs.  Pass
# --mutant <file> as the positive control, --ignore-views for renamed views,
# --speed to fail a copy more than 10% slower.
# diff an interpreter's step-by-step behaviour against another revision
[group('evidence')]
[no-exit-message]
[positional-arguments]
tracediff language *args:
    {{PYTHON}} scripts/tracediff.py "$@"

# A generator refactor's evidence: every table through n=3, at several widths
# and balanced, byte-identical to a git revision (default main).  Pass
# --mutant <file> as the positive control, --speed to fail a tree more than
# 10% slower.
# diff a generator's programs against another revision
[group('evidence')]
[no-exit-message]
[positional-arguments]
gendiff language *args:
    {{PYTHON}} scripts/gendiff.py "$@"

# generator code no test reaches, vs scripts/baselines/deadcode_known.toml; languages narrow it
[group('maintenance')]
[no-exit-message]
[positional-arguments]
deadcode *args:
    {{PYTHON}} scripts/deadcode.py "$@"

# seeded generator mutants against their tests (sweep in a worktree)
[group('maintenance')]
[no-exit-message]
[positional-arguments]
mutants *args:
    {{PYTHON}} scripts/mutants.py "$@"

# Merge downloaded artifacts, one complete CI run per directory.
[group('maintenance')]
[doc('merge downloaded CI timing artifacts, one run per directory')]
[no-exit-message]
[positional-arguments]
refresh-ci-timings *args:
    {{PYTHON}} scripts/ci/shard.py refresh "$@"

# `python -m tests.proofs.deep --list` shows which proofs CI and verify run.
# run every executable proof: the ledger obligations and the deep proofs
[group('evidence')]
proofs:
    {{PYTHON}} -m pytest tests/proofs -q
    {{PYTHON}} -m tests.proofs.deep all
