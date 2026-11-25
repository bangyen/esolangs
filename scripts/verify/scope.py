"""Work out which files a branch touched, so checks can skip what it did not.

The rule is deliberately conservative: when the diff cannot be read, or the
shared machinery moved, the caller is told to run *everything* -- a check that
is skipped by accident is a check that silently stops guarding.
"""

import ast
import functools
import os
import subprocess
import sys
from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import Path

# scripts/ holds the sibling `verify`, `docs`, and `ci` packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]

# Changing any of these changes how *every* interpreter reads, steps, or
# reports, so touching one sweeps the whole registry rather than nothing.
SHARED_INTERPRETER = (
    "runtime/io.py",
    "runtime/memory.py",
    "runtime/brackets.py",
    "exceptions.py",
    "vm.py",
    "raster/__init__.py",
    "raster/png.py",
    "raster/scale.py",
    "registry/__init__.py",
    "registry/_slug.py",
    "registry/_table.py",
    "registry/_contracts.py",
    "registry/_language.py",
    "registry/_describe.py",
)

# The checking machinery itself.  A change here can alter what every step
# does, so it can never be validated by a scoped run of that same machinery.
SHARED_TOOLING = (
    "scripts/verify/gate.py",
    "scripts/verify/scope.py",
    "uv.lock",
    ".python-version",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "justfile",
    "conftest.py",
)
# Files any tooling integration may read: a change here keeps them all.
_TOOLING_ROOTS = frozenset(
    {
        *SHARED_TOOLING,
        "uv.lock",
        ".coveragerc",
        "tests/__init__.py",
        "tests/tooling/script_support.py",
        "setup.cfg",
        "pytest.ini",
        "tox.ini",
        "snapshot.json",
    }
)


def diff_paths(root: Path, *args: str) -> list[str] | None:
    """Return exact changed paths, or None when Git cannot establish the diff."""
    try:
        got = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", *args],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if got.returncode != 0:
        return None
    return [os.fsdecode(name) for name in got.stdout.split(b"\0") if name]


def changed_files() -> list[str]:
    """Return the repo-relative paths this branch changed, or [] if unknown.

    Prefers local ``main`` so unpushed integrated work is not attributed
    to this branch; tries ``origin/main`` and the last commit if absent.
    Uncommitted work counts too -- the point is to check the tree in hand, not
    only what has been committed.  An empty list means "could not tell", which
    callers must read as "run everything".
    """
    names: list[str] = []
    known = False
    for ref in ("main...HEAD", "origin/main...HEAD", "HEAD~1"):
        paths = diff_paths(ROOT, ref)
        if paths is not None:
            names = paths
            known = True
            break
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        cwd=ROOT,
        check=False,
        timeout=60,
    )
    if not known or status.returncode != 0:
        return []
    records = iter(status.stdout.split(b"\0"))
    for record in records:
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            return []
        names.append(os.fsdecode(record[3:]))
        if b"R" in record[:2] or b"C" in record[:2]:
            original = next(records, b"")
            if not original:
                return []
            names.append(os.fsdecode(original))
    # Committed-and-dirty paths repeat; mypy rejects duplicate modules.
    return list(dict.fromkeys(names))


def widens_to_everything(changed: list[str]) -> str | None:
    """Return why *changed* forces a full run, or ``None`` if scoping is safe."""
    if not changed:
        return "no diff available"
    if any(
        f.endswith(SHARED_INTERPRETER)
        or f.startswith(("src/esolangs/runtime/", "src/esolangs/registry/"))
        for f in changed
    ):
        return "shared interpreter machinery changed"
    if any(
        f.endswith(SHARED_TOOLING)
        or f.startswith(("scripts/verify/", "checks/", ".github/actions/"))
        for f in changed
    ):
        return "verification tooling changed"
    return None


TOOLING_INTEGRATIONS = {
    "tests/tooling/test_ci_coverage.py": (
        ("test_combining_shards_retains_every_branch",),
        (
            ".github/workflows/",
            ".github/actions/",
            "scripts/ci/shard.py",
        ),
    ),
}


def local_tooling_deselections(changed: list[str]) -> list[str]:
    """Defer unrelated tooling integrations to the unchanged CI test bands."""
    if not changed or any(
        path in _TOOLING_ROOTS
        or path.startswith("tests/support/fixtures/")
        or (path.startswith("tests/tooling/") and Path(path).name == "conftest.py")
        for path in changed
    ):
        return []
    return [
        f"--deselect={suite}::{test}"
        for suite, (tests, dependencies) in TOOLING_INTEGRATIONS.items()
        if not any(
            path == suite
            or path.startswith((*dependencies, "tests/tooling/__init__.py"))
            for path in changed
        )
        for test in tests
    ]


@functools.lru_cache(maxsize=1)
def _scope_changed_files() -> tuple[str, ...]:
    """Return this branch's changed paths, queried once per run."""
    return tuple(changed_files())


def verify_full() -> bool:
    """Whether ``VERIFY_FULL`` asks for the whole tree."""
    return os.environ.get("VERIFY_FULL", "0") not in ("", "0")


def _scope_plan(*, full: bool) -> tuple[bool, str]:
    """Return whether all files need checking, and why."""
    if full:
        return True, "--full requested"
    if verify_full():
        return True, "VERIFY_FULL set"
    changed = list(_scope_changed_files())
    reason = widens_to_everything(changed)
    if reason is not None:
        return True, reason
    return False, f"{len(changed)} file(s) changed"


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


INTERPRETER_CONTRACT_TESTS = (
    "tests/runtime/test_vm_protocol.py",
    "tests/runtime/test_stepping_parity.py",
    "tests/runtime/test_run_bounded.py",
    "tests/api/test_api_contracts.py",
    "tests/interpreters/test_interpreter_conventions.py",
    "tests/interpreters/test_interpreters_robustness.py",
    "tests/interpreters/test_io.py",
    "tests/interpreters/test_input_convention.py",
    # A Cyclic tag rewrite passed the scoped gate yet failed these two: no
    # pure `_advance`, and a regrouped snapshot one bit off its exact formula.
    "tests/interpreters/test_transition_purity.py",
    "tests/proofs/test_workspace_formulas.py",
    "tests/proofs/test_execution_formulas.py",
    "tests/proofs/_witnesses.py",
    "tests/generators/test_boolean_contract.py",
    "tests/tooling/test_examples.py",
)


def _import_references(
    source: Path, text: str, normalise: Callable[[str], str], owners: dict[str, str]
) -> set[str]:
    """Return every module, owner and imported name ``source`` refers to."""
    references = set()
    package = list(source.parent.relative_to(ROOT / "src").parts)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                prefix = ".".join(
                    [
                        *package[: len(package) - node.level + 1],
                        *(prefix.split(".") if prefix else []),
                    ]
                )
            references.add(normalise(prefix))
            for alias in node.names:
                references.add(normalise(prefix + "." + alias.name))
                references.add(owners.get(alias.name, alias.name))
        elif isinstance(node, ast.Import):
            references.update(normalise(alias.name) for alias in node.names)
    return references


def _named_owner(stem: str, owners: dict[str, str]) -> str | None:
    """Return the language a ``test_[boolean_]<name>`` file stem names, if any."""
    for prefix in ("test_boolean_", "test_"):
        if stem.startswith(prefix):
            suffix = stem.removeprefix(prefix)
            matches = [
                name
                for name in owners
                if suffix == name or suffix.startswith(name + "_")
            ]
            if matches:
                return owners[max(matches, key=len)]
    return None


def _generator_test_scope(module: str) -> list[str] | None:
    """Keep shared tests and dependent language suites for a leaf generator."""
    from esolangs.registry import LANGUAGES

    owners: dict[str, str] = {}
    modules: dict[str, str] = {}
    for language in LANGUAGES.values():
        if language.backend is not None:
            defining = language.backend.generate.__module__
            owner = language.id
            modules[defining] = owner
            for name in (
                language.id,
                language.name,
                *language.aliases,
                language.backend.generate.__name__,
            ):
                owners[name] = owner

    def normalise(reference: str) -> str:
        for canonical, owner in modules.items():
            if reference == canonical or reference.startswith(canonical + "."):
                return owner + reference[len(canonical) :]
        return reference

    module = normalise(module)
    if module not in owners.values():
        return None
    needles = {name for name, owner in owners.items() if owner == module}
    # A generator importing this one makes its language suite relevant too.
    dependents = {module}
    tools_root = ROOT / "src/esolangs/generation"
    sources = {
        source: source.read_text(encoding="utf-8")
        for source in (
            *tools_root.rglob("*.py"),
            *(
                path
                for path in (ROOT / "src/esolangs/languages").rglob("*.py")
                if "generator" in path.parts or path.stem == "generator"
            ),
        )
    }
    imports: dict[Path, set[str]] = {}
    while True:
        found = set()
        for source, text in sources.items():
            if not any(dep.rsplit(".", 1)[-1] in text for dep in dependents):
                continue
            if source not in imports:
                imports[source] = _import_references(source, text, normalise, owners)
            if imports[source] & dependents:
                owner = normalise(
                    source.relative_to(ROOT / "src")
                    .with_suffix("")
                    .as_posix()
                    .replace("/", ".")
                    .removesuffix(".__init__")
                )
                found.add(owner)
        if found <= dependents:
            break
        dependents.update(found)
    selected = []
    for test in (
        *((ROOT / "tests").rglob("*.py")),
        *((ROOT / "src/esolangs/languages").glob("*/tests/**/*.py")),
    ):
        parts = test.relative_to(ROOT).parts
        path = "/".join(parts)
        if not _is_collected(path):
            continue
        test_owner: str | None
        if parts[:3] == ("src", "esolangs", "languages") and "tests" in parts:
            local, test_owner = True, parts[3]
        else:
            # Only language-local directories follow this naming convention.
            local = test.parent.name in {"generators", "interpreters", "languages"}
            test_owner = _named_owner(test.stem, owners)
        if local and test_owner is not None and test_owner not in dependents:
            text = test.read_text(encoding="utf-8").lower()
            if not any(needle.lower() in text for needle in needles):
                continue
        selected.append(path)
    return selected


def _pytest_scope(changed: list[str]) -> list[str] | str:
    """Return the pytest paths covering *changed*.

    An interpreter runs its language suite and shared contracts; anything under
    ``tests/`` is run directly.  ``WHOLE_SUITE`` means the coverage is not
    localisable -- a new interpreter with no test module yet, or a source file
    whose tests live somewhere this cannot predict -- so everything runs rather
    than guessing.  An empty list means the branch touched nothing the Python
    tests cover (docs, assembly, CI config), so there is nothing to run.
    """
    paths: set[str] = set()
    for f in changed:
        if (
            f == "conftest.py"
            or f.startswith("tests/")
            or (f.startswith("src/esolangs/languages/") and "/tests/" in f)
        ):
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
        if f.startswith("src/esolangs/languages/"):
            relative = Path(f).relative_to("src/esolangs/languages")
            local_tests = ROOT / "src/esolangs/languages" / relative.parts[0] / "tests"
            if local_tests.is_dir() and (
                relative.parts[1:2] == ("interpreter",)
                or relative.parts[1:] == ("interpreter.py",)
            ):
                suites = sorted(local_tests.rglob("test_*.py"))
                if not suites:
                    return WHOLE_SUITE
                paths.update(test.relative_to(ROOT).as_posix() for test in suites)
                paths.update(INTERPRETER_CONTRACT_TESTS)
                continue
        if f.startswith("src/esolangs/languages/") and f.endswith("/generator.py"):
            relative = Path(f).relative_to("src/esolangs/languages")
            parts = relative.with_suffix("").parts
            # Only a leaf generator at ``<id>/generator.py`` is localisable;
            # a root helper or a package submodule keeps the whole suite.
            if len(parts) != 2 or any(part.startswith("_") for part in parts):
                return WHOLE_SUITE
            selected = _generator_test_scope(f"esolangs.languages.{parts[0]}.generator")
            if selected is None:
                return WHOLE_SUITE
            paths.update(selected)
            continue
        if f.startswith("src/"):
            return WHOLE_SUITE  # non-interpreter source: not localisable
        if f.startswith(("scripts/", "checks/")) and f.endswith(".py"):
            # The scripts have unit tests (the bundler's, for one) that do not
            # follow the interpreter naming convention, so there is no way to
            # tell which module covers them.
            return WHOLE_SUITE
    return sorted(paths)


def whole_tree_cmd(cmd: list[str]) -> list[str]:
    """Return *cmd* with ``--all-files`` widened to files not yet added.

    ``--all-files`` lists git's index, so a new language's untracked package
    passed ``finish-language``'s full gate, then failed ruff and the
    prose-density hook at its first commit (2026-10-21).
    """
    if "--all-files" not in cmd:
        return cmd
    got = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        cwd=ROOT,
        check=False,
        timeout=60,
    )
    if got.returncode != 0:
        return cmd
    names = dict.fromkeys(os.fsdecode(f) for f in got.stdout.split(b"\0") if f)
    return _with_files(cmd, [f for f in names if (ROOT / f).is_file()])


def _with_files(cmd: list[str], files: list[str]) -> list[str]:
    """Re-aim a pre-commit ``--all-files`` command at *files*."""
    return [c for c in cmd if c != "--all-files"] + ["--files", *files]


def _scoped_cmd(name: str, cmd: list[str], changed: list[str]) -> list[str] | None:
    """Narrow *cmd* to the branch's files, or ``None`` if it has nothing to do.

    Three steps take a file list rather than being all-or-nothing, so instead
    of skipping them wholesale they are re-aimed at what actually moved.
    """
    if name == "pre-commit":
        files = [f for f in changed if (ROOT / f).is_file()]
        if not files:
            return None
        return _with_files(cmd, files)
    if name == "pytest":
        paths = _pytest_scope(changed)
        if not paths:
            return None  # nothing the Python tests cover moved
        if paths == WHOLE_SUITE:
            return cmd  # not localisable: run every test
        return [*cmd, *paths]
    return cmd
