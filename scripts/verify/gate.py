"""Run lint, types and tests locally; leave specialist checks to CI.

The default scopes pre-commit and pytest to changed files and excludes slow
and weekly tests. Shared changes widen to the whole tree. ``--full`` runs
whole-tree local checks including slow tests; ``--only`` also exposes the
specialist CI checks for manual runs. Weekly tests require explicit selection.

Pre-commit finishes before readers start because its hooks rewrite files.
Pytest overlaps the remaining checks. Failures replay captured output;
single-step runs stream it. ``just test`` and the pre-push hook use this gate.
"""

# Annotate lazily: ``collect_long`` below is annotated ``subprocess.Popen[str]``,
# which tests replace with a plain function.  On 3.12/3.13 (eager annotations)
# that subscript is evaluated when the nested function is defined and raises
# ``TypeError: 'function' object is not subscriptable``; 3.14 defers it (PEP 649).
from __future__ import annotations

import argparse
import contextlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# scripts/ holds the sibling `verify`, `docs`, and `ci` packages.
sys.path.insert(0, str(ROOT / "scripts"))

from verify.process import (  # noqa: E402
    run_bounded,
    start_logged,
    wait_with_heartbeat,
)
from verify.scope import (  # noqa: E402
    CACHED_STEPS,
    VerifiedCache,
    _scope_changed_files,
    _scope_plan,
    _scoped_cmd,
    local_tooling_deselections,
)

# language-owners: ["Line"]
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
    ``python scripts/verify/gate.py``), which does not have the project's dev
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

# CI owns these checks; --only retains manual local access.
MANUAL_ONLY = frozenset(
    {
        "generated docs",
        "dead definitions",
        "generator size baseline",
        "duplicate-code check (pylint)",
        "deep proofs (verify band)",
        "exception leaks",
    }
)

# Both local tiers exclude the weekly probes. A default run also excludes the
# slow band; --full includes it.
LOCAL_PYTEST_MARKS = "not slow and not weekly"
FULL_PYTEST_MARKS = "not weekly"

# How often the long step reports that it is still going.  Short enough that
# the wait never looks stalled, long enough that a normal run prints only a
# handful of lines.
HEARTBEAT_SECONDS = 20.0

# CI allows 15 minutes for pytest; ordinary checks must finish in one minute.
STEP_DEADLINES = {"pytest": 900.0, "exception leaks": 120.0}
DEFAULT_STEP_DEADLINE = 60.0

STEPS = [
    (
        "generated docs",
        [*PY, "checks/check_generated_docs.py"],
    ),
    ("pre-commit", [*PY, "-m", "pre_commit", "run", "--all-files"]),
    # The only mypy run.  pre-commit has no mypy hook: the mirror's isolated
    # env lacks the scripts' imports, so it could only ever cover src/, and
    # this run covers src/ and scripts/ both from the project env.
    ("mypy (src + scripts)", [*PY, "-m", "mypy"]),
    ("pytest", [*PY, "-m", "pytest", "-q"]),
    # A generator route that was replaced keeps its own tests green, so it
    # never fails; three sat that way.  <1s.
    ("dead definitions", [*PY, "checks/check_dead_definitions.py"]),
    # What every generator emits, and how many steps the emitted program
    # runs, pinned exactly against a committed baseline: the two quantities
    # the collection's claims rest on, and until this step nothing measured
    # them outside a hand-run `just benchmark`.  192 measurements, ~3s.
    ("generator size baseline", [*PY, "checks/check_generator_sizes.py"]),
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
            "checks/check_duplicate_code.py",
            "--disable=all",
            "--enable=duplicate-code",
            "--min-similarity-lines=10",
            "--ignore-imports=yes",
            "--ignore=tests",
            "src/esolangs",
            "scripts",
            "checks",
        ],
    ),
    # language-owners: ["ArrowQueue", "BIO"]
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
    # --all over the whole registry.
    (
        "exception leaks",
        [*PY, "checks/verify_no_exception_leaks.py"],
    ),
]


# What fixes a step beyond rerunning it, for the steps whose failure is a
# stale committed file a script rewrites.  Printed under its rerun command.
FIXES: dict[str, tuple[str, ...]] = {
    "generated docs": ("uv run python scripts/docs/generate.py docs",),
    "generator size baseline": (
        "uv run python checks/check_generator_sizes.py --update  "
        "(only if the size change is intended)",
    ),
}


def _rerun_hint(name: str) -> list[str]:
    """Return the commands that rerun, and any that fix, failed step *name*."""
    if name == "verification inputs":
        return ["  rerun: uv run python scripts/verify/gate.py"]
    step = name
    rerun = f"  rerun: uv run python scripts/verify/gate.py --only {shlex.quote(step)}"
    return [rerun, *(f"  fix:   {fix}" for fix in FIXES.get(name, ()))]


def _parse_only_skip() -> tuple[
    set[str] | None, set[str] | None, bool, bool, bool, bool
]:
    parser = argparse.ArgumentParser(description="Run the local verification stack")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="comma-separated subset of STEPS names to run (--only pytest)",
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
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="skip unavailable tools and report incomplete verification",
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
    return only, skip, args.full, args.quiet, args.verbose, args.allow_incomplete


# The step that mutates the working tree.  pre-commit's ruff/ruff-format and
# whitespace hooks rewrite files in place, so anything that reads the tree has
# to wait for it -- running it alongside pytest would race the edit against
# the read.  The only such step: everything else only reads.
MUTATES_TREE = "pre-commit"

# The long pole.  The runner starts it first and fills its shadow with the
# cheap steps.
LONG_STEP = "pytest"

# Unbounded overlap took the leak sweep from 35.6s to 85.4s.
# Three leak workers plus four pytest workers leave a core
# for the serial shadow checks; a standalone sweep keeps six.
LEAK_STEP = "exception leaks"
HEAVY_STEPS = frozenset({LEAK_STEP})
LEAKSWEEP_JOBS = "6"
OVERLAPPED_LEAKSWEEP_JOBS = "3"


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
    probe = run_bounded(
        [*PY, "-c", "import pytest"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode == 0:
        return
    if shutil.which("uv") is None:
        return
    print("dev dependencies missing; running `uv sync --group dev` ...")
    run_bounded(["uv", "sync", "--group", "dev"], cwd=ROOT, check=False)


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
    return wait_with_heartbeat(
        proc,
        name,
        start,
        STEP_DEADLINES.get(name, DEFAULT_STEP_DEADLINE),
        HEARTBEAT_SECONDS,
    )


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
) -> tuple[int, list[tuple[str, float]], float]:
    """Run the planned steps, overlapping the long one with the cheap ones.

    ``pre-commit`` finishes before readers start. Captured runs overlap
    pytest with the leak sweep and one serial shadow lane. Streaming runs
    leave the sweep until afterwards to keep terminal output coherent.

    Output is captured and replayed only on failure unless *stream*.  A step
    that is holding the terminal alone can stream it live instead; two can
    not, since concurrent writers interleave into nonsense.

    Returns the failure count, per-step CPU timings, and the wall time, which
    concurrency makes smaller than the timings' sum.
    """
    failed: list[str] = []
    timings: list[tuple[str, float]] = []
    wall_start = time.monotonic()
    clean_cache: VerifiedCache | None = None
    cache_keys: dict[str, str | None] = {}

    def record(name: str, elapsed: float, returncode: int, output: str | None) -> None:
        timings.append((name, elapsed))
        if not _report(name, elapsed, returncode, output):
            failed.append(name)

    def run_serial(name: str, cmd: list[str], step_env: dict[str, str]) -> None:
        start = time.monotonic()
        # Only the captured branch has output to replay; the streaming one
        # already wrote it straight to the terminal.
        captured: str | None = None
        key = None
        if clean_cache is not None and name in CACHED_STEPS:
            key = cache_keys.get(name)
            if key is not None:
                cached = clean_cache.load(key)
                if cached is not None:
                    print(f"[cache] {name}: identical verified inputs")
                    record(name, time.monotonic() - start, 0, cached)
                    return
        captured, returncode = _wait_with_heartbeat(
            start_logged(cmd, name, step_env, ROOT, stream=stream),
            name,
            start,
        )
        record(name, time.monotonic() - start, returncode, captured)
        if key is not None and returncode == 0 and captured is not None:
            assert clean_cache is not None
            clean_cache.remember(key, captured, returncode)

    # Companion checks wait for formatting; runtime probes may overlap it.
    # The cache's initial snapshot rejects entries if formatting changed inputs.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = []
        if not stream and any(
            name in CACHED_STEPS and env.get("VERIFY_CLEAN_CACHE", "1") != "0"
            for name, _, env in runnable
        ):
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                clean_cache = VerifiedCache(ROOT)

                def prepare(steps: list[tuple[str, list[str], dict[str, str]]]) -> None:
                    assert clean_cache is not None
                    for name, cmd, step_env in steps:
                        cache_keys[name] = clean_cache.key(name, cmd, step_env)

                eligible = [step for step in runnable if step[0] in CACHED_STEPS]
                futures = [pool.submit(prepare, eligible)]
        for name, cmd, step_env in runnable:
            if name == MUTATES_TREE:
                run_serial(name, cmd, step_env)
        for future in futures:
            future.result()
    if MUTATES_TREE in failed:
        clean_cache = None
        cache_keys.clear()

    # Phase 2: launch the long step, then run the cheap ones in its shadow.
    rest = [s for s in runnable if s[0] != MUTATES_TREE]
    long_step = next((s for s in rest if s[0] == LONG_STEP), None)
    shadow = [s for s in rest if s[0] != LONG_STEP and s[0] not in HEAVY_STEPS]
    heavy = [s for s in rest if s[0] in HEAVY_STEPS]
    proc = None
    long_start = 0.0
    # Nothing to fill the shadow with: run it as an ordinary step, which lets
    # a single-step run (`just test-py`) stream its output live.
    if long_step is not None and not shadow and (stream or not heavy):
        run_serial(*long_step)
        long_step = None
    if long_step is not None:
        _, cmd, step_env = long_step
        long_start = time.monotonic()
        proc = start_logged(cmd, LONG_STEP, step_env, ROOT, stream=False)
        print(f"[....] {LONG_STEP} (running alongside the remaining steps)")

    if proc is not None:

        def collect_long(
            child: subprocess.Popen[str], started: float
        ) -> tuple[str, int, float]:
            output, returncode = _wait_with_heartbeat(child, LONG_STEP, started)
            return output, returncode, time.monotonic() - started

        # Drain immediately: waiting until the shadow ends can fill the pipe
        # and stall pytest. The collector also measures its actual finish.
        with ThreadPoolExecutor(max_workers=1) as collector:
            pending = collector.submit(collect_long, proc, long_start)
            if stream:
                for name, cmd, step_env in shadow:
                    run_serial(name, cmd, step_env)
            else:

                def run_shadow() -> None:
                    for step in shadow:
                        run_serial(*step)

                with ThreadPoolExecutor(max_workers=2) as checks:
                    results = [checks.submit(run_serial, *step) for step in heavy]
                    results.append(checks.submit(run_shadow))
                    for result in results:
                        result.result()
                heavy = []
            output, returncode, elapsed = pending.result()
        record(LONG_STEP, elapsed, returncode, output)
    else:
        for name, cmd, step_env in shadow:
            run_serial(name, cmd, step_env)

    # Phase 4: the parallel steps, now that they can have the machine.
    for name, cmd, step_env in heavy:
        run_serial(name, cmd, step_env)

    if clean_cache is not None and not clean_cache.finish():
        record("verification inputs", 0.0, 1, "Inputs changed during verification")

    for name in failed:
        print(f"[FAIL] {name}", *_rerun_hint(name), sep="\n")
    return len(failed), timings, time.monotonic() - wall_start


def main() -> int:
    """Run the verification stack: lint, types, tests, and scoping."""
    only, skip, full, quiet, verbose, allow_incomplete = _parse_only_skip()

    # `--list` exits inside the parse, so this never slows it down.
    _ensure_dev_deps()

    # An explicit --only is already a hand-picked subset; scoping it further
    # would silently drop steps the caller asked for by name.
    unaffected, why = (None, "--only given") if only else _scope_plan(full=full)
    changed = (
        []
        if only or full or os.environ.get("VERIFY_FULL", "0") not in ("", "0")
        else list(_scope_changed_files())
    )
    if unaffected is None:
        print(f"scope: full run ({why})")
    else:
        print(f"scope: {len(STEPS) - len(unaffected)}/{len(STEPS)} steps ({why})")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    if only is not None or full or os.environ.get("VERIFY_FULL", "0") not in ("", "0"):
        env["VERIFY_CLEAN_CACHE"] = "0"
    # Probe PY rather than the running interpreter: verify.py may be launched
    # by a different python than the one it runs the steps with (e.g.
    # `uv run --with pylint python scripts/verify/gate.py`, which leaves PY pointing
    # at .venv), and it is PY that has to import pylint.
    have_pylint = (
        only is not None
        and "duplicate-code check (pylint)" in only
        and (
            run_bounded(
                [*PY, "-c", "import pylint"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
    )
    # Decide every step first, then run.  Deciding is pure bookkeeping (scope
    # lookups, tool probes) while running is where the time goes, so keeping
    # the two apart lets the runner overlap the long step with the short ones
    # without the skip logic having to care.
    runnable: list[tuple[str, list[str], dict[str, str]]] = []
    unavailable: list[str] = []
    for name, cmd in STEPS:
        if only is not None and name not in only:
            continue
        if skip is not None and name in skip:
            print(f"[skip] {name}: filtered via --skip")
            continue
        if name in MANUAL_ONLY and only is None:
            print(f"[skip] {name}: left to CI; use --only to run locally")
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
        # language-owners: ["Line"]
        # The tests/interpreters suites carry the same marker on their two 5.2s tests
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
        if only is None and name == "pytest":
            # A default run leaves the slow band to CI; --full takes it but
            # not the `weekly` probes, which only weekly.yml runs.
            #
            # Appended to argv rather than set in `addopts`, because pytest
            # *prepends* addopts: a default there would sit before the
            # caller's own `-m` and lose to it. `just test-quick` supplies its
            # own expression excluding all three deferred bands.
            cmd = [*cmd, "-m", FULL_PYTEST_MARKS if full else LOCAL_PYTEST_MARKS]
            if full:
                directory = ROOT / "notes/verification"
                directory.mkdir(parents=True, exist_ok=True)
                timing_directory = Path(
                    tempfile.mkdtemp(prefix="pytest-timings-", dir=directory)
                )
                output = timing_directory / "durations.json"
                print(f"[timings] {output}.progress.jsonl")
                cmd.extend(
                    [
                        "-p",
                        "scripts.ci.shard",
                        "--duration-output",
                        str(output),
                        "--duration-input",
                        str(ROOT / "tests/support/fixtures/slow_durations.json"),
                    ]
                )
            if not full and os.environ.get("VERIFY_FULL", "0") in ("", "0"):
                deferred = local_tooling_deselections(changed)
                cmd.extend(deferred)
                if deferred:
                    print("[defer] unrelated tooling integrations: covered by CI")
        if not have_pylint and "(pylint)" in name:
            unavailable.append(f"{name}: pylint not installed (pip install pylint)")
            continue
        runnable.append((name, cmd, step_env))

    if unavailable:
        for reason in unavailable:
            print(f"[unavailable] {reason}")
        if not allow_incomplete:
            print(
                "verification failed: install required tools or use --allow-incomplete"
            )
            return 1

    if "LEAKSWEEP_JOBS" not in env:
        overlap = not _should_stream(
            len(runnable), quiet=quiet, verbose=verbose
        ) and any(name == LONG_STEP for name, _, _ in runnable)
        jobs = OVERLAPPED_LEAKSWEEP_JOBS if overlap else LEAKSWEEP_JOBS
        runnable = [
            (name, cmd, dict(step_env, LEAKSWEEP_JOBS=jobs))
            if name == LEAK_STEP
            else (name, cmd, step_env)
            for name, cmd, step_env in runnable
        ]

    # Name validation catches a typo; this catches the rest (--only X --skip X,
    # a probe that found no tool).  Zero steps is not a pass.
    if not runnable:
        print("=" * 40)
        print("no checks ran: the filters selected zero steps")
        return 1

    stream = _should_stream(len(runnable), quiet=quiet, verbose=verbose)
    failures, timings, wall = _run_steps(runnable, stream=stream)

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
    if unavailable:
        print(
            "incomplete verification: available checks passed; required tools missing"
        )
    else:
        print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
