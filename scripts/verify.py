"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types) and pytest (the test suite)
2. bandit (via uv) and the ``tests/interpreters`` suites (via uv, which supplies the
   image libraries the package itself does not depend on)

``.githooks/pre-push`` and ``just test`` both run this script.

By default the run is *scoped*: each step declares the paths it guards (see
``STEP_SCOPE``), and a step whose paths this branch never touched is skipped,
because nothing the branch did could have broken it.  Two steps take a file
list instead, so they are narrowed rather than skipped -- pre-commit to the
changed files, and pytest to the matching test modules.

Scoping only ever subtracts work that provably could not have broken.  When
the branch's diff cannot be read, or it touches the shared interpreter
machinery or the verification tooling itself, the run widens back to
everything (see ``scripts/_scope.py``).  ``--full`` forces that too, and CI
still runs the complete suite on every push regardless.

A default run also leaves work to CI where CI already covers it: the steps in
``FULL_ONLY`` and the ``slow`` marker in both test suites -- pytest's (the
fuzzers' divergence-detection tests, which CI runs by that same marker and
errors on if they skip) and
tests/interpreters's (its two 5.2s render round trips, which CI's ``line`` job runs
unfiltered).  ``--full``, ``just test-full``, and an explicit ``--only`` all
still run them.

The steps do not all run one after another.  ``pytest`` is the longest, so it
is launched first and the one-core steps run while it goes; ``pre-commit``
runs to completion before anything else starts, because its fix hooks rewrite
the very files the other steps read; and the steps that are parallel in their
own right wait until pytest has joined, because beside it they were not
overlapping work but fighting it for cores.  That makes the timing table's
two totals differ: the sum is how much work ran, the wall is how long the
push waited.

Output is replayed only for the steps that failed.  A run of one step streams
it live instead (``--verbose`` forces that, ``--quiet`` forbids it).

Usage:
    python scripts/verify.py [--only STEPS] [--skip STEPS] [--full] [--list]
    python scripts/verify.py --full                       # every step, whole tree
    python scripts/verify.py --only pytest,bandit         # comma-separated STEPS names
    python scripts/verify.py --only pre-commit,pytest --skip bandit
"""

import argparse
import atexit
import functools
import os
import shutil
import subprocess
import sys
import tempfile
import time
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).parents[1]

# Git runs this hook with its stdout attached to a pipe, not the terminal, so
# Python block-buffers our own prints while the steps -- which inherit the
# same pipe and write to it directly -- stream straight through.  The result
# is that `scope:`, the `[skip]` lines and the `[....] pytest` banner arrive
# only when the run ends, after the very silence they exist to explain.  Line
# buffering puts them in front of the wait, where they belong.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


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

# Steps a default run leaves to CI.  These guard real bugs but cost more than
# they save at push time, and CI already runs them on every push.  They
# still run under --full, under an explicit --only, and via `just test-full`.
FULL_ONLY: frozenset[str] = frozenset()

# Named once: the step table, STEP_SCOPE and the slow-marker filter all refer
# to this step, and a typo in any of them would silently stop matching.
LINE_STEP = "Line interpreter suites"

# How often the long step reports that it is still going.  Short enough that
# the wait never looks stalled, long enough that a normal run prints only a
# handful of lines.
HEARTBEAT_SECONDS = 20.0

# Not a STEPS entry: it reads the coverage data file `pytest` writes, and
# `pytest` is LONG_STEP -- launched with Popen and left running while the
# short steps go by.  A sibling step would race it and read a half-written
# file, so the gate is run by _run_steps once the long step has exited.
DIFF_COVERAGE_STEP = "touched-file coverage"


def _line_addopts(env: dict[str, str]) -> str:
    """``PYTEST_ADDOPTS`` for the line step, deselecting the slow tests.

    Composed with whatever the caller already set rather than replacing it,
    so `PYTEST_ADDOPTS=-x just test` keeps its own flag.  A caller who has
    already chosen a `-m` expression is left alone: two `-m` flags would let
    the last one win, silently discarding theirs.

    Both spellings count as a choice -- pytest takes the marker attached
    (`-mslow`) as readily as separated (`-m slow`), and only the separated
    form survives a plain membership test.
    """
    existing = env.get("PYTEST_ADDOPTS", "")
    if any(word.startswith("-m") for word in existing.split()):
        return existing
    return f"{existing} -m 'not slow'".strip()


# Which paths each step actually guards.  A step whose prefixes the branch did
# not touch cannot have been broken by that branch, so a scoped run skips it.
# A step absent from this table is always run: it is either cheap enough not to
# matter or it guards the whole tree.  Prefixes are repo-relative.
STEP_SCOPE: dict[str, tuple[str, ...]] = {
    "bandit": ("src/",),
    LINE_STEP: ("tests/interpreters/",),
    "duplicate-code check (pylint)": ("src/esolangs/", "scripts/"),
    "dead definitions": ("src/", "scripts/"),
    # Only a generator, an interpreter (the step counts are executed), or the
    # baseline itself can move these numbers.
    "generator size baseline": (
        "src/esolangs/tools/",
        "src/esolangs/interpreters/",
        "scripts/check_generator_sizes.py",
        "scripts/benchmark.py",
        "tests/fixtures/generator_sizes.json",
    ),
    # The union of what the two proofs in this band read: ArrowQueue's lemmas
    # import the generator and nothing else, and BIO's also parse the emitted
    # program and instantiate it through the shipped fill.  The runner is in
    # the scope too, since it decides which of them run at all.
    "deep proofs (verify band)": (
        "src/esolangs/tools/parameterized.py",
        "src/esolangs/tools/examples.py",
        "tests/proofs/deep/",
    ),
    # Only an interpreter (or the sweep itself) can introduce a leak.
    "exception leaks": (
        "src/esolangs/interpreters/",
        "scripts/verify_no_exception_leaks.py",
    ),
}

STEPS = [
    (
        "generated docs",
        [*PY, "scripts/check_generated_docs.py"],
    ),
    ("pre-commit", [*PY, "-m", "pre_commit", "run", "--all-files"]),
    # The only mypy run.  pre-commit has no mypy hook: the mirror's isolated
    # env lacks the scripts' imports, so it could only ever cover src/, and
    # this run covers src/ and scripts/ both from the project env.
    ("mypy (src + scripts)", [*PY, "-m", "mypy"]),
    # `--cov-report=` writes no report: the run is here for the data file,
    # which the touched-file gate reads afterwards.
    #
    # Whole-package measurement is what a full run pays for: 13s over the
    # 27s the fast selection takes bare, measured on 3.14 at
    # 9861 tests (it read as free at half that suite).  A scoped run does
    # not pay it -- `_scoped_coverage` narrows the measurement to the
    # touched files, which is all the gate reads.
    #
    # `--cov-branch` costs 3.3x before 3.14, where sys.monitoring cannot
    # measure branches and coverage falls back to the old tracer.  An older
    # interpreter pays that silently rather than breaking, so if this ever
    # feels slow again check the interpreter before the tests: coverage says
    # so on stderr with a `no-sysmon` CoverageWarning.  Both timing tables
    # are in ``the verification history``.
    ("pytest", [*PY, "-m", "pytest", "-q", "--cov", "--cov-branch", "--cov-report="]),
    ("bandit", ["uv", "run", "--with", "bandit", "bandit", "-r", "src", "-q"]),
    # A generator route that was replaced keeps its own tests green, so it
    # never fails; three sat that way.  <1s.
    ("dead definitions", [*PY, "scripts/check_dead_definitions.py"]),
    # What every generator emits, and how many steps the emitted program
    # runs, pinned exactly against a committed baseline: the two quantities
    # the collection's claims rest on, and until this step nothing measured
    # them outside a hand-run `just benchmark`.  192 measurements, ~3s.
    ("generator size baseline", [*PY, "scripts/check_generator_sizes.py"]),
    (
        # These also run under the plain `pytest` step above.  Repeated here
        # under `--isolated --no-project`, which installs only pytest, so a
        # green run proves the subtree pulls in no third-party dependency.
        # The in-project run cannot show that.
        LINE_STEP,
        [
            *PY,
            "-m",
            "pytest",
            "tests/line/test_bf_to_line.py",
            "tests/line/test_line_boolean.py",
            "tests/line/test_mask.py",
            "tests/raster/test_png.py",
            "tests/line/test_simulate.py",
            "-q",
        ],
    ),
    (
        # pylint's R0801 reports similar blocks across files, catching
        # copy-pasted helpers like the bracket matcher or the OISC memory
        # tokenizer.  --ignore-imports keeps shared import blocks from
        # counting as duplication.  tests/ is left out: it doubled the line
        # count and quadrupled the file pairs the O(files^2) comparison
        # walks (53s -> 10s), and shared test scaffolding is not what the
        # check is for.  No -j: this runs in pytest's shadow, and the 2s
        # that workers save here they take back from its four.
        "duplicate-code check (pylint)",
        [
            *PY,
            "-m",
            "pylint",
            "--disable=all",
            "--enable=duplicate-code",
            "--min-similarity-lines=10",
            "--ignore-imports=yes",
            "src/esolangs",
            "scripts",
        ],
    ),
    # The deep proofs cheap enough to gate locally: ArrowQueue's twelve named
    # lemmas and BIO's telescoping lookup, each pinning finite facts their
    # total-over-every-arity proofs rest on.  2.2s together.  Which proofs
    # those are is not listed here -- each declares a band beside itself and
    # `tests/proofs/test_bands.py` holds the band to a 5s budget, so this step
    # cannot silently grow or shrink.  The registry-wide battery sits in the
    # `ci` band instead: it touches every generator, so scoping it here would
    # mean running its 12s on nearly every edit.
    (
        "deep proofs (verify band)",
        [*PY, "-m", "tests.proofs.deep", "verify"],
    ),
    # The contract exceptions.py states, executed: no interpreter may leak a
    # raw Python error to its caller.  Bare, it checks only the languages
    # this branch touched, which is why it is affordable here; CI runs
    # --all (59 languages, 68s).
    (
        "exception leaks",
        [*PY, "scripts/verify_no_exception_leaks.py"],
    ),
]


@functools.lru_cache(maxsize=1)
def _scope_changed_files() -> tuple[str, ...]:
    """Return this branch's changed paths, queried once per run."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _scope import changed_files

    return tuple(changed_files())


def _scope_plan(*, full: bool) -> tuple[set[str] | None, str]:
    """Return the step names to skip as unaffected, and why.

    ``None`` means "run everything".  That is the answer whenever the branch's
    diff cannot be read or something shared moved, so scoping can only ever
    remove work that provably could not have broken -- never work whose status
    is unknown.
    """
    if full:
        return None, "--full requested"
    if os.environ.get("VERIFY_FULL", "0") not in ("", "0"):
        return None, "VERIFY_FULL set"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _scope import widens_to_everything

    changed = list(_scope_changed_files())
    reason = widens_to_everything(changed)
    if reason is not None:
        return None, reason
    skip = {
        name
        for name, prefixes in STEP_SCOPE.items()
        if not any(f.startswith(prefixes) for f in changed)
    }
    return skip, f"{len(changed)} file(s) changed"


# What a scoped pytest run should do.  Spelled out rather than overloading
# ``None``: ``_scoped_cmd`` uses ``None`` to mean "skip this step", which is
# the *opposite* of WHOLE_SUITE, and one sentinel meaning both is a trap.
WHOLE_SUITE = "whole-suite"

# pyproject's ``python_files``.  Kept in step by a test, since a path this
# says is collectable but pytest does not would fail the run it is scoped to.
COLLECTED_PATTERNS = ("test_*.py", "*_test.py")


def _is_collected(path: str) -> bool:
    """Whether pytest would collect tests from *path*."""
    name = Path(path).name
    return any(fnmatch(name, pattern) for pattern in COLLECTED_PATTERNS)


def _pytest_scope(changed: list[str]) -> list[str] | str:
    """Return the pytest paths covering *changed*.

    An interpreter is covered by its own test module; anything touched under
    ``tests/`` is run directly.  ``WHOLE_SUITE`` means the coverage is not
    localisable -- a new interpreter with no test module yet, or a source file
    whose tests live somewhere this cannot predict -- so everything runs rather
    than guessing.  An empty list means the branch touched nothing the Python
    tests cover (docs, assembly, CI config), so there is nothing to run.
    """
    paths: set[str] = set()
    for f in changed:
        if f.startswith("tests/"):
            # A conftest configures every test beneath it, a non-.py file is
            # fixture data some unknown test reads, and a module pytest does
            # not collect is a helper imported from tests that live elsewhere.
            # Scoped to itself each collects nothing, which pytest exits
            # non-zero for, so all three widen.
            if Path(f).name == "conftest.py" or not _is_collected(f):
                return WHOLE_SUITE
            if (ROOT / f).exists():
                paths.add(f)
            continue
        if f.startswith("src/esolangs/interpreters/") and f.endswith(".py"):
            stem = Path(f).stem
            if stem.startswith("_"):
                return WHOLE_SUITE
            candidate = f"tests/interpreters/test_{stem}.py"
            if not (ROOT / candidate).exists():
                return WHOLE_SUITE
            paths.add(candidate)
            continue
        if f.startswith("src/"):
            return WHOLE_SUITE  # non-interpreter source: not localisable
        if f.startswith("scripts/") and f.endswith(".py"):
            # The scripts have unit tests (the bundler's, for one) that do not
            # follow the interpreter naming convention, so there is no way to
            # tell which module covers them.
            return WHOLE_SUITE
    return sorted(paths)


def _scoped_cmd(name: str, cmd: list[str], changed: list[str]) -> list[str] | None:
    """Narrow *cmd* to the branch's files, or ``None`` if it has nothing to do.

    Three steps take a file list rather than being all-or-nothing, so instead
    of skipping them wholesale they are re-aimed at what actually moved.
    """
    if name == "pre-commit":
        files = [f for f in changed if (ROOT / f).is_file()]
        if not files:
            return None
        return [c for c in cmd if c != "--all-files"] + ["--files", *files]
    if name == "pytest":
        paths = _pytest_scope(changed)
        if not paths:
            return None  # nothing the Python tests cover moved
        cmd = _scoped_coverage(cmd, changed)
        if paths == WHOLE_SUITE:
            return cmd  # not localisable: run every test
        return [*cmd, *paths]
    return cmd


def _scoped_coverage(cmd: list[str], changed: list[str]) -> list[str]:
    """Measure coverage over the touched source files only.

    The gate that reads the data judges just the ``src/esolangs`` files the
    branch touched, so measuring the whole package is overhead spent on files
    nothing will look at.  Whole-package ``--cov --cov-branch`` costs 13s on
    top of a 27s run; an ``include`` of the touched files costs nothing
    measurable, because sys.monitoring never instruments the rest.  A branch
    that touched no source file measures nothing at all -- the gate skips on
    its own, having no targets.

    coverage refuses ``include`` beside ``source`` (it warns and ignores the
    include), so this cannot be a pyproject default; the rc is written for
    the run and replaces the pyproject one for *measurement* only.  Reporting
    is untouched: the gate reads the data through ``coverage json``, which
    consults pyproject and so keeps ``exclude_lines``.
    """
    if "--cov" not in cmd:
        return cmd
    touched = [
        f for f in changed if f.startswith("src/esolangs/") and f.endswith(".py")
    ]
    without = [c for c in cmd if c not in ("--cov", "--cov-branch", "--cov-report=")]
    if not touched:
        return without
    fd, rc = tempfile.mkstemp(prefix="verify-coverage-", suffix=".rc")
    with os.fdopen(fd, "w") as f:
        f.write("[run]\ncore = sysmon\nbranch = True\ninclude =\n")
        f.writelines(f"    {path}\n" for path in touched)
    atexit.register(os.unlink, rc)
    return [*without, "--cov", f"--cov-config={rc}", "--cov-report="]


def _parse_only_skip() -> tuple[set[str] | None, set[str] | None, bool, bool, bool]:
    parser = argparse.ArgumentParser(description="Run the local verification stack")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="comma-separated subset of STEPS names to run (e.g. --only pytest,bandit)",
    )
    parser.add_argument(
        "--skip",
        type=str,
        default=None,
        help="comma-separated STEPS names to skip",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available STEPS names and exit",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress successful step output even for a single-step run",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="stream every step's output live instead of replaying failures",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="run every step over the whole tree instead of scoping the run "
        "to the files this branch touched",
    )
    args = parser.parse_args()
    if args.list:
        for name, _ in STEPS:
            print(name)
        sys.exit(0)
    only = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None
    skip = {s.strip() for s in args.skip.split(",") if s.strip()} if args.skip else None
    # A typo'd name used to filter STEPS down to nothing and print the same
    # "all local checks passed" a real green run prints -- a gate that ran
    # zero steps must never look like a gate that passed.
    known = {name for name, _ in STEPS}
    for flag, names in (("--only", only), ("--skip", skip)):
        unknown = sorted((names or set()) - known)
        if unknown:
            parser.error(
                f"{flag}: unknown step(s) {', '.join(unknown)}; "
                f"--list prints the {len(known)} names"
            )
    return only, skip, args.full, args.quiet, args.verbose


# The step that mutates the working tree.  pre-commit's ruff/ruff-format and
# whitespace hooks rewrite files in place, so anything that reads the tree has
# to wait for it -- running it alongside pytest would race the edit against
# the read.  The only such step: everything else only reads.
MUTATES_TREE = "pre-commit"

# The long pole.  The runner starts it first and fills its shadow with the
# cheap steps.
LONG_STEP = "pytest"

# Steps that are *themselves* parallel, so running them beside pytest does not
# overlap work -- it oversubscribes the machine and makes both slower.  The
# shadow is only free for steps that use one core.
#
# Measured on a 10-core laptop (8 performance), each alone against the same
# step inside the old all-at-once shadow: pytest 39.8s alone vs 137.3s,
# bandit 2.7s vs 11.2s, the line suites 2.6s vs 28.5s, the leak sweep
# (`--all`) 35.6s vs 85.4s scoped.  Nothing was slow; everything was
# contending.  So the heavy steps wait for pytest to finish and then get the
# machine to themselves.
LEAK_STEP = "exception leaks"
HEAVY_STEPS = frozenset({LEAK_STEP})

#: Workers for the leak sweep when *this* runner drives it.  The script's own
#: default is a deliberate 2, sized for a laptop doing other things; here the
#: heavy steps run alone with pytest already joined, which is the "cores to
#: spare" case its comment names.  6 is measured: 70.9s at 2, 35.6s at 6 over
#: `--all`, and past the 8 performance cores the curve turns back up (the
#: same shape pyproject records for xdist).  A caller who sets the variable
#: keeps their value.
LEAKSWEEP_JOBS = "6"


def _ensure_dev_deps() -> None:
    """Sync dev dependencies when the runner's Python lacks them.

    A fresh worktree venv has an interpreter but no third-party packages, so
    every step fails at 0.0s with ``No module named ...`` -- missing tooling,
    not broken code.  Syncing once here fixes it where the failure surfaces.
    ``VERIFY_NO_SYNC`` opts out (offline machines); without ``uv`` there is
    nothing to sync with, so the steps report it themselves.
    """
    if os.environ.get("VERIFY_NO_SYNC", "0") not in ("", "0"):
        return
    probe = subprocess.run(
        [*PY, "-c", "import pytest"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode == 0:
        return
    if shutil.which("uv") is None:
        return
    print("dev dependencies missing; running `uv sync --extra dev` ...")
    subprocess.run(["uv", "sync", "--extra", "dev"], cwd=ROOT, check=False)


def _should_stream(steps: int, *, quiet: bool, verbose: bool) -> bool:
    """Whether the steps write to the terminal directly rather than be replayed.

    A stack's worth of streamed output is a wall of text nobody reads: every
    pre-commit hook line, mypy's tally, uv's resolution, two suites' progress
    dots, all to say what the ``[ok]`` lines already say -- and the one thing
    worth reading, a failure, is buried in it.  So the default replays only
    the steps that failed, which is the whole of what a passing run has to
    say plus the whole of what a failing one does.

    A run of one step is the other case: `just test-py` is asking to watch
    pytest run.  Nothing else is writing to the terminal then, so the output
    cannot interleave with another step's into nonsense.
    """
    if verbose:
        return True
    return steps == 1 and not quiet


def _wait_with_heartbeat(
    proc: subprocess.Popen[str], name: str, start: float
) -> tuple[str, int]:
    """Collect *proc*'s output, saying every ``HEARTBEAT_SECONDS`` it is alive.

    Waiting in one blocking call left the push silent for the minutes the
    stack takes, which reads as a hang -- long enough to invite the Ctrl-C
    that skips the checks.  Waiting in slices costs nothing, and it is what
    lets the output be captured at all: a captured step prints nothing until
    it ends, so without this the silence would get worse, not better.
    """
    while True:
        try:
            output, _ = proc.communicate(timeout=HEARTBEAT_SECONDS)
            return output, proc.returncode
        except subprocess.TimeoutExpired:
            print(f"[....] {name} still running ({time.time() - start:.0f}s elapsed)")


def _report(name: str, elapsed: float, returncode: int, output: str | None) -> bool:
    """Print one step's result, its captured output on failure.  Return ok."""
    if returncode != 0 and output:
        print(output, end="")
    ok = returncode == 0
    print(f"[{'ok' if ok else 'FAIL'}] {name} ({elapsed:.1f}s)")
    return ok


def _run_steps(
    runnable: list[tuple[str, list[str], dict[str, str]]],
    *,
    stream: bool,
    gate: tuple[str, list[str], dict[str, str]] | None = None,
) -> tuple[int, list[tuple[str, float]], float]:
    """Run the planned steps, overlapping the long one with the cheap ones.

    Four phases.  ``pre-commit`` rewrites files, so it runs to completion
    before anything reads the tree it edits.  Then ``pytest`` is launched and
    the one-core steps go by in its shadow, which is free.  Then the
    ``HEAVY_STEPS`` -- parallel in their own right, so the shadow was never
    free for them -- run with the machine to themselves.  *gate* is the
    touched-file coverage check, which reads the data file ``pytest`` writes,
    so it goes between the two: as soon as the data is complete, before the
    heavy steps make it wait.

    Output is captured and replayed only on failure unless *stream*.  A step
    that is holding the terminal alone can stream it live instead; two can
    not, since concurrent writers interleave into nonsense.

    Returns the failure count, per-step CPU timings, and the wall time, which
    concurrency makes smaller than the timings' sum.
    """
    failed: list[str] = []
    timings: list[tuple[str, float]] = []
    wall_start = time.time()

    def record(name: str, elapsed: float, returncode: int, output: str | None) -> None:
        timings.append((name, elapsed))
        if not _report(name, elapsed, returncode, output):
            failed.append(name)

    def run_serial(name: str, cmd: list[str], step_env: dict[str, str]) -> None:
        start = time.time()
        # Only the captured branch has output to replay; the streaming one
        # already wrote it straight to the terminal.
        captured: str | None = None
        if stream:
            returncode = subprocess.run(cmd, env=step_env).returncode
        else:
            # Captured, but not in one blocking call: a captured step prints
            # nothing until it ends, and the leak sweep runs for half a
            # minute.  Waiting in slices costs nothing and keeps it legible.
            captured, returncode = _wait_with_heartbeat(
                subprocess.Popen(
                    cmd,
                    env=step_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                ),
                name,
                start,
            )
        record(name, time.time() - start, returncode, captured)

    # Phase 1: the tree-mutating step, alone, before anything reads the tree.
    for name, cmd, step_env in runnable:
        if name == MUTATES_TREE:
            run_serial(name, cmd, step_env)

    # Phase 2: launch the long step, then run the cheap ones in its shadow.
    rest = [s for s in runnable if s[0] != MUTATES_TREE]
    long_step = next((s for s in rest if s[0] == LONG_STEP), None)
    shadow = [s for s in rest if s[0] != LONG_STEP and s[0] not in HEAVY_STEPS]
    heavy = [s for s in rest if s[0] in HEAVY_STEPS]
    proc = None
    long_start = 0.0
    # Nothing to fill the shadow with: run it as an ordinary step, which lets
    # a single-step run (`just test-py`) stream its output live.
    if long_step is not None and not shadow:
        run_serial(*long_step)
        long_step = None
    if long_step is not None:
        _, cmd, step_env = long_step
        long_start = time.time()
        proc = subprocess.Popen(
            cmd,
            env=step_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(f"[....] {LONG_STEP} (running alongside the remaining steps)")

    for name, cmd, step_env in shadow:
        run_serial(name, cmd, step_env)

    if proc is not None:
        # The cheap steps are done and pytest holds the only remaining output.
        output, returncode = _wait_with_heartbeat(proc, LONG_STEP, long_start)
        record(LONG_STEP, time.time() - long_start, returncode, output)

    # Phase 3: the coverage gate, which only speaks for a complete data file,
    # and only if the run that wrote it passed -- coverage from a failed suite
    # records which lines ran before the failure, not which are tested.  Keyed
    # on pytest alone, not on the failure count: another step failing says
    # nothing about the data file.  It is 0.2s and it unblocks nothing, so it
    # goes before the heavy steps rather than after them.
    ran_pytest = any(name == LONG_STEP for name, _ in timings)
    if gate is not None and ran_pytest and LONG_STEP not in failed:
        run_serial(*gate)

    # Phase 4: the parallel steps, now that they can have the machine.
    for name, cmd, step_env in heavy:
        run_serial(name, cmd, step_env)

    return len(failed), timings, time.time() - wall_start


def main() -> int:
    """Compile and run every example, reporting failures."""
    only, skip, full, quiet, verbose = _parse_only_skip()

    # `--list` exits inside the parse, so this never slows it down.
    _ensure_dev_deps()

    # An explicit --only is already a hand-picked subset; scoping it further
    # would silently drop steps the caller asked for by name.
    unaffected, why = (None, "--only given") if only else _scope_plan(full=full)
    changed = [] if unaffected is None else list(_scope_changed_files())
    if unaffected is None:
        print(f"scope: full run ({why})")
    else:
        print(f"scope: {len(STEPS) - len(unaffected)}/{len(STEPS)} steps ({why})")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    # Probe PY rather than the running interpreter: verify.py may be launched
    # by a different python than the one it runs the steps with (e.g.
    # `uv run --with pylint python scripts/verify.py`, which leaves PY pointing
    # at .venv), and it is PY that has to import pylint.
    have_pylint = (
        subprocess.run(
            [*PY, "-c", "import pylint"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    # Decide every step first, then run.  Deciding is pure bookkeeping (scope
    # lookups, tool probes) while running is where the time goes, so keeping
    # the two apart lets the runner overlap the long step with the short ones
    # without the skip logic having to care.
    runnable: list[tuple[str, list[str], dict[str, str]]] = []
    for name, cmd in STEPS:
        if only is not None and name not in only:
            continue
        if skip is not None and name in skip:
            print(f"[skip] {name}: filtered via --skip")
            continue
        if name in FULL_ONLY and only is None and not full:
            print(f"[skip] {name}: left to CI and --full")
            continue
        if unaffected is not None and name in unaffected:
            print(f"[skip] {name}: branch touched none of its files")
            continue
        if unaffected is not None:
            narrowed = _scoped_cmd(name, cmd, changed)
            if narrowed is None:
                print(f"[skip] {name}: branch touched none of its files")
                continue
            cmd = narrowed
        # The `slow` marker covers the generator derivations and fuzz loops
        # whose cost is seconds each.  Deselecting them locally trades no
        # coverage, because the sharded `slow` job runs every marked test
        # on every push.  This is keyed on
        # --full rather than on scoping because a run that widens back to
        # everything -- a tooling change, an unreadable diff -- should still
        # not pay for them.
        #
        # The tests/interpreters suites carry the same marker on their two 5.2s tests
        # (the eight-level nesting round trip and the n=5 parity table), which
        # are 10.4s of that step's 12.8s.  CI's `line` job runs that suite
        # unfiltered on every push, so deselecting them here trades no
        # coverage either.
        step_env = env
        if name == LEAK_STEP and "LEAKSWEEP_JOBS" not in env:
            step_env = dict(step_env, LEAKSWEEP_JOBS=LEAKSWEEP_JOBS)
        if name == "pre-commit":
            # Skip the config's mypy hook: the very next step runs mypy over
            # src/ *and* scripts/ from the project env, against the same
            # pyproject config, so the hook re-proves a strict subset -- and
            # pays for its own isolated env to do it.  Only the local run
            # skips it; CI runs `pre-commit run --all-files` with no SKIP
            # (ci.yml:28), so the hook still guards the config itself.
            step_env = dict(step_env, SKIP="mypy")
        if only is None and name == "pytest":
            # A default run leaves the whole slow band to CI.  A --full run
            # takes the band but not the `weekly` probes inside it,
            # which are 142.6s of its ~182s and are sampled once a week by
            # `.github/workflows/weekly.yml` -- which runs bare `pytest`
            # rather than this script, so it is unaffected by either flag.
            #
            # Appended to argv rather than set in `addopts`, because pytest
            # *prepends* addopts: a default there would sit before the
            # caller's own `-m` and lose to it, and `just test-quick`'s
            # `-m 'not slow and not medium'` would then re-admit the band it
            # exists to skip.
            cmd = [*cmd, "-m", "not weekly" if full else "not slow"]
        if only is None and not full and name == LINE_STEP:
            # Not argv: the command ends in `pytest . -q` under `uv run
            # --isolated`, so an appended flag would land after the path
            # argument and be read by uv's pytest, not composed with the
            # rest of the step's own options.  PYTEST_ADDOPTS is applied
            # by pytest itself wherever it ends up running.
            step_env = dict(env, PYTEST_ADDOPTS=_line_addopts(env))
        if shutil.which("uv") is None and ("bandit" in name or "(uv)" in name):
            print(f"[skip] {name}: uv not installed")
            continue
        if not have_pylint and "(pylint)" in name:
            print(f"[skip] {name}: pylint not installed (pip install pylint)")
            continue
        runnable.append((name, cmd, step_env))

    # The gate speaks only for the suite that actually ran.  A default local
    # run deselects the `slow` tests, so a line covered only by one of those
    # would read as uncovered; --partial makes the gate report it rather than
    # fail on evidence it does not have.  A --full run has no such excuse.
    #
    # The deselection has two sources, and both have to be caught.  This file
    # appends `-m "not slow"` itself, but `just test-quick` instead exports
    # PYTEST_ADDOPTS and passes --only, which suppresses the append while
    # pytest still reads the env var and runs the subset.  Keying on --only
    # alone would leave that path enforcing strict subset data -- the exact
    # false failure --partial exists to prevent, on the blessed fast loop.
    gate: tuple[str, list[str], dict[str, str]] | None = None
    if any(name == "pytest" for name, _, _ in runnable):
        gate_cmd = [*PY, "scripts/check_diff_coverage.py"]
        selected = any(
            word.startswith("-m") for word in env.get("PYTEST_ADDOPTS", "").split()
        )
        if selected or (only is None and not full):
            gate_cmd.append("--partial")
        gate = (DIFF_COVERAGE_STEP, gate_cmd, env)

    # Name validation catches a typo; this catches the rest (--only X --skip X,
    # a probe that found no tool).  Zero steps is not a pass.
    if not runnable:
        print("=" * 40)
        print("no checks ran: the filters selected zero steps")
        return 1

    stream = _should_stream(len(runnable), quiet=quiet, verbose=verbose)
    failures, timings, wall = _run_steps(runnable, stream=stream, gate=gate)

    if timings:
        print("-" * 40)
        for name, elapsed in timings:
            print(f"{elapsed:5.1f}s  {name}")
        total = sum(t for _, t in timings)
        # Two totals, because they stopped being the same number once pytest
        # started running alongside the rest: the sum is how much work was
        # done, the wall is how long the push actually waited for it.
        print(f"{total:5.1f}s  TOTAL (sum of steps)")
        print(f"{wall:5.1f}s  WALL  (elapsed, steps overlap)")
    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
