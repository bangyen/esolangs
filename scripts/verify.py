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
RISC-V unicorn round-trip, which CI's assembly job runs) and
pytest's ``slow`` marker (the fuzzers' divergence-detection tests,
which CI runs by that same marker and errors on if they skip).  ``--full``,
``just test-full``, and an explicit ``--only`` all still run them.

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

# Which paths each step actually guards.  A step whose prefixes the branch did
# not touch cannot have been broken by that branch, so a scoped run skips it.
# A step absent from this table is always run: it is either cheap enough not to
# matter or it guards the whole tree.  Prefixes are repo-relative.
STEP_SCOPE: dict[str, tuple[str, ...]] = {
    "bandit": ("src/",),
    "extra/line suites (uv)": ("extra/line/",),
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
    ("pytest", [*PY, "-m", "pytest", "-q"]),
    ("bandit", ["uv", "run", "--with", "bandit", "bandit", "-r", "src", "-q"]),
    (
        # Run from extra/line: its modules import each other as flat top-level
        # names, and it needs image libraries the package does not depend on,
        # so they are supplied ad hoc rather than from the project env.
        "extra/line suites (uv)",
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--directory",
            "extra/line",
            "--with",
            "pillow",
            "--with",
            "numpy",
            "--with",
            "scipy",
            "--with",
            "scikit-image",
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

    failures = 0
    timings: list[tuple[str, float]] = []
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
        if name == "pytest" and only is None and not full:
            cmd = [*cmd, "-m", "not slow"]
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
        start = time.time()
        result: subprocess.CompletedProcess[Any]
        if quiet:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if result.returncode != 0 and result.stdout:
                print(result.stdout, end="")
        else:
            result = subprocess.run(cmd, env=env)
        elapsed = time.time() - start
        timings.append((name, elapsed))
        ok = result.returncode == 0
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {name} ({elapsed:.1f}s)")

    if timings:
        print("-" * 40)
        for name, elapsed in timings:
            print(f"{elapsed:5.1f}s  {name}")
        total = sum(t for _, t in timings)
        print(f"{total:5.1f}s  TOTAL")
    print("=" * 40)
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
