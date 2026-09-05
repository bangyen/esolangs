"""Mutation-test one boolean generator against the boolean test suites.

The companion to ``scripts/mutate_one.py``, which does this for
interpreters.  The question is the same one line coverage cannot answer:
not whether a test *executed* a line, but whether it would have noticed the
line being wrong.  A generator is a good target for it, because the thing
it emits is a program -- a test that only checks the program *runs* cannot
see a change that leaves it running and computing something else.

Where this differs from ``mutate_one`` is that it does not bundle.
``mutate_one`` inlines the interpreter into one dependency-closed file
because mutating the installed package fails two ways: naming one module
leaves the other 124 unimportable, and copying all of them fires an
import-time trampoline in ``registry``/``lamfunc`` before mutmut has set
``mutmut.config``.  Neither applies here.  Only the *target* file is in
``paths_to_mutate``, so only it gets trampolines; every other module is
copied verbatim and imports normally.  The generator modules also import
cleanly on their own -- ``esolangs.tools.boolean.*`` reaches only
``helpers``, ``text.helpers`` and ``_polynomial``, none of which do work at
import time.

So the layout is the package itself, copied whole into a work directory
that shadows the editable install because the runner's cwd leads
``sys.path``.  That shadowing is the one mechanism worth stating outright:
it has to hold inside ``mutants/`` too, where mutmut chdirs, and it does --
verified by importing the target and printing its ``__file__`` before the
baseline runs, which is the positive control this harness keeps rather than
assumes.

One limit on how a score here should be read: **module-level constants are
not mutated.**  mutmut 3.x mutates function bodies through a trampoline, so
a table defined at module scope -- ``_DIG_BRANCH``, the opcode strings, the
layout tables -- yields no mutants at all.  Several generators keep real
behaviour in exactly those constants, so a high score says the *code* is
covered, not the tables.

The tests are not a limit: every suite in ``tests/tools`` runs, rather than
the ones that name the target.  :func:`_test_files` has the measurement
behind that, and it is the correction this harness needed most -- selecting
by import alone under-reported 19 of the 27 generator modules.

Usage:
    python scripts/mutate_generator.py register
    python scripts/mutate_generator.py dimensional --keep   # leave the work dir

Requires: mutmut==3.7.0, the same pin ``mutate_one`` documents.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# The package the generators live in, and where it sits on disk.
_PKG = "esolangs.tools.boolean"
_PKG_DIR = ROOT / "src" / "esolangs" / "tools" / "boolean"

# The boolean test modules live here.  Only these are copied: pointing
# mutmut at the whole suite made its stats pass collect
# ``tests/fuzz/test_differential_fuzz.py``, which imports ``scripts.*`` and
# so cannot resolve from the work directory -- the run died before
# generating a mutant.
_TESTS_DIR = ROOT / "tests" / "tools"

# Test-support modules the boolean suites import that are not themselves
# tests.  ``tests.interpreters.runner`` is what ``boolean_runners`` drives
# the interpreters through, so a generator's output can be executed.
_SUPPORT = (
    Path("tests/__init__.py"),
    Path("tests/interpreters/__init__.py"),
    Path("tests/interpreters/runner.py"),
)

# The per-test alarm turns a mutant that *hangs* the suite into one that
# fails it.  Both are kills, but a hang costs mutmut's whole
# ``(estimate + 1) * 30`` CPU-second RLIMIT where a failure costs a fraction
# of a second.  Paying off therefore requires the alarm to come in under
# that RLIMIT, which is what the ceiling is for: the baseline here covers
# every suite in tests/tools, so ``elapsed * _ALARM_FACTOR`` off a
# minute-long baseline would sit far above the limit and never fire -- an
# alarm that looks like protection and is dead code.  The floor is the other
# direction: failing a slow-but-passing test reports a kill no mutation
# earned, which is worse than an alarm that rarely fires.  The ceiling is
# measured, not guessed: over the whole of tests/tools with the slow tests
# deselected, 2135 tests run in 39s and the slowest single one is 2.98s, so
# 20s is nearly seven times the worst case while staying well under the
# RLIMIT.  The slow tests have to be deselected in configuration for that
# bound to hold -- see :func:`_pytest_args`.
_ALARM_FACTOR = 10.0
_MIN_ALARM = 5.0
_MAX_ALARM = 20.0

# How long the unmutated suite may take before the run is called stuck.
# Higher than ``mutate_one``'s 120s: a generator's selected suites are the
# whole boolean corpus for that family, where an interpreter's was one file.
_BASELINE_TIMEOUT = 600.0

# Below this share of mutants killed, the run is treated as broken rather
# than reported -- the mutants did not run.  Same reasoning as
# ``mutate_one``: a suite worth mutating does not miss nine mutants in ten.
_MIN_KILL_RATE = 0.1


def _module_path(name: str) -> Path:
    """Return the generator module named ``name``, or raise if absent."""
    path = _PKG_DIR / f"{name}.py"
    if not path.exists():
        names = sorted(p.stem for p in _PKG_DIR.glob("*.py") if p.stem != "__init__")
        raise SystemExit(
            f"unknown generator {name!r}; choose one of: {', '.join(names)}"
        )
    return path


def _test_files() -> list[str]:
    """Return every test module in ``tests/tools``.

    Deliberately not narrowed to the suites that name the target.  Three
    selection rules were tried, and each one under-reported:

    * **By import.**  A suite that imports
      ``esolangs.tools.boolean.<module>`` can kill its mutants -- but most
      suites do not import the module at all.  They import the *package*
      and reach the generator through its re-export (``boolean.laserfuck``),
      which no import scan can see.  Measured over the 27 generator
      modules, importing alone under-selected 19 of them: every ``rotfuck``
      test lives in ``test_boolean_tape``, which imports only ``boolean``.
    * **By import, plus the contract suite always.**  Better -- the contract
      suite is where several generators are checked -- but it fixes only
      the one file that was noticed, and 19 modules were short by more than
      that file.
    * **By attribute access**, resolving ``boolean.<name>`` back to the
      module that defines it.  This catches the re-export, and still misses
      a suite that dispatches through a string or a table.
      ``test_generate`` is that shape, and it reaches 19 of the 27 modules.

    So selection is a glob, which has no blind spot to construct a
    refutation for.  Breadth is nearly free here because mutmut does not
    run this whole set per mutant: its stats pass records which tests
    execute which functions, and each mutant then runs only the tests that
    cover it.  The dimensional run is the measurement -- a ~2s suite, and
    9 mutants at 24 mutations/second.  A suite that never touches the
    target costs one stats-pass run, not one run per mutant.
    """
    return sorted(path.name for path in _TESTS_DIR.glob("test_*.py"))


# A decorator line on a class, and the class statement it applies to.
_DECORATED_CLASS = re.compile(
    r"^(?P<decorators>(?:@[^\n(]+(?:\([^\n]*\))?\n)+)class (?P<name>\w+)", re.M
)


def _undecorate_classes(target: Path) -> list[str]:
    """Rewrite ``@d`` on a class into ``Class = d(Class)`` after its body.

    mutmut skips any ``ClassDef`` carrying decorators, so a ``@dataclass``
    state class yields no mutants while the run still prints a percentage.
    ``tape.py`` is exactly this shape -- five decorated dataclasses
    (``_Cmd``, ``_If``, ``_MoveLeft``, ``_Out``, ``_End``) that model the
    emitted program -- and ``examples.py`` has another.

    Applying the decorator as a plain call below the class is what the
    decorator syntax means, so the class behaves identically, but the
    ``ClassDef`` mutmut parses no longer has decorators and its methods are
    mutated like any other.  Only classes are rewritten: a decorated
    *method* keeps its decorator, since ``@property`` is precisely what the
    trampoline cannot take.

    This is ``mutate_one._undecorate_classes``, which operates on a bundle
    where this one operates on a copied module.  Returns the decorators
    moved, for the note the caller prints.
    """
    text = target.read_text()
    moved: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        name = match.group("name")
        decorators = match.group("decorators").strip().splitlines()
        moved.extend(f"{d.lstrip('@')} to {name}" for d in decorators)
        return f"class {name}"

    new = _DECORATED_CLASS.sub(rewrite, text)
    if not moved:
        return []

    # The calls go at the end of the module, after every class body has been
    # defined, innermost decorator first -- the order the syntax applies them.
    applied = "\n".join(
        f"{name} = {decorator}({name})"
        for entry in moved
        for decorator, name in [entry.split(" to ")]
    )
    target.write_text(f"{new}\n\n{applied}\n")
    return moved


_CONFTEST = '''"""mutmut workarounds, all of which otherwise fail silently.

1. ``set_start_method`` raises on the second call under macOS + Python 3.12,
   which aborts the run rather than the mutant.
2. A mutant that turns a loop condition around does not fail the suite, it
   hangs it, and mutmut only reclaims a hung mutant at its RLIMIT_CPU of
   ``(estimate + 1) * 30`` CPU-seconds.  Such a mutant is killed either way
   -- a generator that never returns is a caught bug -- but at ~30
   CPU-seconds instead of the fraction of a second an ordinary kill costs.

   The budget is passed in rather than hardcoded, because "too long" is a
   property of the suite: the caller derives it from the measured baseline,
   and when the variable is absent no alarm is installed -- which leaves
   the harness's own baseline run, and any other use of these tests,
   untouched.
"""

import contextlib
import multiprocessing
import os
import signal

import pytest

_orig = multiprocessing.set_start_method


def _patched(method, force=False):
    with contextlib.suppress(RuntimeError):
        _orig(method, force=force)


multiprocessing.set_start_method = _patched

_budget = float(os.environ.get("MUTATE_GENERATOR_ALARM", "0"))


def _expired(signum, frame):
    raise TimeoutError(f"exceeded the {_budget:g}s per-test budget")


if _budget:

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(item, nextitem):
        """Fail a test that outruns the budget instead of hanging on it."""
        signal.signal(signal.SIGALRM, _expired)
        signal.setitimer(signal.ITIMER_REAL, _budget)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
'''

# mutmut parses each file into an AST to build its mutants, and the parsing
# runs in spawned children on macOS -- so the limit has to be raised at
# interpreter startup, which is what a sitecustomize on PYTHONPATH does.
# The generator modules are much larger than an interpreter (%^2^-1 is 3337
# lines), so this matters more here than it did there.
_SITECUSTOMIZE = "import sys\n\nsys.setrecursionlimit(50000)\n"


def _pytest_args(tests: list[str]) -> list[str]:
    """Return the pytest arguments, as a list, that the runs share.

    Deliberately free of ``-m``.  Deselecting the slow tests belongs in the
    work directory's ``addopts`` instead, because mutmut's stats pass runs
    pytest with its *own* arguments rather than the runner's -- so a ``-m``
    here filtered the baseline and the mutant runs while the stats pass
    collected the slow tests regardless.  ``test_minifuck_builds_five_input
    _xor`` is a 4s build that then ran under mutmut's tracing, blew the
    per-test alarm, and failed the stats pass; every mutant was scored 0.
    Configuration is honoured by all three passes, an argument is not.

    ``-n 0`` is not optional either.  The repo's ``addopts`` pins ``-n 4``,
    so without it every one of a few thousand mutants would spawn four xdist
    workers -- to run a suite that takes seconds.
    """
    return ["-x", "-q", "-p", "no:cacheprovider", "-n", "0"] + [
        f"tests/tools/{name}" for name in tests
    ]


def _runner_command(tests: list[str]) -> str:
    """Return the same arguments as the shell command line mutmut runs.

    mutmut takes its runner as a string and splits it with ``shlex``, so an
    argument containing a space has to be quoted rather than merely joined.
    """
    return "python -m pytest " + shlex.join(_pytest_args(tests))


def _prepare(module: str, work: Path, *, slow: bool) -> tuple[Path, list[str]]:
    """Lay out the work directory; return (project dir, selected test files).

    The whole package is copied rather than bundled, so every import the
    generator makes resolves exactly as it does in the repo.  Only the
    target file is named in ``paths_to_mutate``.
    """
    proj = work / "proj"
    proj.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")

    shutil.copytree(ROOT / "src" / "esolangs", proj / "esolangs", ignore=ignore)
    for rel in _SUPPORT:
        dest = proj / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)

    tests = _test_files()
    tools = proj / "tests" / "tools"
    tools.mkdir(parents=True)
    # Every module in tests/tools is copied, not just the selected suites:
    # the ones that are not tests are helpers the selected suites import
    # (``boolean_runners``, the APA trace and proof checkers), and a missing
    # one fails collection rather than a mutant.
    for path in _TESTS_DIR.glob("*.py"):
        shutil.copy(path, tools / path.name)
    (tools / "conftest.py").write_text(_CONFTEST)

    # Several suites read a shipped example, and the APA checkers read the
    # fixtures.  Both are resolved relative to the test file's parents, which
    # lands in proj for the baseline and in mutants/ for the mutation runs --
    # so both need the link.  Link rather than copy: nothing here is mutated.
    for base in (proj, proj / "mutants"):
        base.mkdir(parents=True, exist_ok=True)
        (base / "examples").symlink_to(ROOT / "examples")
    (proj / "tests" / "fixtures").symlink_to(ROOT / "tests" / "fixtures")

    target = proj / "esolangs" / "tools" / "boolean" / f"{module}.py"
    moved = _undecorate_classes(target)
    if moved:
        print(
            f"[note] applied {', '.join(moved)} after the class body "
            "so mutmut can see it"
        )

    rel_target = f"esolangs/tools/boolean/{module}.py"
    runner = _runner_command(tests)
    # In addopts rather than in the runner's arguments, so that mutmut's
    # stats pass -- which supplies its own -- deselects these too.
    addopts = "" if slow else 'addopts = ["-m", "not slow"]\n'
    (proj / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        f'paths_to_mutate = ["{rel_target}"]\n'
        # mutmut copies only what it mutates into mutants/, so the rest of
        # the package and the tests have to be carried across explicitly or
        # every mutant dies on an import the baseline resolves fine.
        'also_copy = ["esolangs/", "tests/"]\n'
        "backup = false\n"
        f'runner = "{runner}"\n'
        # ``tests/tools`` rather than ``tests``.  mutmut's stats pass
        # collects this path ignoring the runner's own arguments, and the
        # wider path swept in ``tests/fuzz/test_differential_fuzz.py``,
        # which imports ``scripts.*`` and cannot resolve from the work
        # directory -- the run died before generating a mutant.
        'tests_dir = ["tests/tools"]\n'
        "\n"
        # The work dir has its own pyproject, so the repo's pytest config
        # does not apply and the markers the suites use must be re-declared
        # -- ``--strict-markers`` is not in force here, but an unregistered
        # mark still warns on every one of thousands of mutant runs.
        "[tool.pytest.ini_options]\n"
        "markers = [\n"
        '    "slow: marks tests as slow",\n'
        '    "integration: marks tests as integration tests",\n'
        "]\n" + addopts
    )
    (work / "sitecustomize.py").write_text(_SITECUSTOMIZE)
    return proj, tests


def _check_shadowing(proj: Path, module: str) -> None:
    """Fail unless the copied package is what an import in ``proj`` resolves to.

    This is the positive control, and it is the one thing about this layout
    that cannot be verified by reading.  ``mutate_one`` sidesteps the
    question with a flat single file; a package copy instead relies on the
    runner's cwd leading ``sys.path``, so that the copy shadows the editable
    install.  If it ever stopped holding, every mutant would run against the
    *repo's* generator, nothing would fail, and the run would report a
    perfect score having tested nothing.  A score of 100% is exactly what
    this failure looks like, which is why it is checked rather than assumed.
    """
    dotted = f"{_PKG}.{module}"
    code = (
        "import sys, importlib; "
        f"importlib.import_module({dotted!r}); "
        f"print(sys.modules[{dotted!r}].__file__)"
    )
    got = subprocess.run(
        [sys.executable, "-c", code],
        cwd=proj,
        capture_output=True,
        text=True,
        check=False,
    )
    if got.returncode != 0:
        raise SystemExit(f"could not import {dotted} from the work dir:\n{got.stderr}")
    # Both sides are resolved before comparing: on macOS the temp directory
    # is handed out as ``/var/...`` and reported back as ``/private/var/...``,
    # which compares unequal while naming the same file.
    resolved = Path(got.stdout.strip()).resolve()
    if not resolved.is_relative_to(proj.resolve()):
        raise SystemExit(
            f"{dotted} resolved to {resolved}, outside the work directory.  The "
            "copied package is not shadowing the installed one, so the mutants "
            "would run against the repo and every one would survive undetected."
        )


def _score(proj: Path, module: str) -> tuple[int, int, list[str]]:
    """Return (killed, total, survivor names) from mutmut's own result file.

    Simpler than ``mutate_one._score``: only the target file is mutated, so
    every mutant in the meta belongs to it and there is nothing to filter
    out.  ``mutate_one`` needs a class-ownership filter because its bundle
    inlines two other modules alongside the interpreter.
    """
    meta_path = (
        proj / "mutants" / "esolangs" / "tools" / "boolean" / f"{module}.py.meta"
    )
    if not meta_path.exists():
        raise SystemExit(
            f"mutmut wrote no result file at {meta_path}: the run did not get "
            "as far as generating mutants."
        )
    codes = json.loads(meta_path.read_text())["exit_code_by_key"]
    killed = sum(1 for v in codes.values() if v)
    return killed, len(codes), sorted(k for k, v in codes.items() if not v)


def main() -> int:
    """Copy the package, mutate one generator, and report what survived."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("module", help="generator module, e.g. register")
    parser.add_argument(
        "--keep", action="store_true", help="leave the work directory in place"
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="include tests marked slow.  They are deselected by default: a "
        "mutation run pays the suite's cost once per mutant, so a test that "
        "adds seconds to the baseline adds hours to the run",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="mutants to run at once (default 4; mutmut's own default is "
        "every core, which saturates the machine for the whole run)",
    )
    args = parser.parse_args()

    _module_path(args.module)
    work = Path(tempfile.mkdtemp(prefix="mutate-generator-"))
    try:
        proj, tests = _prepare(args.module, work, slow=args.slow)
        print(f"[note] selected {len(tests)} test file(s): {', '.join(tests)}")
        _check_shadowing(proj, args.module)
        print("[note] the copied package shadows the installed one")

        started = time.monotonic()
        try:
            baseline = subprocess.run(
                [sys.executable, "-m", "pytest", *_pytest_args(tests)],
                cwd=proj,
                capture_output=True,
                text=True,
                check=False,
                timeout=_BASELINE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise SystemExit(
                f"the selected tests did not finish in {_BASELINE_TIMEOUT:g}s.  "
                "Either a test loops without the bound its helper gave it, or "
                "the harness itself is stuck before pytest -- sample the "
                "process to tell which."
            ) from None
        elapsed = time.monotonic() - started
        if baseline.returncode != 0:
            print(baseline.stdout[-3000:])
            raise SystemExit("the selected tests fail before any mutation")

        budget = min(_MAX_ALARM, max(_MIN_ALARM, elapsed * _ALARM_FACTOR))
        print(f"[note] baseline {elapsed:.2f}s; capping each test at {budget:.1f}s")

        env = {
            "PYTHONPATH": str(work),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MUTATE_GENERATOR_ALARM": f"{budget:.3f}",
        }
        mutation = subprocess.run(
            [sys.executable, "-m", "mutmut", "run", "--max-children", str(args.jobs)],
            cwd=proj,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=False,
        )

        killed, total, survivors = _score(proj, args.module)
        if not total:
            raise SystemExit("no mutants were generated")
        if killed < total * _MIN_KILL_RATE:
            # An exit code still at its initial 0 means that mutant never
            # reported, which a suite that passes its baseline cannot cause.
            print(mutation.stdout[-3000:] or mutation.stderr[-3000:])
            raise SystemExit(
                f"only {killed} of {total} mutants killed with a passing "
                "baseline: the mutants did not run.  Check the output above "
                "-- usually the suite fails inside mutants/, where it runs "
                "from a different directory than the baseline."
            )
        print(f"\n{args.module}: {killed}/{total} killed ({100 * killed / total:.1f}%)")
        if survivors:
            print(f"\n{len(survivors)} survived:")
            for name in survivors:
                print(f"  {name}")
            print(
                "\nA survivor is an equivalent mutant or a gap; read the diff "
                "before writing a test for it.  Note that module-level tables "
                "are never mutated, so they are covered by neither number."
            )
        return 0
    finally:
        if args.keep:
            print(f"\nwork dir: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
