"""Work out which files a branch touched, so checks can skip what it did not.

The rule is deliberately conservative: when the diff cannot be read, or the
shared machinery moved, the caller is told to run *everything* -- a check that
is skipped by accident is a check that silently stops guarding.
"""

import ast
import atexit
import functools
import hashlib
import importlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify.process import run_bounded

ROOT = Path(__file__).resolve().parents[2]

# Changing any of these changes how *every* interpreter reads, steps, or
# reports, so touching one sweeps the whole registry rather than nothing.
SHARED_INTERPRETER = (
    "interpreters/io.py",
    "interpreters/memory.py",
    "interpreters/brackets.py",
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
)

# The checking machinery itself.  A change here can alter what every step
# does, so it can never be validated by a scoped run of that same machinery.
SHARED_TOOLING = (
    "scripts/verify/gate.py",
    "scripts/verify/scope.py",
    "checks/check_diff_coverage.py",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "justfile",
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
    if any(f.endswith(SHARED_INTERPRETER) for f in changed):
        return "shared interpreter machinery changed"
    if any(f.endswith(SHARED_TOOLING) for f in changed):
        return "verification tooling changed"
    return None


TOOLING_INTEGRATIONS = {
    "tests/scripts/test_ci_coverage.py": (
        ("test_combining_shards_retains_every_branch",),
        (
            ".github/workflows/",
            "scripts/ci/shard.py",
            "checks/check_diff_coverage.py",
        ),
    ),
}


def local_tooling_deselections(changed: list[str]) -> list[str]:
    """Defer unrelated tooling integrations to the unchanged CI test bands."""
    if not changed or any(
        path in SHARED_TOOLING
        or path
        in {
            "uv.lock",
            ".coveragerc",
            "tests/conftest.py",
            "tests/__init__.py",
            "tests/scripts/script_support.py",
            "setup.cfg",
            "pytest.ini",
            "tox.ini",
        }
        or path.startswith("tests/fixtures/")
        or (path.startswith("tests/scripts/") and Path(path).name == "conftest.py")
        for path in changed
    ):
        return []
    return [
        f"--deselect={suite}::{test}"
        for suite, (tests, dependencies) in TOOLING_INTEGRATIONS.items()
        if not any(
            path == suite
            or path.startswith((*dependencies, "tests/scripts/__init__.py"))
            for path in changed
        )
        for test in tests
    ]


CACHED_STEPS = frozenset(
    {
        "bandit",
        "generated docs",
        "deep proofs (verify band)",
        "dead definitions",
        "generator size baseline",
        "duplicate-code check (pylint)",
    }
)
_DISTRIBUTIONS = {
    "bandit": {"bandit", "stevedore", "pyyaml"},
    "python checks": {
        "pillow",
        "sympy",
        "mpmath",
        "pylint",
        "astroid",
        "dill",
        "isort",
        "platformdirs",
        "tomlkit",
        "mccabe",
    },
}


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


def _feed(digest: _Digest, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def runtime_digest(step: str) -> str:
    """Hash the interpreter, dependency inventory and the check's tool sources."""
    modules = {
        "bandit": ("bandit.core.extension_loader",),
        "python checks": ("ast", "PIL.Image", "pylint.lint"),
    }
    for name in modules[step]:
        importlib.import_module(name)
    digest = hashlib.sha256()
    _feed(digest, sys.version.encode())
    _feed(digest, Path(sys.executable).read_bytes())
    files: dict[Path, str] = {}
    for distribution in sorted(
        importlib.metadata.distributions(),
        key=lambda item: (item.metadata["Name"], str(item.locate_file(""))),
    ):
        name = distribution.metadata["Name"].lower().replace("_", "-")
        _feed(digest, f"{name}:{distribution.version}".encode())
        selected = name in _DISTRIBUTIONS[step] or any(
            entry.group.startswith(("bandit", "pylint"))
            for entry in distribution.entry_points
        )
        for file in distribution.files or ():
            if file.suffix == ".pyc":
                continue
            if selected or file.name in ("METADATA", "RECORD", "entry_points.txt"):
                path = Path(str(distribution.locate_file(file)))
                if path.is_file():
                    files[path] = str(path)
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).is_file():
            # uv's bootstrap module lives in a fresh temporary directory.
            # Its import name and bytes identify the input across invocations.
            files.setdefault(Path(filename), f"module:{module.__name__}")
    for path in sorted(files):
        _feed(digest, files[path].encode())
        _feed(digest, path.read_bytes())
    return digest.hexdigest()


def _tree(
    root: Path, *, bandit: bool = False
) -> tuple[str, dict[str, tuple[int, int, int]]]:
    result = run_bounded(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = {root / name for name in result.stdout.split("\0") if name}
    for directory in ("src", "scripts"):
        paths.update(
            path
            for path in (root / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    paths.update(root / name for name in (".bandit", ".pylintrc", "setup.cfg"))
    if bandit:
        paths = {
            path
            for path in paths
            if path.is_relative_to(root / "src") or path == root / ".bandit"
        }
    for path in tuple(paths):
        if path.is_symlink() and path.is_dir():
            if not path.resolve().is_relative_to(root.resolve()):
                raise OSError("cannot fingerprint an external input directory")
            paths.update(child for child in path.rglob("*") if child.is_file())
    digest = hashlib.sha256()
    stamps = {}
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        _feed(digest, name.encode())
        if path.is_symlink() and path.is_dir():
            _feed(digest, str(path.resolve()).encode())
            continue
        if path.is_file():
            stat = path.stat()
            stamps[name] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            _feed(digest, b"present" + path.read_bytes())
        else:
            _feed(digest, b"absent")
    return digest.hexdigest(), stamps


class VerifiedCache:
    """Reuse clean runs; publish new entries only after input stability checks."""

    def __init__(self, root: Path) -> None:
        """Snapshot the tree, and the bandit-scoped inputs, at construction."""
        self.root = root
        self.initial = _tree(root)
        self.bandit = _tree(root, bandit=True)[0]
        self.pending: list[tuple[Path, dict[str, str | int]]] = []
        self.runtimes: dict[str, tuple[list[str], dict[str, str], str]] = {}

    def key(self, step: str, cmd: list[str], env: dict[str, str]) -> str | None:
        """Return a key, or decline caching when the runtime cannot be verified."""
        if env.get("VERIFY_CLEAN_CACHE", "1") == "0":
            return None
        if step == "bandit":
            if cmd[:4] != ["uv", "run", "--no-sync", "--with"]:
                return None
            prefix = [*cmd[:5], "python"]
        else:
            if "python" not in Path(cmd[0]).name:
                return None
            prefix = [cmd[0]]
        query = [
            *prefix,
            str(Path(__file__).resolve()),
            "bandit" if step == "bandit" else "python checks",
        ]
        query_key = json.dumps([query, sorted(env.items())])
        if query_key in self.runtimes:
            runtime = self.runtimes[query_key][2]
            return self._key(step, cmd, env, runtime)
        try:
            result = run_bounded(
                query,
                env=env,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        runtime = result.stdout.strip()
        if len(runtime) != 64 or any(
            char not in "0123456789abcdef" for char in runtime
        ):
            return None
        self.runtimes[query_key] = (query, env, runtime)
        return self._key(step, cmd, env, runtime)

    def _key(self, step: str, cmd: list[str], env: dict[str, str], runtime: str) -> str:
        # Only the known source scan has an audited dependency footprint.
        inputs = (
            self.bandit
            if step == "bandit"
            and cmd
            == [
                "uv",
                "run",
                "--no-sync",
                "--with",
                "bandit",
                "bandit",
                "-r",
                "src",
                "-q",
            ]
            else self.initial[0]
        )
        return hashlib.sha256(
            json.dumps(
                [step, cmd, sorted(env.items()), inputs, runtime],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def path(self, key: str) -> Path:
        """Return the cache file path for a key."""
        return self.root / ".cache" / "verification" / f"{key}.json"

    def load(self, key: str) -> str | None:
        """Return the clean run's output, treating corrupt entries as misses."""
        try:
            entry = json.loads(self.path(key).read_text())
        except (OSError, ValueError):
            return None
        if (
            isinstance(entry, dict)
            and entry.get("key") == key
            and type(entry.get("returncode")) is int
            and entry["returncode"] == 0
        ):
            output = entry.get("output")
            if isinstance(output, str):
                return output
        return None

    def remember(self, key: str, output: str, returncode: int) -> None:
        """Queue a clean result to publish if the inputs stay fixed."""
        if returncode == 0:
            self.pending.append(
                (self.path(key), {"key": key, "output": output, "returncode": 0})
            )

    def finish(self) -> bool:
        """Publish clean results only if repository and runtime inputs stayed fixed."""
        try:
            stable = _tree(self.root) == self.initial
        except (OSError, subprocess.SubprocessError):
            return False
        if not stable:
            return False

        def matches(runtime: tuple[list[str], dict[str, str], str]) -> bool:
            query, env, original = runtime
            try:
                result = run_bounded(
                    query,
                    env=env,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                return False
            return result.returncode == 0 and result.stdout.strip() == original

        with ThreadPoolExecutor(max_workers=2) as pool:
            if not all(pool.map(matches, self.runtimes.values())):
                return False
        try:
            stable = _tree(self.root) == self.initial
        except (OSError, subprocess.SubprocessError):
            return False
        if not stable:
            return False
        for path, entry in self.pending:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=path.parent, delete=False
            ) as stream:
                json.dump(entry, stream)
                temporary = Path(stream.name)
            temporary.replace(path)
        return True


COVERAGE_TEST_STEP = "coverage tests"


# Which paths each step actually guards.  A step whose prefixes the branch did
# not touch cannot have been broken by that branch, so a scoped run skips it.
# A step absent from this table is always run: it is either cheap enough not to
# matter or it guards the whole tree.  Prefixes are repo-relative.
STEP_SCOPE: dict[str, tuple[str, ...]] = {
    "bandit": ("src/",),
    "duplicate-code check (pylint)": ("src/esolangs/", "scripts/", "checks/"),
    "dead definitions": ("src/", "scripts/", "checks/"),
    # Only a generator, an interpreter (the step counts are executed), or the
    # baseline itself can move these numbers.
    "generator size baseline": (
        "src/esolangs/tools/",
        "src/esolangs/interpreters/",
        "checks/check_generator_sizes.py",
        "scripts/benchmark.py",
        "tests/fixtures/generator_sizes.json",
    ),
    # The union of what the two proofs in this band read: ArrowQueue's lemmas
    # import the generator and nothing else, and BIO's also parse the emitted
    # program and instantiate it through the shipped fill.  The runner is in
    # the scope too, since it decides which of them run at all.
    "deep proofs (verify band)": (
        "src/esolangs/tools/bio.py",
        "src/esolangs/tools/arrowqueue.py",
        "src/esolangs/tools/examples.py",
        "tests/proofs/deep/",
    ),
    # Helpers outside interpreters can introduce leaks too. The sweep's
    # dependency graph narrows this to the languages that import them.
    "exception leaks": (
        "src/esolangs/",
        "checks/verify_no_exception_leaks.py",
    ),
}


@functools.lru_cache(maxsize=1)
def _scope_changed_files() -> tuple[str, ...]:
    """Return this branch's changed paths, queried once per run."""
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
    from verify.scope import widens_to_everything

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


INTERPRETER_CONTRACT_TESTS = (
    "tests/test_vm_protocol.py",
    "tests/test_stepping_parity.py",
    "tests/test_api_contracts.py",
    "tests/test_interpreter_conventions.py",
    "tests/interpreters/test_io.py",
    "tests/interpreters/test_input_convention.py",
)


def _generator_test_scope(module: str) -> list[str] | None:
    """Keep shared tests and dependent language suites for a leaf generator."""
    from esolangs.registry import LANGUAGES

    owners: dict[str, str] = {}
    for language in LANGUAGES.values():
        if language.boolean is not None:
            owner = language.boolean.__module__.removeprefix("esolangs.tools.")
            for name in (
                language.id,
                language.name,
                *language.aliases,
                language.boolean.__name__,
                owner,
            ):
                owners[name] = owner
    if module not in owners.values():
        return None
    needles = {name for name, owner in owners.items() if owner == module}
    # A generator importing this one makes its language suite relevant too.
    dependents = {module}
    tools_root = ROOT / "src/esolangs/tools"
    sources = {
        source: source.read_text(encoding="utf-8")
        for source in tools_root.rglob("*.py")
    }
    imports: dict[Path, set[str]] = {}
    while True:
        found = set()
        for source, text in sources.items():
            if not any(dep.rsplit(".", 1)[-1] in text for dep in dependents):
                continue
            if source not in imports:
                references = set()
                package = list(source.parent.relative_to(tools_root).parts)
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
                        prefix = prefix.removeprefix("esolangs.tools.")
                        references.add(prefix)
                        for alias in node.names:
                            references.add(prefix + "." + alias.name)
                            references.add(owners.get(alias.name, alias.name))
                    elif isinstance(node, ast.Import):
                        references.update(
                            alias.name.removeprefix("esolangs.tools.")
                            for alias in node.names
                        )
                imports[source] = references
            if imports[source] & dependents:
                owner = (
                    source.relative_to(tools_root)
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
    for test in (ROOT / "tests").rglob("*.py"):
        path = test.relative_to(ROOT).as_posix()
        if not _is_collected(path):
            continue
        test_owner: str | None = None
        for prefix in ("test_boolean_", "test_"):
            if test.stem.startswith(prefix):
                suffix = test.stem.removeprefix(prefix)
                matches = [
                    name
                    for name in owners
                    if suffix == name or suffix.startswith(name + "_")
                ]
                if matches:
                    test_owner = owners[max(matches, key=len)]
                    break
        # Only language-local directories follow this naming convention.
        local = test.parent.name in {"tools", "interpreters", "languages"}
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
            relative = Path(f).relative_to("src/esolangs/interpreters")
            # Package helpers can share a filename with another interpreter.
            if len(relative.parts) != 2:
                return WHOLE_SUITE
            stem = Path(f).stem
            if stem.startswith("_"):
                return WHOLE_SUITE
            candidate = f"tests/interpreters/test_{stem}.py"
            if not (ROOT / candidate).exists():
                return WHOLE_SUITE
            paths.add(candidate)
            for suite in (ROOT / "tests/interpreters").glob(f"test_{stem}_*.py"):
                paths.add(suite.relative_to(ROOT).as_posix())
            # Language-local tests cannot detect broken VM or public I/O contracts.
            paths.update(INTERPRETER_CONTRACT_TESTS)
            generator_tests = f"tests/tools/test_boolean_{stem}.py"
            if (ROOT / generator_tests).exists():
                paths.add(generator_tests)
            continue
        if f.startswith("src/esolangs/tools/") and f.endswith(".py"):
            relative = Path(f).relative_to("src/esolangs/tools")
            if len(relative.parts) != 1 or relative.stem.startswith("_"):
                return WHOLE_SUITE
            selected = _generator_test_scope(relative.stem)
            if selected is None:
                return WHOLE_SUITE
            paths.update(selected)
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


if __name__ == "__main__":
    print(runtime_digest(sys.argv[1]))
