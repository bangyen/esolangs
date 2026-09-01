"""Run the full local verification stack.

Everything that can be checked on a dev machine without a Linux host:

1. pre-commit (lint, format, types) and pytest (the test suite)
2. bandit (via uv), the ``extra/line`` suites (via uv, which supplies the
   image libraries the package itself does not depend on), and the
   interpreter-vs-native differential corpora
3. unicorn-based round-trips (RISC-V assembly compilers and the
   differential corpora) — skipped when unicorn or the RISC-V
   cross-compiler is missing

The native qemu-riscv64 checks need Linux, so they run only in CI (see
.github/workflows/ci.yml).  ``.githooks/pre-push`` and ``just test`` both run
this script.

By default the run is *scoped*: each step declares the paths it guards (see
``STEP_SCOPE``), and a step whose paths this branch never touched is skipped,
because nothing the branch did could have broken it.  Three steps take a file
list instead of being all-or-nothing, so they are narrowed rather than skipped
-- pre-commit to the changed files, pytest to the matching test modules, and
the differential corpora to the cross-checked languages that moved.

Scoping only ever subtracts work that provably could not have broken.  When
the branch's diff cannot be read, or it touches the shared interpreter
machinery or the verification tooling itself, the run widens back to
everything (see ``scripts/_scope.py``).  ``--full`` forces that too, and CI
still runs the complete suite on every push regardless.

A default run also leaves work to CI where CI already covers it: the steps in
``FULL_ONLY`` (the differential corpora, which CI runs twice with ``--fuzz
50``; the ZTOALC anchor table, which CI's lint job re-derives; and the
RISC-V unicorn round-trip, which CI's assembly job runs) and the ``slow``
marker in both test suites -- pytest's (the fuzzers' divergence-detection
tests, which CI runs by that same marker and errors on if they skip) and
extra/line's (its two 5.2s render round trips, which CI's ``line`` job runs
unfiltered).  ``--full``, ``just test-full``, and an explicit ``--only`` all
still run them.

The steps do not all run one after another.  ``pytest`` takes longer than
everything else put together, so it is launched first and the short steps run
while it goes; ``pre-commit`` is the exception on the other side, run to
completion before anything else starts because its fix hooks rewrite the very
files the other steps read.  That makes the timing table's two totals differ:
the sum is how much work ran, the wall is how long the push waited.

Usage:
    python scripts/verify.py [--only STEPS] [--skip STEPS] [--full] [--list]
    python scripts/verify.py --full                       # every step, whole tree
    python scripts/verify.py --only pytest,bandit         # comma-separated STEPS names
    python scripts/verify.py --only pre-commit,pytest --skip bandit
"""

import argparse
import functools
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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
# they save at push time, and CI already runs them on every push -- the
# differential twice, and with --fuzz 50, so more thoroughly than here.  They
# still run under --full, under an explicit --only, and via `just test-full`.
FULL_ONLY = frozenset(
    {
        "interpreter vs native differential corpora",
        # Re-deriving the table costs ~3.2s and only guards two files that
        # rarely move; CI's lint job runs it on every push instead.
        "ztoalc anchor table is reproducible",
        # Assembling and emulating every compiler's output is the slowest
        # non-pytest step (~8s, a third of the rest put together), and its
        # scope includes all of src/esolangs/, so it fires on any interpreter
        # edit.  CI's assembly job runs the identical script on every push.
        "RISC-V assembly under unicorn (compilers + cross-checks)",
    }
)

# Named once: the step table, STEP_SCOPE and the slow-marker filter all refer
# to this step, and a typo in any of them would silently stop matching.
LINE_STEP = "extra/line suites (uv)"

# How often the long step reports that it is still going.  Short enough that
# the wait never looks stalled, long enough that a normal run prints only a
# handful of lines.
HEARTBEAT_SECONDS = 20.0

# Not a STEPS entry: it reads the coverage data file `pytest` writes, and
# `pytest` is LONG_STEP -- launched with Popen and left running while the
# short steps go by.  A sibling step would race it and read a half-written
# file, so the gate is run by _run_steps once the long step has exited.
DIFF_COVERAGE_STEP = "changed-line coverage"


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
    LINE_STEP: ("extra/line/",),
    # The check re-derives the anchor table and diffs it against the committed
    # file, importing nothing from the interpreters -- so the only things that
    # can break it are the generator script and the table itself.  Scoping to
    # `interpreters/` instead both ran it for every unrelated interpreter edit
    # and missed a hand-edit of the table, the one case it exists to catch.
    "ztoalc anchor table is reproducible": (
        "scripts/make_ztoalc_table.py",
        "src/esolangs/tools/ztoalc_starts.py",
    ),
    "RISC-V assembly under unicorn (compilers + cross-checks)": (
        "extra/assembly/",
        "src/esolangs/",
        "scripts/verify_riscv_unicorn.py",
    ),
    "duplicate-code check (pylint)": ("src/esolangs/", "scripts/", "tests/"),
    "single-interpreter installer": (
        "src/esolangs/",
        "scripts/install_one.sh",
        "scripts/bundle_one.py",
        "scripts/verify_install_one.py",
    ),
}

STEPS = [
    ("pre-commit", [*PY, "-m", "pre_commit", "run", "--all-files"]),
    # pre-commit's mypy hook is scoped to src/ (its isolated env lacks the
    # scripts' imports), so scripts/ is type-checked here, in the project env.
    ("mypy (src + scripts)", [*PY, "-m", "mypy"]),
    # `--cov-report=` writes no report: the run is here for the data file,
    # which the changed-line gate reads afterwards.
    #
    # `--cov-branch` is asked for unconditionally, but only because the
    # interpreter moved.  It is worth recording why, since the answer has now
    # flipped twice.  sys.monitoring cannot measure branches before 3.14, so
    # asking for arcs there drops coverage onto the old tracer -- measured on
    # 3.13 over this suite (-n 4, coverage 7.13.4, the fast selection):
    #
    #     no coverage                36.5s
    #     --cov (line, sysmon)       36.1s
    #     --cov --cov-branch         119.3s   <- 3.3x, the no-sysmon fallback
    #
    # 3.14's sys.monitoring measures branches, so the fallback never happens
    # and the flag is free again.  Re-measured on 3.14, same suite and flags:
    #
    #     --cov (line, sysmon)       17.81s
    #     --cov --cov-branch         17.89s   <- free
    #
    # An older interpreter would silently pay the 3.3x rather than break, so
    # if this ever feels slow again, check the interpreter before the tests:
    # coverage says so on stderr with a `no-sysmon` CoverageWarning.
    ("pytest", [*PY, "-m", "pytest", "-q", "--cov", "--cov-branch", "--cov-report="]),
    ("bandit", ["uv", "run", "--with", "bandit", "bandit", "-r", "src", "-q"]),
    (
        # These also run under the plain `pytest` step above.  Repeated here
        # under `--isolated --no-project`, which installs only pytest, so a
        # green run proves the subtree pulls in no third-party dependency.
        # The in-project run cannot show that.
        LINE_STEP,
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--directory",
            "extra/line",
            "--with",
            "pytest",
            "--with",
            "pytest-xdist",
            "pytest",
            ".",
            "-q",
        ],
    ),
    (
        "ztoalc anchor table is reproducible",
        [*PY, "scripts/make_ztoalc_table.py", "--check"],
    ),
    (
        "RISC-V assembly under unicorn (compilers + cross-checks)",
        [*PY, "scripts/verify_riscv_unicorn.py"],
    ),
    (
        "interpreter vs native differential corpora",
        [*PY, "scripts/verify_differential.py"],
    ),
    (
        "docstring check",
        [*PY, "scripts/check_docstrings.py"],
    ),
    (
        # pylint's R0801 reports similar blocks across files, catching
        # copy-pasted helpers like the bracket matcher or the OISC memory
        # tokenizer.  --ignore-imports keeps shared import blocks from
        # counting as duplication.
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
            "tests",
        ],
    ),
    (
        "single-interpreter installer",
        [*PY, "scripts/verify_install_one.py"],
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
            # A conftest configures every test beneath it, and a non-.py file
            # is fixture data some unknown test reads.  Either scoped to itself
            # would collect nothing and pass trivially, so both widen.
            if Path(f).name == "conftest.py" or not f.endswith(".py"):
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
        if paths == WHOLE_SUITE:
            return cmd  # not localisable: run every test
        if not paths:
            return None  # nothing the Python tests cover moved
        return [*cmd, *paths]
    if name == "interpreter vs native differential corpora":
        return [*cmd, "--scope"]
    return cmd


def _parse_only_skip() -> tuple[set[str] | None, set[str] | None, bool, bool]:
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
        help="suppress successful step output (only failures, [ok] and timing)",
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
    return only, skip, args.full, args.quiet


# The step that mutates the working tree.  pre-commit's ruff/ruff-format and
# whitespace hooks rewrite files in place, so anything that reads the tree has
# to wait for it -- running it alongside pytest would race the edit against the
# read.  It is the only such step: everything else only reads.
MUTATES_TREE = "pre-commit"

# The long pole.  Every other step put together is shorter than this one, so
# the runner starts it first and fills its shadow with the rest.
LONG_STEP = "pytest"


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
    quiet: bool,
    gate: tuple[str, list[str], dict[str, str]] | None = None,
) -> tuple[int, list[tuple[str, float]], float]:
    """Run the planned steps, overlapping the long one with the short ones.

    ``pytest`` is longer than everything else combined, so it is launched
    first and left running while the short steps go by in order.  *gate* is
    the changed-line coverage check, which reads the data file ``pytest``
    writes and so can only run once it has exited.  Its output
    is captured either way -- two live subprocesses writing to one terminal
    interleave into nonsense -- so unlike the short steps it does not stream
    even outside ``--quiet``.  ``pre-commit`` rewrites files, so it is run to
    completion *before* anything is launched against the tree it edits.

    Returns the failure count, per-step CPU timings, and the wall time, which
    concurrency makes smaller than the timings' sum.
    """
    failures = 0
    timings: list[tuple[str, float]] = []
    wall_start = time.time()

    def run_serial(name: str, cmd: list[str], step_env: dict[str, str]) -> None:
        nonlocal failures
        start = time.time()
        result: subprocess.CompletedProcess[Any]
        # Only the captured branch has output to replay; the streaming one
        # already wrote it straight to the terminal.
        captured: str | None = None
        if quiet:
            result = subprocess.run(
                cmd,
                env=step_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            captured = result.stdout
        else:
            result = subprocess.run(cmd, env=step_env)
        elapsed = time.time() - start
        timings.append((name, elapsed))
        failures += not _report(name, elapsed, result.returncode, captured)

    # Phase 1: the tree-mutating step, alone, before anything reads the tree.
    for name, cmd, step_env in runnable:
        if name == MUTATES_TREE:
            run_serial(name, cmd, step_env)

    # Phase 2: launch the long step, then run the short ones in its shadow.
    rest = [s for s in runnable if s[0] != MUTATES_TREE]
    long_step = next((s for s in rest if s[0] == LONG_STEP), None)
    proc = None
    long_start = 0.0
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

    for name, cmd, step_env in rest:
        if name != LONG_STEP:
            run_serial(name, cmd, step_env)

    if proc is not None:
        # The short steps are done and pytest holds the only remaining output,
        # captured rather than streamed so two live subprocesses cannot
        # interleave into nonsense.  Waiting on it in one blocking call meant
        # the push sat silent for the ~2 minutes the suite takes, which reads
        # as a hang -- long enough to invite the Ctrl-C that skips the checks.
        # Waiting in slices costs nothing and keeps the wait legible.
        output = ""
        while True:
            try:
                output, _ = proc.communicate(timeout=HEARTBEAT_SECONDS)
                break
            except subprocess.TimeoutExpired:
                waited = time.time() - long_start
                print(f"[....] {LONG_STEP} still running ({waited:.0f}s elapsed)")
        elapsed = time.time() - long_start
        timings.append((LONG_STEP, elapsed))
        pytest_ok = _report(LONG_STEP, elapsed, proc.returncode, output)
        failures += not pytest_ok
        # Only meaningful once the data file is complete, and only if the run
        # that wrote it passed: coverage from a failed suite records which
        # lines ran before the failure, not which are tested.
        if pytest_ok and gate is not None:
            run_serial(*gate)

    return failures, timings, time.time() - wall_start


def main() -> int:
    """Compile and run every example, reporting failures."""
    import importlib.util

    only, skip, full, quiet = _parse_only_skip()

    # An explicit --only is already a hand-picked subset; scoping it further
    # would silently drop steps the caller asked for by name.
    unaffected, why = (None, "--only given") if only else _scope_plan(full=full)
    changed = [] if unaffected is None else list(_scope_changed_files())
    if unaffected is None:
        print(f"scope: full run ({why})")
    else:
        print(f"scope: {len(STEPS) - len(unaffected)}/{len(STEPS)} steps ({why})")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    have_unicorn = importlib.util.find_spec("unicorn") is not None
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
    have_riscv_gcc = (
        shutil.which("riscv64-elf-gcc") is not None
        or shutil.which("riscv64-linux-gnu-gcc") is not None
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
        # The `slow` marker is on the fuzzers' divergence-detection tests,
        # which drive the native toolchains: ~19s of the suite's ~25s for 10
        # of its 3758 tests.  CI runs exactly those ten (ci.yml:323, `-m
        # slow`) and errors if any is skipped, so deselecting them locally
        # trades no coverage.  This is keyed on --full rather than on scoping
        # because a run that widens back to everything -- a tooling change, an
        # unreadable diff -- should still not pay for them.
        #
        # The extra/line suites carry the same marker on their two 5.2s tests
        # (the eight-level nesting round trip and the n=5 parity table), which
        # are 10.4s of that step's 12.8s.  CI's `line` job runs that suite
        # unfiltered on every push, so deselecting them here trades no
        # coverage either.
        step_env = env
        if name == "pre-commit":
            # Skip the config's mypy hook: the very next step runs mypy over
            # src/ *and* scripts/ from the project env, against the same
            # pyproject config, so the hook re-proves a strict subset -- and
            # pays for its own isolated env to do it.  Only the local run
            # skips it; CI runs `pre-commit run --all-files` with no SKIP
            # (ci.yml:28), so the hook still guards the config itself.
            step_env = dict(step_env, SKIP="mypy")
        if only is None and not full:
            if name == "pytest":
                cmd = [*cmd, "-m", "not slow"]
            elif name == LINE_STEP:
                # Not argv: the command ends in `pytest . -q` under `uv run
                # --isolated`, so an appended flag would land after the path
                # argument and be read by uv's pytest, not composed with the
                # rest of the step's own options.  PYTEST_ADDOPTS is applied
                # by pytest itself wherever it ends up running.
                step_env = dict(env, PYTEST_ADDOPTS=_line_addopts(env))
        if not have_unicorn and "unicorn" in name:
            print(f"[skip] {name}: unicorn not installed (pip install unicorn)")
            continue
        if not have_riscv_gcc and "assembly" in name:
            print(f"[skip] {name}: RISC-V cross-compiler not installed")
            continue
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
    # alone would leave that path strict-gating subset data -- the exact
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

    failures, timings, wall = _run_steps(runnable, quiet=quiet, gate=gate)

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
