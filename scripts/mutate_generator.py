"""Mutation-test one generator against the suite that covers it.

The companion to ``scripts/mutate_one.py``, which does this for
interpreters.  The question is the same one line coverage cannot answer:
not whether a test *executed* a line, but whether it would have noticed the
line being wrong.  A generator is a good target for it, because the thing
it emits is a program -- a test that only checks the program *runs* cannot
see a change that leaves it running and computing something else.

Three kinds of target share this harness, differing only in where their
source and tests live (see ``_KINDS``): the ``boolean`` generator family
under ``esolangs.tools``, the modules directly under ``esolangs.tools``,
and ``core`` -- the package root, where ``vm``, ``debug``, ``tui`` and
``cli`` sit.

One blind spot belongs to the harness rather than to any suite, and the
``core`` kind is where it shows: **a function called only while its module
is imported cannot be mutated**.  mutmut switches variants through a
trampoline that reads its config at call time, and an import has already
happened by then, so the original ran.  ``vm.py``'s ``_derived_adapter`` is
the case -- ``_VM_ADAPTERS`` is a module-level comprehension over all 69
languages -- and all 43 of its mutants survive, including ones that would
raise on any call.  They are not a gap in the tests, which construct VMs
for every language; they are unreachable by the tool.  Read a ``core``
score with that subtracted, and do not restructure a module to suit it.

That third kind is here rather than in ``mutate_one`` because
``mutate_one`` cannot reach it.  It mutates a *bundle*, an interpreter
inlined with its shared modules into one dependency-closed file, and its
own docstring says tests reaching past the interpreter into the VM or the
registry cannot run against one.  The core modules are the top of that
stack rather than a leaf, so bundling one would mean inlining the package
-- and not bundling is precisely what this harness already does.

Where this differs from ``mutate_one`` is that it does not bundle.
``mutate_one`` inlines the interpreter into one dependency-closed file
because mutating the installed package fails two ways: naming one module
leaves the other 124 unimportable, and copying all of them fires an
import-time trampoline in ``registry``/``lamfunc`` before mutmut has set
``mutmut.config``.  Neither applies here.  Only the *target* file is in
``paths_to_mutate``, so only it gets trampolines; every other module is
copied verbatim and imports normally.  The generator modules also import
cleanly on their own -- ``esolangs.tools.boolean.*`` reaches only
``helpers``, ``wrap``, ``_polynomial``, ``laserfuck_layout`` and
``ztoalc_starts``.  None of them do work at import time, which is what lets
both kinds share this layout.

So the layout is the package itself, copied whole into a work directory
that shadows the editable install because the runner's cwd leads
``sys.path``.  The shadowing has to hold inside ``mutants/`` too, where
mutmut chdirs, and it does -- verified by importing the target and printing
its ``__file__`` before the baseline runs, the positive control this harness
keeps rather than assumes.

One limit on how a score here should be read: **module-level constants are
not mutated.**  mutmut 3.x mutates function bodies through a trampoline, so
a table defined at module scope -- ``_DIG_BRANCH``, the opcode strings, the
layout tables -- yields no mutants at all.  Several generators keep real
behaviour in exactly those constants, so a high score says the *code* is
covered, not the tables.

The tests are not a limit: every suite in the kind's test directory runs,
rather than the ones that name the target.  :func:`_test_files` has the
measurement behind that -- the correction this harness needed most, since
selecting by import alone under-reported 19 of the 27 generator modules.

Every kind is reachable as ``family/module``.  Eight module names --
helpers, laserfuck, other, register, stack, streetcode, super_snusp, tape
-- exist in *both* generator packages, so a bare name is accepted only
where it is unambiguous; see :func:`_parse_target`.

Usage:
    python scripts/mutate_generator.py boolean/register
    python scripts/mutate_generator.py boolean/streetcode
    python scripts/mutate_generator.py dimensional --keep   # leave the work dir

Requires: mutmut==3.7.0, the same pin ``mutate_one`` documents.
"""

import argparse
import ast
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

# Test-support modules the suites import that are not themselves tests.
# ``tests.interpreters.runner`` is what ``boolean_runners`` drives the
# interpreters through, so a generator's output can be executed, and
# ``tests.raises`` is a helper the generator suites import at module scope.
#
# ``tests.raises`` was missing once, and the way it surfaced is worth
# keeping: every suite in ``tests/tools`` is copied, so the *file* was
# there, but ``tests/raises.py`` sits one level up and was not -- so the
# suite failed to import and the baseline gate stopped the run.  That gate
# is the reason this cost minutes rather than a wrong number: a missing
# support module fails collection, and with ``tests_dir`` pointing at
# ``tests/tools`` a silently uncollected suite would have scored its
# generators against the remaining ones alone.
_TOOLS_SUPPORT = (
    Path("tests/__init__.py"),
    Path("tests/raises.py"),
    Path("tests/interpreters/__init__.py"),
    Path("tests/interpreters/runner.py"),
)

# The root suites' own reach outside ``tests/``.  ``tests/*.py`` is copied
# wholesale by the layout, so ``samples``, ``raises`` and ``conftest`` come
# along on their own; what does not is the subpackage they reach into --
# ``samples`` imports a truth machine out of an interpreter's *test* file,
# which is why one of those is here rather than only its helpers.
_CORE_SUPPORT = (
    Path("tests/interpreters/__init__.py"),
    Path("tests/interpreters/runner.py"),
    Path("tests/interpreters/test_inject.py"),
    Path("tests/interpreters/contract.py"),
)


class _Kind:
    """Where one mutable family's source, tests and support files live.

    The kinds differ only in these paths, so they are a table rather
    than separate code paths.  Every one satisfies the two preconditions the
    layout relies on: each module imports cleanly on its own, and nothing it
    reaches does work at import time.  ``boolean.*`` reaches only
    ``helpers``, ``wrap``, ``_polynomial``, ``laserfuck_layout`` and
    ``ztoalc_starts``, which the copied package resolves like any other
    import.

    ``tests_dir`` is deliberately narrow: pointing mutmut at the whole
    suite widens its stats pass past the tests that actually cover the
    target.
    """

    def __init__(
        self,
        name: str,
        pkg_rel: str,
        tests_rel: str,
        support: tuple[Path, ...],
        *,
        needs_scripts: bool = False,
        skip_tests: frozenset[str] = frozenset(),
    ) -> None:
        self.name = name
        self.pkg_rel = pkg_rel  # under src/esolangs, e.g. "tools/boolean"
        self.tests_rel = tests_rel  # e.g. "tests/tools"
        self.support = support
        # Whether the suite reaches scripts/.
        self.needs_scripts = needs_scripts
        # Suites that cannot run against a *copy* of the package, because
        # they anchor to the repository's own layout rather than to what is
        # importable.  Kept as small and as named as possible: a glob with
        # no exceptions is the goal, and every name here owes a reason.
        self.skip_tests = skip_tests

    @property
    def pkg_dir(self) -> Path:
        """Return where this kind's modules sit on disk."""
        base = ROOT / "src" / "esolangs"
        return base / self.pkg_rel if self.pkg_rel else base

    @property
    def tests_dir(self) -> Path:
        """Return where this kind's test modules sit on disk."""
        return ROOT / self.tests_rel

    def dotted(self, module: str) -> str:
        """Return the dotted module name a target resolves to."""
        # An empty ``pkg_rel`` is the package root itself, where ``vm`` and
        # the rest of the top-of-stack modules live; joining it blindly
        # would ask for ``esolangs..vm``.
        parts = ["esolangs", *self.pkg_rel.split("/"), module]
        return ".".join(part for part in parts if part)

    def rel_target(self, module: str) -> str:
        """Return the path mutmut mutates, relative to the work directory."""
        parts = ["esolangs", *self.pkg_rel.split("/"), f"{module}.py"]
        return "/".join(part for part in parts if part)


# Keyed by the name the CLI takes.
_KINDS = {
    "boolean": _Kind("boolean", "tools/boolean", "tests/tools", _TOOLS_SUPPORT),
    # The modules directly under ``esolangs.tools`` rather than in a family
    # package -- ``wrap`` and the layout helpers.  The glob picks up only
    # files, so the ``boolean`` subpackage is not swept in twice.
    "tools": _Kind("tools", "tools", "tests/tools", _TOOLS_SUPPORT),
    # The package root: ``vm``, ``debug``, ``tui``, ``cli``, ``registry``.
    #
    # These are the modules ``mutate_one`` cannot reach.  It mutates a
    # *bundle* -- an interpreter inlined with its shared modules into one
    # dependency-closed file -- and says so: tests that reach past the
    # interpreter into the VM or the registry cannot run against one.  These
    # sit at the top of that stack rather than at a leaf, so bundling one
    # would mean inlining the package.  Not bundling is exactly what this
    # harness already does.
    #
    # They satisfy the same two preconditions as the other kinds: each
    # imports cleanly on its own, and the import-time trampoline the
    # docstring warns about fires only for a module named in
    # ``paths_to_mutate``, which is one target at a time.
    "core": _Kind(
        "core",
        "",
        "tests",
        _CORE_SUPPORT,
        # One suite reads the *repository* rather than the package:
        # ``test_interpreter_conventions`` walks ``src/esolangs/interpreters``
        # as a directory to ask a question about source shape, which the
        # copied tree does not have and which covers no ``core`` module.
        #
        # The README-reading suites are *not* here.  They are given the file
        # instead -- see the symlink in ``_prepare`` -- because several of
        # them check that the README documents the CLI, and ``cli`` is a
        # target of this kind.  Skipping them would have quietly stopped
        # measuring the thing they cover.
        # These are the root suite's *repository* meta-tests, and they are
        # a class rather than a list of accidents: each asserts something
        # about the checkout -- the shape of the interpreter tree, how the
        # package is declared, that every test a docstring cites exists --
        # and a copied work directory is none of those things.  They cover
        # no ``core`` module, and linking a file or two cannot make a
        # temporary directory into a repository.
        #
        # The suites that merely *read* a repository file are not here;
        # those are given the file, above.  The difference is whether the
        # subject is the file or the checkout.
        # ``test_answer_plumbing`` is here for a different reason and it is
        # worth keeping separate: it times a termination proof against a
        # millisecond bound, and this harness runs its suite under tracing
        # for the stats pass and alongside three other mutants after it.
        # A wall-clock margin measured on an idle machine does not survive
        # that, and a timing flake would be scored as a kill.
        skip_tests=frozenset(
            {
                "test_interpreter_conventions.py",
                "test_cli_conventions.py",
                "test_documented_commands.py",
                "test_answer_plumbing.py",
            }
        ),
    ),
}

_FAMILIES = tuple(_KINDS)

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
# bound to hold -- see :func:`_pytest_args` -- so under ``--slow`` the
# ceiling is dropped rather than applied to tests it was not measured over.
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


# Modules in a family package that are not generators.  ``__init__`` is the
# re-export surface and ``__main__`` a ``python -m`` entry point; neither
# holds generation logic worth a mutant.  ``helpers`` is deliberately *not*
# here: it is shared machinery the output depends on, so it is a real
# target.
_NON_TARGETS = frozenset({"__init__", "__main__"})


def _modules(family: str) -> list[str]:
    """Return the mutable module names in ``family``, sorted."""
    return sorted(
        p.stem
        for p in _KINDS[family].pkg_dir.glob("*.py")
        if p.stem not in _NON_TARGETS
    )


def _parse_target(target: str) -> tuple[str, str]:
    """Return the (family, module) a CLI target names, or raise.

    Accepts ``boolean/streetcode`` and the bare ``streetcode``.  A bare name
    is resolved against every kind, which makes it an error rather than a
    silent choice when more than one matches -- ``helpers`` is in both
    ``tools`` and ``tools/boolean``.  Bare names that are unambiguous still
    work, so ``mutate_generator.py minifuck`` needs no qualifier.
    """
    if "/" in target:
        family, _, module = target.partition("/")
        if family not in _FAMILIES:
            raise SystemExit(
                f"unknown generator family {family!r}; "
                f"choose one of: {', '.join(_FAMILIES)}"
            )
        if module not in _modules(family):
            raise SystemExit(
                f"unknown {family} generator {module!r}; "
                f"choose one of: {', '.join(_modules(family))}"
            )
        return family, module

    matches = [family for family in _FAMILIES if target in _modules(family)]
    if not matches:
        listing = "\n".join(
            f"  {family}: {', '.join(_modules(family))}" for family in _FAMILIES
        )
        raise SystemExit(f"unknown generator {target!r}; choose one of:\n{listing}")
    if len(matches) > 1:
        spellings = ", ".join(f"{family}/{target}" for family in matches)
        raise SystemExit(
            f"{target!r} names a generator in more than one family; "
            f"say which: {spellings}"
        )
    return matches[0], target


def _test_files(kind: _Kind) -> list[str]:
    """Return every test module in this kind's test directory.

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
      a suite that dispatches through a string or a table, which some
      of these do.

    So selection is a glob, which has no blind spot to construct a
    refutation for.  Breadth is nearly free here because mutmut does not
    run this whole set per mutant: its stats pass records which tests
    execute which functions, and each mutant then runs only the tests that
    cover it.  The dimensional run is the measurement -- a ~2s suite, and
    9 mutants at 24 mutations/second.  A suite that never touches the
    target costs one stats-pass run, not one run per mutant.
    """
    return sorted(
        path.name
        for path in kind.tests_dir.glob("test_*.py")
        if path.name not in kind.skip_tests
    )


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

    # The rewrite only works for a class the module does not *use* while it
    # is still importing.  The calls below go at the end, so a module body
    # that constructs one has already run against the undecorated class --
    # ``registry.py`` builds ``LANGUAGES`` out of ``Language(...)`` and
    # fails with "Language() takes no arguments", which says nothing about
    # what went wrong.  Refuse with the reason instead.
    #
    # Moving the calls up to each class body would trade this for a worse
    # problem: a decorator naming another class in the same module would
    # then run before that class exists.
    built = {entry.split(" to ")[1] for entry in moved}
    for node in ast.parse(text).body:
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id in built
                and not isinstance(node, (ast.FunctionDef, ast.ClassDef))
            ):
                raise SystemExit(
                    f"{target.name} constructs {inner.func.id}() in its module "
                    "body, so its decorator cannot be moved below the class -- "
                    "the construction would run against the undecorated one.  "
                    "This module's classes cannot be mutated by this harness."
                )

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

3. The alarm must not run during mutmut's *stats* pass.  That pass executes
   every test under coverage tracing to record which tests reach which
   functions, and tracing costs far more than the untraced baseline the
   budget was derived from.  A fast suite is the dangerous case: a suite
   baselining under a second lands the budget at its 5s floor, and a traced
   run blows straight through it.  The alarm
   then fails the *stats* pass rather than a mutant; mutmut writes no stats,
   every mutant is skipped as "not checked", and the run still prints a
   percentage -- a confident 0/711 that has tested nothing.

   mutmut sets ``MUTANT_UNDER_TEST`` to the sentinel ``stats`` for that pass
   and to a real mutant name for the runs that matter, so the two are told
   apart exactly rather than by a timing heuristic.  Installing no alarm
   under the sentinel keeps the measured ceiling meaningful for mutant runs,
   where the trampoline -- not the tracer -- is what executes.
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

# mutmut runs its stats pass under coverage tracing, which costs far more
# than the untraced baseline the budget came from.  It marks that pass with
# the sentinel below, so the alarm is skipped there and kept for the mutant
# runs it was measured for.  Without this a fast suite fails its own stats
# pass and every mutant is silently skipped.
_STATS_PASS = os.environ.get("MUTANT_UNDER_TEST") == "stats"


def _expired(signum, frame):
    raise TimeoutError(f"exceeded the {_budget:g}s per-test budget")


if _budget and not _STATS_PASS:

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


def _pytest_args(kind: _Kind, tests: list[str]) -> list[str]:
    """Return the pytest arguments, as a list, that the runs share.

    Deliberately free of ``-m``.  Deselecting the slow tests belongs in the
    work directory's ``addopts`` instead, because mutmut's stats pass runs
    pytest with its *own* arguments rather than the runner's -- so a ``-m``
    here filtered the baseline and the mutant runs while the stats pass
    collected the slow tests regardless.  ``test_minifuck_builds_five_input
    _xor`` is a 4s build that then ran under mutmut's tracing, blew the
    per-test alarm, and failed the stats pass; every mutant was scored 0.
    Configuration is honoured by all three passes, an argument is not.
    (The alarm no longer fires during that pass at all -- see the conftest
    -- but the ``-m`` reasoning is unchanged.)

    ``-n 0`` is not optional either.  The repo's ``addopts`` pins ``-n 4``,
    so without it every one of a few thousand mutants would spawn four xdist
    workers -- to run a suite that takes seconds.
    """
    return ["-x", "-q", "-p", "no:cacheprovider", "-n", "0"] + [
        f"{kind.tests_rel}/{name}" for name in tests
    ]


def _runner_command(kind: _Kind, tests: list[str]) -> str:
    """Return the same arguments as the shell command line mutmut runs.

    mutmut takes its runner as a string and splits it with ``shlex``, so an
    argument containing a space has to be quoted rather than merely joined.
    """
    return "python -m pytest " + shlex.join(_pytest_args(kind, tests))


def _prepare(
    family: str, module: str, work: Path, *, slow: bool
) -> tuple[Path, list[str]]:
    """Lay out the work directory; return (project dir, selected test files).

    The whole package is copied rather than bundled, so every import the
    generator makes resolves exactly as it does in the repo.  Only the
    target file is named in ``paths_to_mutate``.
    """
    kind = _KINDS[family]
    proj = work / "proj"
    proj.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")

    shutil.copytree(ROOT / "src" / "esolangs", proj / "esolangs", ignore=ignore)
    for rel in kind.support:
        dest = proj / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)

    tests = _test_files(kind)
    tools = proj / kind.tests_rel
    tools.mkdir(parents=True, exist_ok=True)
    # Every module in the test directory is copied, not just the selected
    # suites: the ones that are not tests are helpers the selected suites
    # import (``boolean_runners``, the APA trace and proof checkers), and a
    # missing one fails collection rather than a mutant.
    for path in kind.tests_dir.glob("*.py"):
        # A skipped suite is left out of the tree entirely rather than
        # merely unselected.  mutmut's stats pass is configured with the
        # *directory*, so a file that cannot run here would be collected by
        # it however carefully the runner command names the others -- and a
        # failed stats pass scores every mutant zero.
        if path.name in kind.skip_tests:
            continue
        shutil.copy(path, tools / path.name)
    (tools / "conftest.py").write_text(_CONFTEST)

    # Several suites read a shipped example, and the APA checkers read the
    # fixtures.  Both are resolved relative to the test file's parents, which
    # lands in proj for the baseline and in mutants/ for the mutation runs --
    # so both need the link.  Link rather than copy: nothing here is mutated.
    for base in (proj, proj / "mutants"):
        base.mkdir(parents=True, exist_ok=True)
        (base / "examples").symlink_to(ROOT / "examples")
        # A suite that reaches scripts/ resolves it relative to the test
        # file's parents, which lands in the work dir rather than the repo.
        # mutmut chdirs into mutants/ for the stats pass and every mutant
        # run, so the link has to exist under both roots.  Linked, not
        # copied: nothing under scripts/ is mutated.
        if kind.needs_scripts and not (base / "scripts").exists():
            (base / "scripts").symlink_to(ROOT / "scripts")
        # Several root suites check that the README documents what the CLI
        # does, resolving it from the test file's parents the same way.
        # Linking it is better than skipping those suites: they run, and
        # they cover ``cli``, which is a target of this kind.
        #
        # ``pyproject.toml`` is deliberately *not* linked, and the reason is
        # worth keeping: this harness writes its mutmut configuration to
        # ``proj/pyproject.toml``, so a symlink there is a write straight
        # through into the repository's own file.  Linking it once replaced
        # the real ``pyproject.toml`` with a mutmut config.  The suite that
        # wanted it is skipped below instead.
        if not (base / "README.md").exists():
            (base / "README.md").symlink_to(ROOT / "README.md")
    (proj / "tests" / "fixtures").symlink_to(ROOT / "tests" / "fixtures")

    rel_target = kind.rel_target(module)
    target = proj / rel_target
    moved = _undecorate_classes(target)
    if moved:
        print(
            f"[note] applied {', '.join(moved)} after the class body "
            "so mutmut can see it"
        )

    runner = _runner_command(kind, tests)
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
        # The kind's own directory rather than ``tests``.  mutmut's stats
        # pass collects this path ignoring the runner's own arguments, so a
        # wider path sweeps in tests that cannot resolve from the work
        # directory.
        f'tests_dir = ["{kind.tests_rel}"]\n'
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


def _check_shadowing(proj: Path, family: str, module: str) -> None:
    """Fail unless the copied package is what an import in ``proj`` resolves to.

    This positive control checks the part of this layout that
    that cannot be verified by reading.  ``mutate_one`` sidesteps the
    question with a flat single file; a package copy instead relies on the
    runner's cwd leading ``sys.path``, so that the copy shadows the editable
    install.  If it ever stopped holding, every mutant would run against the
    *repo's* generator, nothing would fail, and the run would report a
    perfect score having tested nothing.  A score of 100% is exactly what
    this failure looks like, which is why it is checked rather than assumed.
    """
    dotted = _KINDS[family].dotted(module)
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


def _score(proj: Path, family: str, module: str) -> tuple[int, int, list[str]]:
    """Return (killed, total, survivor names) from mutmut's own result file.

    Simpler than ``mutate_one._score``: only the target file is mutated, so
    every mutant in the meta belongs to it and there is nothing to filter
    out.  ``mutate_one`` needs a class-ownership filter because its bundle
    inlines two other modules alongside the interpreter.
    """
    meta_path = proj / "mutants" / (_KINDS[family].rel_target(module) + ".meta")
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
    parser.add_argument(
        "module",
        help="generator module as family/module, e.g. boolean/streetcode.  A "
        "bare name works where only one family defines it",
    )
    parser.add_argument(
        "--keep", action="store_true", help="leave the work directory in place"
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="include tests marked slow.  They are deselected by default "
        "because a mutant that one of them covers pays its cost on every "
        "run that reaches it, and they also lift the per-test alarm: the "
        "20s ceiling is measured over the fast suite, so it is dropped here "
        "rather than applied to tests it was never measured over",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="mutants to run at once (default 4; mutmut's own default is "
        "every core, which saturates the machine for the whole run)",
    )
    args = parser.parse_args()

    family, module = _parse_target(args.module)
    work = Path(tempfile.mkdtemp(prefix="mutate-generator-"))
    try:
        proj, tests = _prepare(family, module, work, slow=args.slow)
        print(f"[note] mutating {family}/{module}")
        print(f"[note] selected {len(tests)} test file(s): {', '.join(tests)}")
        _check_shadowing(proj, family, module)
        print("[note] the copied package shadows the installed one")

        started = time.monotonic()
        try:
            baseline = subprocess.run(
                [sys.executable, "-m", "pytest", *_pytest_args(_KINDS[family], tests)],
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

        # The ceiling is derived from the fast suite's worst single test, so
        # it only applies while the slow tests are deselected.  Under
        # ``--slow`` they are not, and capping at 20s would fail the very
        # tests the flag asks for -- the 4s Minifuck build runs far longer
        # under mutmut's tracing.  There the budget is left uncapped, which
        # is what ``mutate_one`` does at every run.
        budget = max(_MIN_ALARM, elapsed * _ALARM_FACTOR)
        if not args.slow:
            budget = min(_MAX_ALARM, budget)
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

        # mutmut reports a failed stats pass on stdout and exits nonzero, but
        # it still leaves a complete ``.meta`` whose every exit code is the
        # initial 0 -- which scores as "everything survived" rather than as
        # the failure it is.  ``_MIN_KILL_RATE`` below catches the total
        # case; this catches a partial one, and names the cause instead of
        # leaving a plausible-looking percentage to be believed.
        if "failed to collect stats" in mutation.stdout:
            print(mutation.stdout[-3000:] or mutation.stderr[-3000:])
            raise SystemExit(
                "mutmut could not collect stats, so no mutant was checked.  "
                "The usual cause is the per-test alarm firing during the "
                "stats pass, which runs under tracing and so costs far more "
                "than the baseline the budget came from."
            )

        killed, total, survivors = _score(proj, family, module)
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
        print(
            f"\n{family}/{module}: {killed}/{total} killed "
            f"({100 * killed / total:.1f}%)"
        )
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
