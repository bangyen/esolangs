r"""Mutation-test one interpreter against its own unit tests."""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tests that reach past the.
# cannot run against a bundle,.
# the copied test file, so the.
# :func:`_reaches_unbundled`.
# than its text.

# Packages the bundle does not.
# resolving against the.
# set.
# test importing one of these.
# reaches the registry or the.
# cut.
# bundle for a name it never.
_NOT_REWRITTEN = ("vm", "registry", "tools")

# The two modules.
# classes are the *only* ones a.
# ``_score`` checks its.
_INLINED = ("esolangs.exceptions", "esolangs.interpreters.io")

# How far past the unmutated.
# in ``_CONFTEST`` fails it.
# job here is to come in under.
# RLIMIT, and being too tight.
# earned) is far worse than.
_ALARM_FACTOR = 10.0
_MIN_ALARM = 2.0

# How long the unmutated suite.
_BASELINE_TIMEOUT = 120.0

# Below this share of mutants.
# than reported: the lowest.
# is 76.7%, so a figure down.
_MIN_KILL_RATE = 0.1


def _test_file(module: str) -> Path:
    r"""Return the test file for ``category.module``, or raise if absent."""
    path = ROOT / "tests" / "interpreters" / f"test_{module.rsplit('.', 1)[-1]}.py"
    if not path.exists():
        raise SystemExit(f"no test file for {module}: expected {path}")
    return path


def _reaches_unbundled(node: ast.AST) -> bool:
    r"""Return whether ``node``'s subtree really reaches past the bundle."""
    packages = ("esolangs.vm", "esolangs.registry")
    for sub in ast.walk(node):
        if isinstance(sub, ast.ImportFrom) and sub.module is not None:
            if any(
                sub.module == pkg or sub.module.startswith(f"{pkg}.")
                for pkg in packages
            ):
                return True
        elif isinstance(sub, ast.Import):
            if any(
                alias.name == pkg or alias.name.startswith(f"{pkg}.")
                for alias in sub.names
                for pkg in packages
            ):
                return True
        elif isinstance(sub, ast.Call):
            func = sub.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "run"
                and isinstance(func.value, ast.Name)
                and func.value.id == "esolangs"
            ):
                return True
    return False


def _reaching_helpers(src: str) -> list[str]:
    r"""Return call markers for helpers that themselves reach past the."""
    try:
        tree = ast.parse(src)
    except SyntaxError:  # pragma: no cover - bodies come from a valid module
        return []

    markers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("test_"):
            continue
        if _reaches_unbundled(node):
            markers += [f"{node.name}(", f".{node.name}("]
    return markers


def _parse_body(body: str) -> ast.AST:
    r"""Parse a carved-out test body, which is indented inside its class."""
    try:
        return ast.parse(textwrap.dedent(body))
    except SyntaxError:  # pragma: no cover - bodies come from a valid module
        return ast.Module(body=[], type_ignores=[])


def _drop_unbundled_tests(src: str) -> tuple[str, int]:
    r"""Remove tests importing modules the bundle does not inline."""
    dropped = 0
    callers = _reaching_helpers(src)
    for name in re.findall(r"\n    def (test_\w+)\(", src):
        # The lines above the ``def``.
        # any continuation of one (more.
        # bracket that closes a.
        # the ``@``.
        # ``@pytest.mark.parametrize``.
        # Break's malformed-program.
        # unindented fragment, and the.
        # .
        # These are one flat.
        # another.
        # more ways than there are.
        # then backtracks through all.
        # run inside ``sre_search``,.
        body = re.search(
            rf"\n(?:    @[^\n]*\n|     [^\n]*\n|    [)\]][^\n]*\n)*    def {name}\("
            rf".*?(?=\n    @|\n    def |\nclass |\n@|\ndef |\Z)",
            src,
            re.S,
        )
        # The reach itself is judged on.
        # comment or docstring no.
        # reaching helper stays a text.
        # carries no such hazard, and.
        # class, so it is re-parsed on.
        if body and (
            any(name in body.group(0) for name in callers)
            or _reaches_unbundled(_parse_body(body.group(0)))
        ):
            src = src.replace(body.group(0), "\n")
            dropped += 1

    # A class can lose every test.
    # assertions on what.
    # leaves a class statement with.
    # not parse.
    src = re.sub(
        r"(\nclass \w+[^\n]*:\n)(?=\s*\n*(?:class |def |@|\Z))",
        r"\1    pass\n",
        src,
    )
    return src, dropped


def _copy_test_helpers(src: str, tests_dir: Path, stem: str) -> str:
    r"""Copy the sibling test modules ``src`` imports, and flatten the."""
    for name in sorted(set(re.findall(r"from tests\.interpreters\.(\w+) import", src))):
        helper = ROOT / "tests" / "interpreters" / f"{name}.py"
        if not helper.exists():
            raise SystemExit(f"test helper not found: {helper}")
        (tests_dir / f"{name}.py").write_text(
            _rewrite_imports(helper.read_text(), stem)
        )
    src = re.sub(r"from tests\.interpreters\.(\w+) import", r"from \1 import", src)

    # ``tests/raises.py`` is the.
    # it needs the same treatment:.
    # dir, so ``from tests.raises.
    # outright -- before any mutant.
    # it (Container, Forbin and.
    # standard library and pytest,.
    # .
    # Deliberately *not*.
    # ``tests/samples.py`` imports.
    # inline, and copying it would.
    # cut by.
    if re.search(r"from tests\.raises import", src):
        (tests_dir / "raises.py").write_text((ROOT / "tests" / "raises.py").read_text())
        src = re.sub(r"from tests\.raises import", "from raises import", src)
    return src


def _rewrite_imports(src: str, stem: str, module: str = "") -> str:
    r"""Repoint every package import at the single bundled module."""
    if module:
        # ``from esolangs.<pkg> import.
        # *module*, not a name inside.
        # rewrite is a plain alias --.
        # <name>`` asks for an.
        # .
        # The skip list applies here.
        # interpreter only hits when a.
        # module of the *same leaf.
        # generator is.
        # ``from esolangs.tools.boolean.
        # this rule and ``gen`` came.
        # The suite then called it --.
        # "'module' object is not.
        leaf = module.rsplit(".", 1)[-1]
        skipped = "|".join(_NOT_REWRITTEN)
        src = re.sub(
            rf"from esolangs(?!\.(?:{skipped})\b)(?:\.[\w.]+)? import {leaf} as (\w+)",
            rf"import {stem} as \1",
            src,
        )
        # ``importlib.import_module("eso.
        # the interpreter in a.
        # see.
        # they test the installed.
        # visible, so mutmut's.
        # single one is scored.
        # than the call, because the.
        # %^2^-1 suite splits it across.
        src = re.sub(
            rf"""(['"])esolangs\.interpreters\.{re.escape(module)}\1""",
            rf"\g<1>{stem}\g<1>",
            src,
        )
    skip = "|".join(_NOT_REWRITTEN)
    return re.sub(
        rf"from esolangs(?!\.(?:{skip})\b)(?:\.[\w.]+)? import ",
        f"from {stem} import ",
        src,
    )


_CONFTEST = '''"""mutmut workarounds, all of which otherwise fail silently.

1. ``set_start_method`` raises on the second call under macOS + Python 3.12,
   which aborts the run rather than the mutant.
2. mutmut names a mutant without the module prefix while the trampoline
   builds its qualname from ``__module__``, which has it.  Without the
   prefix the selected mutant never activates and every one "passes".
3. A mutant that turns a loop condition around does not fail the suite, it
   hangs it, and mutmut only reclaims a hung mutant at its RLIMIT_CPU of
   ``(estimate + 1) * 30`` CPU-seconds.  Such a mutant is killed either way
   -- an interpreter that never halts is a caught bug -- but at ~30
   CPU-seconds instead of the ~0.2s an ordinary kill costs.  Over brainfuck
   18 of 68 mutants hung, and capping each test below the RLIMIT reproduced
   the identical verdict in 5s where the run had taken 33s.

   The budget is passed in rather than hardcoded, because "too long" is a
   property of the suite: a fixed cap would fail the languages whose tests
   legitimately run for seconds (Minifuck's is a generator build).  The
   caller derives it from the measured baseline, and when the variable is
   absent no alarm is installed -- which is what leaves the harness's own
   baseline run, and any other use of these tests, untouched.
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

_mut = os.environ.get("MUTANT_UNDER_TEST", "")
if _mut and "__mutmut_" in _mut and not _mut.startswith("{stem}"):
    os.environ["MUTANT_UNDER_TEST"] = "{stem}" + _mut

_budget = float(os.environ.get("MUTATE_ONE_ALARM", "0"))


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

# mutmut parses each file into.
# runs in spawned children on.
# interpreter startup, which is.
_SITECUSTOMIZE = "import sys\n\nsys.setrecursionlimit(50000)\n"


def _split_inlined(bundle: Path, module: str) -> int:
    r"""Move the bundle's inlined prefix into a module the mutants import."""
    text = bundle.read_text()
    marker = (
        f"# --- inlined from esolangs/interpreters/{module.replace('.', '/')}.py ---"
    )
    head, sep, tail = text.partition(marker)
    if not sep:
        raise SystemExit(f"no inline marker for {module} in {bundle.name}")

    # The header (shebang,.
    # stay with both halves: the.
    # ``from __future__`` must be.
    lines = head.splitlines(keepends=True)
    first_inline = next(
        (i for i, line in enumerate(lines) if line.startswith("# --- inlined from")),
        len(lines),
    )
    preamble, inlined = "".join(lines[:first_inline]), "".join(lines[first_inline:])
    if not inlined.strip():
        return 0

    # ``from _inlined import *``.
    # module says otherwise, and.
    # are often private: Factor is.
    # ``_Machine`` lands here and.
    # died on a NameError.
    # prefix defines, underscores.
    export = '\n\n__all__ = [_n for _n in dir() if not _n.startswith("__")]\n'
    (bundle.parent / "_inlined.py").write_text(preamble + inlined + export)
    bundle.write_text(
        preamble + "from _inlined import *  # noqa: F403\n\n" + sep + tail
    )
    return inlined.count("\n")


def _prepare(language: str, work: Path) -> tuple[Path, str, int, set[str]]:
    r"""Lay out the project; return (dir, stem, dropped, the module's."""
    from bundle_one import Source, bundle

    from esolangs.registry import RUNNERS

    if language not in RUNNERS:
        raise SystemExit(f"unknown language {language!r}")
    module = RUNNERS[language][0]

    proj = work / "proj"
    (proj / "tests").mkdir(parents=True)
    out = bundle(language, Source(None), proj / "bundled.py")
    stem = out.stem
    moved = _split_inlined(out, module)
    if moved:
        print(f"[note] moved {moved} inlined lines out of the mutation target")

    tests, dropped = _drop_unbundled_tests(_test_file(module).read_text())
    tests = _copy_test_helpers(tests, proj / "tests", stem)
    (proj / "tests" / "test_bundled.py").write_text(
        _rewrite_imports(tests, stem, module)
    )
    (proj / "tests" / "conftest.py").write_text(_CONFTEST.replace("{stem}", stem))
    (work / "sitecustomize.py").write_text(_SITECUSTOMIZE)
    # Several suites read a shipped.
    # .parents[2]``.
    # to *proj* for the mutation.
    # mutants/ and chdirs there --.
    # tests fail inside mutants/.
    # Link rather than copy:.
    (work / "examples").symlink_to(ROOT / "examples")
    (proj / "examples").symlink_to(ROOT / "examples")
    # The same for.
    # program from.
    # outright -- not one mutant,.
    # be scored at all.
    # only the fixtures need.
    (work / "tests").mkdir(exist_ok=True)
    for tests_dir in (work / "tests", proj / "tests"):
        (tests_dir / "fixtures").symlink_to(ROOT / "tests" / "fixtures")
    (proj / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        f'paths_to_mutate = ["{out.name}"]\n'
        # mutmut copies only what it.
        # half has to be carried across.
        # an import that the baseline.
        'also_copy = ["_inlined.py"]\n'
        "backup = false\n"
        'runner = "python -m pytest -x -q -p no:cacheprovider tests/test_bundled.py"\n'
        'tests_dir = ["tests/"]\n'
    )
    moved_classes = _undecorate_classes(out)
    if moved_classes:
        print(
            f"[note] applied {', '.join(moved_classes)} after the class body "
            "so mutmut can see it"
        )
    return proj, stem, dropped, _own_classes(module)


# A decorator line on a class,.
_DECORATED_CLASS = re.compile(
    r"^(?P<decorators>(?:@[^\n(]+(?:\([^\n]*\))?\n)+)class (?P<name>\w+)", re.M
)


def _undecorate_classes(bundle: Path) -> list[str]:
    r"""Rewrite ``@d`` on a class into ``Class = d(Class)`` after its body."""
    text = bundle.read_text()
    moved: list[str] = []

    def rewrite(match: re.Match[str]) -> str:
        name = match.group("name")
        decorators = match.group("decorators").strip().splitlines()
        moved.extend(f"{d.lstrip('@')} to {name}" for d in decorators)
        return f"class {name}"

    new = _DECORATED_CLASS.sub(rewrite, text)
    if not moved:
        return []

    # The calls go at the end of.
    # defined, innermost decorator.
    applied = "\n".join(
        f"{name} = {decorator}({name})"
        for entry in moved
        for decorator, name in [entry.split(" to ")]
    )
    bundle.write_text(f"{new}\n\n{applied}\n")
    return moved


def _classes_of(dotted: str) -> set[str]:
    r"""Return the names of the classes the module at ``dotted`` defines."""
    import importlib

    mod = importlib.import_module(dotted)
    return {
        obj.__name__
        for obj in vars(mod).values()
        if isinstance(obj, type) and obj.__module__ == dotted
    }


def _own_classes(module: str) -> set[str]:
    r"""Return the names of the classes the interpreter itself defines."""
    return _classes_of(f"esolangs.interpreters.{module}")


def _score(proj: Path, stem: str, classes: set[str]) -> tuple[int, int, list[str]]:
    r"""Return (killed, total, survivor names) from mutmut's own result."""
    meta = json.loads((proj / "mutants" / f"{stem}.py.meta").read_text())
    codes = meta["exit_code_by_key"]
    own = {k: v for k, v in codes.items() if "ǁ" not in k or k.split("ǁ")[1] in classes}

    # Every mutant left out has to.
    # modules defines.
    # are being dropped -- the bug.
    # while hiding the 843.
    # normal-looking 57.6%.
    # estimated: mutmut's own file.
    # missing from it is known.
    inlined = set().union(*(_classes_of(mod) for mod in _INLINED))
    stray: dict[str, int] = {}
    for key in codes:
        if key in own:
            continue
        name = key.split("ǁ")[1]
        if name not in inlined:
            stray[name] = stray.get(name, 0) + 1
    if stray:
        lost = sum(stray.values())
        blame = ", ".join(f"{name} ({n})" for name, n in sorted(stray.items()))
        raise SystemExit(
            f"{lost} of this module's own mutants would not be scored: {blame}. "
            f"No inlined module defines {'them' if len(stray) > 1 else 'it'}, so "
            f"the score would read {len(own)} mutants where the file lists "
            f"{len(codes)}."
        )

    killed = sum(1 for v in own.values() if v)
    return killed, len(own), sorted(k for k, v in own.items() if not v)


def main() -> int:
    r"""Bundle one interpreter, mutate it, and report what survived."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", help="display name, e.g. Qoibl")
    parser.add_argument(
        "--keep", action="store_true", help="leave the work directory in place"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="mutants to run at once (default 4; mutmut's own default is "
        "every core, which saturates the machine for the whole run).  Fewer "
        "is not always cheaper: mutmut caps each mutant with an RLIMIT_CPU "
        "of (baseline + 1) * 30, so with less sibling contention a process "
        "burns that CPU budget in fewer wall-seconds and more mutants reach "
        # argparse expands help through.
        # has to be doubled: 3.14.
        "the cap -- at two workers a Forbin run spent 85%% of its time on the "
        "6%% of mutants that timed out",
    )
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="mutate-one-"))
    try:
        proj, stem, dropped, classes = _prepare(args.language, work)
        if dropped:
            print(f"[note] dropped {dropped} test(s) needing the VM or registry")

        # The per-test alarm belongs to.
        # none, so anything that does.
        # of saying so.
        # under a second, so a cap two.
        # nothing and turns a hang into.
        started = time.monotonic()
        try:
            baseline = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/test_bundled.py"],
                cwd=proj,
                capture_output=True,
                text=True,
                check=False,
                timeout=_BASELINE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise SystemExit(
                f"the bundled tests did not finish in {_BASELINE_TIMEOUT:g}s.  "
                "Either a test loops without the bound its helper gave it, or "
                "the harness itself is stuck before pytest -- sample the "
                "process to tell which."
            ) from None
        elapsed = time.monotonic() - started
        if baseline.returncode != 0:
            print(baseline.stdout[-2000:])
            raise SystemExit("the bundled tests fail before any mutation")

        # What every test does.
        # has to come in under mutmut's.
        # RLIMIT to pay off, so it is.
        # loose still turns a 30-second.
        # alarm too tight would fail a.
        # kill that no mutation earned.
        # rather than any one test's,.
        # whose suites are dominated by.
        budget = max(_MIN_ALARM, elapsed * _ALARM_FACTOR)
        print(f"[note] baseline {elapsed:.2f}s; capping each test at {budget:.1f}s")

        env = {
            "PYTHONPATH": str(work),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MUTATE_ONE_ALARM": f"{budget:.3f}",
        }
        mutation = subprocess.run(
            [sys.executable, "-m", "mutmut", "run", "--max-children", str(args.jobs)],
            cwd=proj,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=False,
        )

        killed, total, survivors = _score(proj, stem, classes)
        if not total:
            raise SystemExit("no mutants were generated")
        if killed < total * _MIN_KILL_RATE:
            # An exit code still at its.
            # reported, which a suite that.
            # Testing for *zero* killed was.
            # brainfuck suite reported 2 of.
            # the mutants did not run --.
            # of tripping the check.
            # the suites this harness.
            print(mutation.stdout[-3000:] or mutation.stderr[-3000:])
            raise SystemExit(
                f"only {killed} of {total} mutants killed with a passing "
                "baseline: the mutants did not run.  Check the output above "
                "-- usually the suite fails inside mutants/, where it runs "
                "from a different directory than the baseline."
            )
        print(
            f"\n{args.language}: {killed}/{total} killed ({100 * killed / total:.1f}%)"
        )
        if survivors:
            print(f"\n{len(survivors)} survived:")
            for name in survivors:
                print(f"  {name}")
            print(
                "\nA survivor is an equivalent mutant or a gap; read the diff "
                "before writing a test for it."
            )
        return 0
    finally:
        if args.keep:
            print(f"\nwork dir: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
