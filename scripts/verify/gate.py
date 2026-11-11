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
import os
import shlex
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# scripts/ holds the sibling `verify`, `docs`, and `ci` packages.
sys.path.insert(0, str(ROOT / "scripts"))

from verify.failures import (  # noqa: E402
    DURATION_FAILURE,
    failed_ids,
    failure_sections,
    section_matches,
)
from verify.process import (  # noqa: E402
    run_bounded,
    start_logged,
    wait_with_heartbeat,
)
from verify.receipts import AcceptanceRun  # noqa: E402
from verify.scope import (  # noqa: E402
    _scope_changed_files,
    _scope_plan,
    _scoped_cmd,
    local_tooling_deselections,
    verify_full,
    whole_tree_cmd,
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


PY = ["uv", "run", "--no-sync", "python"]

# CI owns these checks; --only retains manual local access.
MANUAL_ONLY = frozenset(
    {
        "generated docs",
        "dead definitions",
        "generator size baseline",
        "construction witnesses",
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

_ACTIVE_ACCEPTANCE: AcceptanceRun | None = None

STEPS = [
    (
        "generated docs",
        [*PY, "checks/check_docs.py"],
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
    ("construction witnesses", [*PY, "-m", "checks.check_construction_witnesses"]),
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


def _cause(returncode: int) -> str:
    """Return why a step failed, from the codes ``wait_with_heartbeat`` sets."""
    if returncode == 124:
        return "deadline exceeded"
    if returncode == 125:
        return "log overflow or write error"
    return f"exit {returncode}"


#: Failing tests listed in the closing summary before it says how many more.
_SHOWN_FAILURES = 10


def _located(output: str | None) -> list[str]:
    """Return a failed step's log path and pytest's failing test ids.

    The summary used to end at ``rerun``, and following it meant a second
    full-tree pytest run to learn a name already in the log.
    """
    lines = (output or "").splitlines()
    log = [f"  {line}" for line in lines if line.startswith("[log] ")]
    tests = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
    tests += _failed_hooks(lines)
    shown = [f"  {line}" for line in tests[:_SHOWN_FAILURES]]
    if len(tests) > _SHOWN_FAILURES:
        shown.append(f"  ... and {len(tests) - _SHOWN_FAILURES} more in the log")
    return log + shown


def _failed_hooks(lines: list[str]) -> list[str]:
    """Return ``hook: first line it printed`` for each failed pre-commit hook.

    Six sessions grepped the log for a cause the summary only linked to.
    """
    found = []
    for i, line in enumerate(lines):
        if not line.endswith(".Failed"):
            continue
        hook = line.removesuffix("Failed").rstrip(".")
        detail = ""
        for text in lines[i + 1 : i + 12]:
            if text.endswith(("Passed", "Failed", "Skipped")):
                break  # the next hook: this one printed nothing of its own
            if text.strip() and not text.startswith("- "):
                detail = text.strip()
                break
        found.append(f"{hook}: {detail}" if detail else hook)
    return found


#: Pytest failures that mean a committed artifact is stale.  A generator
#: change once surfaced them one cluster per ~150 s run, a dozen runs in a
#: row (2026-10-20); the fix is the whole regeneration, in this order.
STALE_ARTIFACT_TESTS = (
    "tests/tooling/test_examples.py",
    "tests/tooling/test_make_languages_doc.py",
    "tests/proofs/test_status.py",
    "test_the_size_anchor_is_what_generate_emits",
)
REGENERATE = (
    "uv run python scripts/docs/generate.py docs",
    "uv run python scripts/docs/generate.py examples",
    "uv run python checks/check_generator_sizes.py --update  "
    "(only if the size change is intended; refresh docstring anchors with "
    "scripts/docs/generate.py anchors)",
)


def _rerun_hint(name: str, output: str | None = None) -> list[str]:
    """Return the commands that rerun, and any that fix, failed step *name*."""
    rerun = f"  rerun: uv run python scripts/verify/gate.py --only {shlex.quote(name)}"
    fixes = FIXES.get(name, ())
    if name == LONG_STEP and any(
        line.startswith(("FAILED ", "ERROR "))
        and any(t in line for t in STALE_ARTIFACT_TESTS)
        for line in (output or "").splitlines()
    ):
        fixes = REGENERATE
    return [rerun, *(f"  fix:   {fix}" for fix in fixes)]


def _parse_only_skip() -> tuple[set[str] | None, set[str] | None, bool, bool, bool]:
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

# Unbounded overlap took the leak sweep from 35.6s to 85.4s.
# Three leak workers plus four pytest workers leave a core
# for the serial shadow checks; a standalone sweep keeps six.
LEAK_STEP = "exception leaks"
HEAVY_STEPS = frozenset({LEAK_STEP})
LEAKSWEEP_JOBS = "6"
OVERLAPPED_LEAKSWEEP_JOBS = "3"


def _complete_log(output: str) -> str | None:
    """Return the step's complete log text, when the excerpt names its path.

    The captured output is a bounded tail of the step's log (see
    ``verify.process.excerpt``); its ``[log]`` line names the persistent
    complete log the tail was cut from, which is where the FAILURES
    sections above the tail survive.
    """
    for line in output.splitlines():
        if line.startswith("[log] "):
            path = Path(line[len("[log] ") :].strip())
            if not path.is_absolute():
                path = ROOT / path
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
    return None


def _duration_only_ids(output: str) -> list[str] | None:
    """Return the failed tests' ids when every failure is a duration overrun.

    pytest's one-line summary names the failures but drops their reasons,
    so the claim is read from the FAILURES sections instead: each names its
    test in an underscore header and holds the failure's body, which for a
    band failure is the violation text itself.  Anything unprovable -- an
    ERROR line (a collection or teardown problem, which no duration
    explains), a section without the signature, a section count that
    disagrees with the summary -- returns None.
    """
    lines = output.splitlines()
    if any(line.startswith("ERROR ") for line in lines):
        return None
    ids = failed_ids(lines)
    if not ids:
        return None
    sections = failure_sections(_complete_log(output) or output)
    if sections is None or len(sections) != len(ids):
        return None
    if not all(DURATION_FAILURE.search(body) for _, body in sections):
        return None
    if not all(
        any(section_matches(title, nodeid) for title, _ in sections) for nodeid in ids
    ):
        return None
    return ids


def _rerun_alone(ids: list[str]) -> tuple[int, str]:
    """Rerun the failed tests *ids* alone, serially; return exit and output.

    Serial (``-n 0``) and unfiltered (``-m ""``, undoing the step's own mark
    expression) so the rerun measures the tests, not the machine's load or
    the gate's scoping.  Bounded by the pytest step's own deadline: a rerun
    that needs longer has not exonerated anything.
    """
    command = [*PY, "-m", "pytest", "-q", "-n", "0", "-m", "", *ids]
    started = time.monotonic()
    result = run_bounded(
        command,
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        capture_output=True,
        timeout=STEP_DEADLINES[LONG_STEP],
    )
    output = (result.stdout or "") + (result.stderr or "")
    if _ACTIVE_ACCEPTANCE is not None:
        _ACTIVE_ACCEPTANCE.record(
            "pytest retry",
            time.monotonic() - started,
            result.returncode,
            output,
            command=command,
        )
    return result.returncode, output


def _load_verdict(
    failures: list[tuple[str, int, str | None]],
) -> list[tuple[str, int, str | None]]:
    """Drop a pytest failure the solo rerun proves was load, or say so.

    The duration bands are wall-clock limits, so a loaded machine -- this
    gate's own overlap included -- pushes borderline tests past them without
    anything being wrong with the code.  ``new_language.py`` learned to
    separate those from real failures by rerunning the failures alone; the
    gate reaches the same verdict itself here, because its summary is where
    the reader actually meets the failure.

    The verdict only engages when it cannot hide a real failure: every
    failure must be provably a duration overrun (see
    :func:`_duration_only_ids`), and a deadline's missing output leaves the
    failures untouched.  When the solo rerun still fails, the failure stays
    and the verdict names which tests are real, so the closing summary
    below reads as load casualties plus those names rather than the whole
    list.
    """
    entry = next((f for f in failures if f[0] == LONG_STEP), None)
    if entry is None or entry[2] is None:
        return failures
    ids = _duration_only_ids(entry[2])
    if ids is None:
        return failures
    returncode, rerun_output = _rerun_alone(ids)
    if returncode == 0:
        if _ACTIVE_ACCEPTANCE is not None:
            _ACTIVE_ACCEPTANCE.accepted_retries.add(LONG_STEP)
        print(
            f"[load] pytest: all {len(ids)} failed tests passed alone: the "
            "failures were duration overruns under machine load, not code; "
            "rerun the gate on a quiet machine before pushing"
        )
        return [failure for failure in failures if failure[0] != LONG_STEP]
    still = failed_ids(rerun_output.splitlines())
    named = still or ids
    print(
        f"[load] pytest: {len(named)} of {len(ids)} failures still fail "
        f"alone: {', '.join(named)}"
    )
    return failures


def _ensure_dev_deps() -> None:
    """Sync development dependencies unless VERIFY_NO_SYNC opts out."""
    if os.environ.get("VERIFY_NO_SYNC", "0") in ("", "0"):
        run_bounded(["uv", "sync", "--group", "dev"], cwd=ROOT, check=True)


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


def _drop_long_step_after_mutation_failure(
    failed: list[tuple[str, int, str | None]],
    rest: list[tuple[str, list[str], dict[str, str]]],
) -> list[tuple[str, list[str], dict[str, str]]]:
    """Skip the long step when the tree-mutating step just rewrote the tree.

    The cheap steps still report, but pytest would spend ~150 s on a
    tree the hooks just rewrote and the fix will rewrite again: six
    sessions waited it out for a one-line ruff fix.
    """
    if not any(name == MUTATES_TREE for name, *_ in failed):
        return rest
    if any(step[0] == LONG_STEP for step in rest):
        print(f"[skip] {LONG_STEP}: {MUTATES_TREE} failed; fix it and rerun")
        rest = [step for step in rest if step[0] != LONG_STEP]
    return rest


def _run_shadow_phase(
    long_step: tuple[str, list[str], dict[str, str]] | None,
    shadow: list[tuple[str, list[str], dict[str, str]]],
    heavy: list[tuple[str, list[str], dict[str, str]]],
    *,
    stream: bool,
    run_serial: Callable[..., None],
    record: Callable[..., None],
) -> list[tuple[str, list[str], dict[str, str]]]:
    """Launch the long step and run the cheap ones in its shadow.

    Returns the heavy steps still owed a serial phase: when the shadow
    ran on threads, the heavy steps already ran alongside it.
    """
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
    return heavy


def _run_steps(
    runnable: list[tuple[str, list[str], dict[str, str]]],
    *,
    stream: bool,
) -> tuple[list[tuple[str, int, str | None]], list[tuple[str, float]], float]:
    """Run the planned steps, overlapping the long one with the cheap ones.

    ``pre-commit`` finishes before readers start. Captured runs overlap
    pytest with the leak sweep and one serial shadow lane. Streaming runs
    leave the sweep until afterwards to keep terminal output coherent.

    Output is captured and replayed only on failure unless *stream*.  A step
    that is holding the terminal alone can stream it live instead; two can
    not, since concurrent writers interleave into nonsense.

    Returns the failed steps with their exit codes and captured output,
    per-step CPU timings, and the wall time, which concurrency makes smaller
    than the timings' sum.
    """
    if _ACTIVE_ACCEPTANCE is not None:
        _ACTIVE_ACCEPTANCE.declare(runnable)
    failed: list[tuple[str, int, str | None]] = []
    timings: list[tuple[str, float]] = []
    wall_start = time.monotonic()

    def record(name: str, elapsed: float, returncode: int, output: str | None) -> None:
        if _ACTIVE_ACCEPTANCE is not None:
            _ACTIVE_ACCEPTANCE.record(name, elapsed, returncode, output)
        timings.append((name, elapsed))
        if not _report(name, elapsed, returncode, output):
            failed.append((name, returncode, output))

    def run_serial(name: str, cmd: list[str], step_env: dict[str, str]) -> None:
        start = time.monotonic()
        captured, returncode = _wait_with_heartbeat(
            start_logged(cmd, name, step_env, ROOT, stream=stream),
            name,
            start,
        )
        record(name, time.monotonic() - start, returncode, captured)

    for name, cmd, step_env in runnable:
        if name == MUTATES_TREE:
            run_serial(name, cmd, step_env)
    rest = _drop_long_step_after_mutation_failure(
        failed, [step for step in runnable if step[0] != MUTATES_TREE]
    )

    # Phase 2: launch the long step, then run the cheap ones in its shadow.
    long_step = next((s for s in rest if s[0] == LONG_STEP), None)
    shadow = [s for s in rest if s[0] != LONG_STEP and s[0] not in HEAVY_STEPS]
    heavy = [s for s in rest if s[0] in HEAVY_STEPS]
    heavy = _run_shadow_phase(
        long_step,
        shadow,
        heavy,
        stream=stream,
        run_serial=run_serial,
        record=record,
    )

    # Phase 3: the parallel steps, now that they can have the machine.
    for name, cmd, step_env in heavy:
        run_serial(name, cmd, step_env)

    return failed, timings, time.monotonic() - wall_start


def _pytest_cmd(cmd: list[str], *, full: bool, changed: list[str]) -> list[str]:
    """Return the default run's pytest command: its marks, timings and deferrals."""
    # A default run leaves the slow band to CI; --full takes it but
    # not the `weekly` probes, which only weekly.yml runs.
    #
    # The `slow` marker covers the generator derivations and fuzz loops
    # whose cost is seconds each.  Deselecting them locally trades no
    # coverage, because the sharded `slow` job runs every marked test
    # on every push.  This is keyed on --full rather than on scoping
    # because a run that widens back to everything -- a tooling change,
    # an unreadable diff -- should still not pay for them.
    #
    # language-owners: ["Line"]
    # The tests/interpreters suites carry the same marker on their two 5.2s tests
    # (the eight-level nesting round trip and the n=5 parity table), which
    # are 10.4s of that step's 12.8s.  CI's `line` job runs that suite
    # unfiltered on every push, so deselecting them here trades no
    # coverage either.
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
            ]
        )
    if not full and not verify_full():
        deferred = local_tooling_deselections(changed)
        cmd.extend(deferred)
        if deferred:
            print("[defer] unrelated tooling integrations: covered by CI")
    return cmd


def main() -> int:
    """Run the verification stack: lint, types, tests, and scoping."""
    only, skip, full, quiet, verbose = _parse_only_skip()

    # `--list` exits inside the parse, so this never slows it down.
    _ensure_dev_deps()

    # An explicit --only is already a hand-picked subset; scoping it further
    # would silently drop steps the caller asked for by name.
    unscoped, why = (True, "--only given") if only else _scope_plan(full=full)
    whole = only is not None or full or verify_full()
    changed = [] if whole else list(_scope_changed_files())
    if unscoped:
        print(f"scope: full run ({why})")
    else:
        print(f"scope: changed files ({why})")

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    if _ACTIVE_ACCEPTANCE is not None:
        _ACTIVE_ACCEPTANCE.capture_environment(PY, env)
    # Decide every step first, then run.  Deciding is pure bookkeeping (scope
    # lookups, tool probes) while running is where the time goes, so keeping
    # the two apart lets the runner overlap the long step with the short ones
    # without the skip logic having to care.
    runnable: list[tuple[str, list[str], dict[str, str]]] = []
    for name, raw_cmd in STEPS:
        cmd = raw_cmd
        if only is not None and name not in only:
            continue
        if skip is not None and name in skip:
            print(f"[skip] {name}: filtered via --skip")
            continue
        if name in MANUAL_ONLY and only is None:
            print(f"[skip] {name}: left to CI; use --only to run locally")
            continue
        if not unscoped:
            narrowed = _scoped_cmd(name, cmd, changed)
            if narrowed is None:
                print(f"[skip] {name}: branch touched none of its files")
                continue
            cmd = narrowed
        elif name == MUTATES_TREE:
            cmd = whole_tree_cmd(cmd)
        step_env = env
        if only is None and name == LONG_STEP:
            cmd = _pytest_cmd(cmd, full=full, changed=changed)
        runnable.append((name, cmd, step_env))

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
    # Between the timings and the summary, where the reader meets a failure:
    # a pytest failure made only of duration overruns gets its solo rerun
    # here, and the verdict may remove it before the summary counts failures.
    failures = _load_verdict(failures)
    print("=" * 40)
    # Last, below the timings: a failing run's tail is where the reader looks.
    for name, returncode, output in failures:
        print(
            f"[FAIL] {name}: {_cause(returncode)}",
            *_located(output),
            *_rerun_hint(name, output),
            sep="\n",
        )
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


def cli() -> int:
    """Run the gate and bind its acceptance receipt to the measured inputs."""
    global _ACTIVE_ACCEPTANCE  # noqa: PLW0603
    if "--list" in sys.argv:
        return main()
    receipt = AcceptanceRun(
        ROOT, sys.argv[1:], {"default": DEFAULT_STEP_DEADLINE, **STEP_DEADLINES}
    )
    _ACTIVE_ACCEPTANCE = receipt
    try:
        returncode = main()
    except BaseException:
        path, _ = receipt.finish(None)
        print(f"[receipt] {path}")
        raise
    finally:
        _ACTIVE_ACCEPTANCE = None
    path, passed = receipt.finish(returncode)
    print(f"[receipt] {path}")
    if returncode == 0 and not passed:
        print("[FAIL] acceptance inputs changed or checks did not complete")
        return 1
    return returncode


if __name__ == "__main__":
    raise SystemExit(cli())
