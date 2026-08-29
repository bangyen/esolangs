"""Mutation-test one interpreter against its own unit tests.

Line coverage says a test *executed* a line; it cannot say the test would
have noticed the line being wrong.  mutmut answers that by changing the code
one edit at a time and re-running the tests: an edit no test objects to is a
"survivor", and a survivor is either an equivalent mutant or a gap.  Run
against Qoibl at 100% line coverage this found three real gaps, all of them
guards -- the failure mode where a rejection stops rejecting and nothing
looks wrong until malformed input gets through.

Mutating the installed package does not work.  mutmut copies the code into
``mutants/`` and runs the suite from there, which fails two ways: naming one
module leaves the other 124 unimportable, and copying all of them means
every module that does trampolined work at *import* time (``registry``
building LANGUAGES, ``lamfunc``, ...) fires a trampoline before mutmut has
set ``mutmut.config`` -- "NoneType has no attribute max_stack_depth", once
per module, unfixable one at a time.

So this mutates the *bundle* instead.  ``scripts/bundle_one.py`` already
inlines an interpreter plus its shared modules into one dependency-closed
file, whose executable code is byte-identical to the interpreter's (only
docstrings move).  That gives mutmut a single self-contained target, and the
language's own test file -- with its imports repointed at the bundle -- as
the runner.

Usage:
    python scripts/mutate_one.py Qoibl
    python scripts/mutate_one.py Grapheme --keep   # leave the work dir

Requires: mutmut==3.3.1.  Newer versions build the trampoline qualname with
mangled_name_from_mutant_name(), which strips the class part, so class-method
mutants can never be selected and are silently reported as killed.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Tests that reach past the interpreter -- into the VM or the registry --
# cannot run against a bundle, which inlines neither.  They are dropped from
# the copied test file, so the score is over the tests that can run.
_UNBUNDLED = ("esolangs.vm", "esolangs.registry")

# Packages the bundle does not inline, whose imports must therefore keep
# resolving against the installed package.  This is deliberately *not*
# ``_UNBUNDLED``: that constant also drives ``_drop_unbundled_tests``, and a
# test importing one of these is still perfectly runnable -- BrainIf's suite
# checks its own generated hello-world through ``esolangs.tools.text``, which
# only needs to be left alone, not cut.  Rewriting it to ``from bundled
# import brainif`` asked the bundle for a text generator it never inlines.
_NOT_REWRITTEN = ("vm", "registry", "tools")

# The two modules ``bundle_one`` inlines alongside the interpreter.  Their
# classes are the *only* ones a score may legitimately leave out, which is
# what ``_score`` checks its exclusions against.
_INLINED = ("esolangs.exceptions", "esolangs.interpreters.io")


def _test_file(module: str) -> Path:
    """Return the test file for ``category.module``, or raise if absent."""
    path = ROOT / "tests" / "interpreters" / f"test_{module.rsplit('.', 1)[-1]}.py"
    if not path.exists():
        raise SystemExit(f"no test file for {module}: expected {path}")
    return path


def _drop_unbundled_tests(src: str) -> tuple[str, int]:
    """Remove tests importing modules the bundle does not inline.

    A test that imports ``esolangs.vm`` inside its body cannot be repointed
    at the bundle, so it is cut whole rather than left to fail and mark every
    mutant killed for the wrong reason.

    "Whole" has to include the decorators, which sit *above* the ``def``.
    Cutting from the ``def`` alone leaves a ``@pytest.mark.parametrize``
    stranded on whichever test follows, and pytest rejects the file at
    collection: "function uses no argument 'text'".
    """
    dropped = 0
    for name in re.findall(r"\n    def (test_\w+)\(", src):
        body = re.search(
            rf"\n(?:    @[^\n]*\n(?:        [^\n]*\n)*)*    def {name}\("
            rf".*?(?=\n    @|\n    def |\nclass |\Z)",
            src,
            re.S,
        )
        if body and any(mod in body.group(0) for mod in _UNBUNDLED):
            src = src.replace(body.group(0), "\n")
            dropped += 1
    return src, dropped


def _copy_test_helpers(src: str, tests_dir: Path, stem: str) -> str:
    """Copy the sibling test modules ``src`` imports, and flatten the imports.

    Only the one test file is copied into the work dir, so a suite sharing
    helpers with another language -- ``from tests.interpreters.oisc import
    memory, run_program``, as Decleq's and AddSubJump's both do -- failed
    collection outright: no ``tests.interpreters`` package exists there.

    The helper is copied in beside the test and the import flattened to a
    plain ``from oisc import ...``, which resolves because pytest puts the
    test's own directory on the path.  Helpers import from the package too
    (``oisc`` needs ``ScriptedIO``), so they get the same rewrite -- and
    mutmut copies ``tests/`` wholesale into ``mutants/``, so the copy carries
    across on its own.
    """
    for name in sorted(set(re.findall(r"from tests\.interpreters\.(\w+) import", src))):
        helper = ROOT / "tests" / "interpreters" / f"{name}.py"
        if not helper.exists():
            raise SystemExit(f"test helper not found: {helper}")
        (tests_dir / f"{name}.py").write_text(
            _rewrite_imports(helper.read_text(), stem)
        )
    return re.sub(r"from tests\.interpreters\.(\w+) import", r"from \1 import", src)


def _rewrite_imports(src: str, stem: str, module: str = "") -> str:
    """Repoint every package import at the single bundled module.

    Imports of the modules the bundle does not inline are left alone, so
    they keep resolving against the installed package.  A test file that
    imports a VM helper at module level -- ``run_until_halt_or_cycle``, as
    the three largest grid interpreters' suites all do -- is not reachable
    by ``_drop_unbundled_tests``, which only reads test bodies; repointing
    it at the bundle broke collection before a single mutant ran.  Nothing
    outside the bundle is mutated, so importing the real module is safe.
    """
    if module:
        # ``from esolangs.<pkg> import <name> as m`` imports the interpreter
        # *module*, not a name inside it.  The bundle is that module, so the
        # rewrite is a plain alias -- repointing it at ``from {stem} import
        # <name>`` asks for an attribute the bundle has no reason to define.
        #
        # The skip list applies here too, and not applying it was a bug an
        # interpreter only hits when a package in that list exports a
        # module of the *same leaf name*.  Streetcode is the case: its
        # generator is ``esolangs.tools.boolean.streetcode``, so
        # ``from esolangs.tools.boolean import streetcode as gen`` matched
        # this rule and ``gen`` came out bound to the bundled interpreter.
        # The suite then called it -- ``gen("00110100")`` -- and died with
        # "'module' object is not callable" before a single mutant ran.
        leaf = module.rsplit(".", 1)[-1]
        skipped = "|".join(_NOT_REWRITTEN)
        src = re.sub(
            rf"from esolangs(?!\.(?:{skipped})\b)(?:\.[\w.]+)? import {leaf} as (\w+)",
            rf"import {stem} as \1",
            src,
        )
        # ``importlib.import_module("esolangs.interpreters.<module>")`` names
        # the interpreter in a *string*, which no import-statement rewrite can
        # see.  Eight suites load the interpreter this way, and left alone
        # they test the installed package instead of the bundle: no mutant is
        # visible, so mutmut's forced-fail check aborts the run before a
        # single one is scored.  The quoted module path is rewritten rather
        # than the call, because the call is not always on one line -- the
        # %^2^-1 suite splits it across three.
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


_CONFTEST = '''"""mutmut workarounds, both of which otherwise fail silently.

1. ``set_start_method`` raises on the second call under macOS + Python 3.12,
   which aborts the run rather than the mutant.
2. mutmut names a mutant without the module prefix while the trampoline
   builds its qualname from ``__module__``, which has it.  Without the
   prefix the selected mutant never activates and every one "passes".
"""

import contextlib
import multiprocessing
import os

_orig = multiprocessing.set_start_method


def _patched(method, force=False):
    with contextlib.suppress(RuntimeError):
        _orig(method, force=force)


multiprocessing.set_start_method = _patched

_mut = os.environ.get("MUTANT_UNDER_TEST", "")
if _mut and "__mutmut_" in _mut and not _mut.startswith("{stem}"):
    os.environ["MUTANT_UNDER_TEST"] = "{stem}" + _mut
'''

# mutmut parses each file into an AST to build its mutants, and the parsing
# runs in spawned children on macOS/3.12 -- so the limit has to be raised at
# interpreter startup, which is what a sitecustomize on PYTHONPATH does.
_SITECUSTOMIZE = "import sys\n\nsys.setrecursionlimit(50000)\n"


def _split_inlined(bundle: Path, module: str) -> int:
    """Move the bundle's inlined prefix into a module the mutants import.

    ``bundle_one`` inlines ``esolangs.exceptions`` and
    ``esolangs.interpreters.io`` ahead of the interpreter so the file runs
    standalone.  mutmut mutates whatever is in ``paths_to_mutate``, so those
    two ride along: ~64 mutants per language that :func:`_score` then throws
    away for not being the interpreter's, and -- because a mutated ``IO``
    hangs the suite rather than failing it -- most of the run's timeouts.
    Each timeout costs mutmut's whole ``(estimate + 1) * 30`` CPU budget,
    so the discarded quarter of the mutants was the expensive quarter.

    The prefix moves to ``_inlined.py``, which the bundle imports with a
    star import, leaving executable code identical and the interpreter's
    own definitions the only thing left to mutate.  Returns the number of
    lines moved.
    """
    text = bundle.read_text()
    marker = (
        f"# --- inlined from esolangs/interpreters/{module.replace('.', '/')}.py ---"
    )
    head, sep, tail = text.partition(marker)
    if not sep:
        raise SystemExit(f"no inline marker for {module} in {bundle.name}")

    # The header (shebang, docstring, __future__ and stdlib imports) has to
    # stay with both halves: the prefix needs it to import, and a
    # ``from __future__`` must be the first statement in each file.
    lines = head.splitlines(keepends=True)
    first_inline = next(
        (i for i, line in enumerate(lines) if line.startswith("# --- inlined from")),
        len(lines),
    )
    preamble, inlined = "".join(lines[:first_inline]), "".join(lines[first_inline:])
    if not inlined.strip():
        return 0

    # ``from _inlined import *`` skips underscore-prefixed names unless the
    # module says otherwise, and the names bundled alongside an interpreter
    # are often private: Factor is built on brainfuck, so brainfuck's
    # ``_Machine`` lands here and ``_BFMachine = _Machine`` in the other half
    # died on a NameError.  An explicit ``__all__`` re-exports everything the
    # prefix defines, underscores included.
    export = '\n\n__all__ = [_n for _n in dir() if not _n.startswith("__")]\n'
    (bundle.parent / "_inlined.py").write_text(preamble + inlined + export)
    bundle.write_text(
        preamble + "from _inlined import *  # noqa: F403\n\n" + sep + tail
    )
    return inlined.count("\n")


def _prepare(language: str, work: Path) -> tuple[Path, str, int, set[str]]:
    """Lay out the project; return (dir, stem, dropped, the module's classes)."""
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
    # Several suites read a shipped example through ``Path(__file__)
    # .parents[2]``.  That resolves to the work dir for the baseline run and
    # to *proj* for the mutation runs, because mutmut re-copies tests/ into
    # mutants/ and chdirs there -- so both need the link, or the example
    # tests fail inside mutants/ even unmutated and mutmut scores nothing.
    # Link rather than copy: nothing outside ``bundled.py`` is mutated.
    (work / "examples").symlink_to(ROOT / "examples")
    (proj / "examples").symlink_to(ROOT / "examples")
    (proj / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        f'paths_to_mutate = ["{out.name}"]\n'
        # mutmut copies only what it mutates into mutants/, so the inlined
        # half has to be carried across explicitly or every mutant dies on
        # an import that the baseline -- which runs from proj/ -- resolves.
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


# A decorator line on a class, and the class statement it applies to.
_DECORATED_CLASS = re.compile(
    r"^(?P<decorators>(?:@[^\n(]+(?:\([^\n]*\))?\n)+)class (?P<name>\w+)", re.M
)


def _undecorate_classes(bundle: Path) -> list[str]:
    """Rewrite ``@d`` on a class into ``Class = d(Class)`` after its body.

    mutmut skips any ``FunctionDef`` or ``ClassDef`` carrying decorators --
    copying them for the trampoline can have side effects, and ``@property``
    breaks the signature assignment it does (``file_mutation.py``, "ignore
    decorated functions").  A ``@dataclass`` state class therefore yields no
    mutants at all while the run still prints a percentage: Eval scored 5/6
    over a 124-line file, ``run`` being all that was left to mutate once its
    ``State`` -- the other ninety lines -- was skipped whole.

    Applying the decorator as a plain call below the class is what the
    decorator syntax means, so the class behaves identically (same
    ``__init__``, ``__repr__``, ``__eq__``, same ``field(default_factory=)``
    handling), but the ``ClassDef`` mutmut parses no longer has decorators
    and its methods are mutated like any other.  Only classes are rewritten:
    a decorated *method* keeps its decorator, since ``@property`` is exactly
    what the trampoline cannot take.

    Returns the decorators moved, for the note the caller prints.
    """
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

    # The calls go at the end of the module, after every class body has been
    # defined, innermost decorator first -- the order the syntax applies them.
    applied = "\n".join(
        f"{name} = {decorator}({name})"
        for entry in moved
        for decorator, name in [entry.split(" to ")]
    )
    bundle.write_text(f"{new}\n\n{applied}\n")
    return moved


def _classes_of(dotted: str) -> set[str]:
    """Return the names of the classes the module at ``dotted`` defines."""
    import importlib

    mod = importlib.import_module(dotted)
    return {
        obj.__name__
        for obj in vars(mod).values()
        if isinstance(obj, type) and obj.__module__ == dotted
    }


def _own_classes(module: str) -> set[str]:
    """Return the names of the classes the interpreter itself defines.

    ``RUNNERS`` stores the path from the interpreters package down --
    ``grid_based.streetcode`` -- so it is qualified here before importing.
    """
    return _classes_of(f"esolangs.interpreters.{module}")


def _score(proj: Path, stem: str, classes: set[str]) -> tuple[int, int, list[str]]:
    """Return (killed, total, survivor names) from mutmut's own result file.

    The bundle inlines io and exceptions too, and only the interpreter's own
    mutants are scored.  A class method is named ``x<sep>Class<sep>method``,
    so the class part says whose it is -- dropping every name that *has* a
    class part instead threw away the interpreter's own classes, which for a
    grid language is nearly all of it: Streetcode scored 59 mutants and hid
    843 belonging to ``_Machine``, its entire stepping engine.
    """
    meta = json.loads((proj / "mutants" / f"{stem}.py.meta").read_text())
    codes = meta["exit_code_by_key"]
    own = {k: v for k, v in codes.items() if "ǁ" not in k or k.split("ǁ")[1] in classes}

    # Every mutant left out has to belong to a class one of the *inlined*
    # modules defines.  Anything else means the interpreter's own classes
    # are being dropped -- the bug that scored Streetcode over 59 mutants
    # while hiding the 843 belonging to _Machine, and reported it as a
    # normal-looking 57.6%.  The denominator is checked rather than
    # estimated: mutmut's own file lists every mutant, so what may go
    # missing from it is known exactly.
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
    """Bundle one interpreter, mutate it, and report what survived."""
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
        "the cap -- at two workers a Forbin run spent 85% of its time on the "
        "6% of mutants that timed out",
    )
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="mutate-one-"))
    try:
        proj, stem, dropped, classes = _prepare(args.language, work)
        if dropped:
            print(f"[note] dropped {dropped} test(s) needing the VM or registry")

        baseline = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_bundled.py"],
            cwd=proj,
            capture_output=True,
            text=True,
            check=False,
        )
        if baseline.returncode != 0:
            print(baseline.stdout[-2000:])
            raise SystemExit("the bundled tests fail before any mutation")

        env = {"PYTHONPATH": str(work), "PYTHONDONTWRITEBYTECODE": "1"}
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
        if not killed:
            # Every exit code still at its initial 0 means no mutant run ever
            # reported, which a suite that passes its baseline cannot cause.
            # It reads as a perfect survivor sweep, so say what it is instead.
            print(mutation.stdout[-3000:] or mutation.stderr[-3000:])
            raise SystemExit(
                f"0 of {total} mutants killed with a passing baseline: the "
                "mutants did not run.  Check the output above -- usually the "
                "suite fails inside mutants/, where it runs from a different "
                "directory than the baseline."
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
