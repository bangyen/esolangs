"""Work out which files a branch touched, so checks can skip what it did not.

The full local stack takes ~97s, and most of that is spent re-proving things
the current branch cannot have broken: a change to one tape interpreter does
not need the checks for the other languages re-run.  This module
supplies the shared "what changed?" query that ``verify.py`` scopes itself
with.

The rule is deliberately conservative.  Scoping is only ever an optimisation:
when the answer is unclear -- no diff available, a detached HEAD, no
``origin/main`` -- the caller is told to run *everything*, because a check that
is skipped by accident is a check that silently stops guarding.  Touching the
shared machinery in ``_SHARED`` (or the checking machinery itself) also widens
the sweep back to the full set, since either can change how every interpreter
reads, steps, or reports.
"""

import codecs
import ctypes
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol, cast
from weakref import WeakKeyDictionary

ROOT = Path(__file__).resolve().parents[1]

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
    "scripts/verify.py",
    "scripts/_scope.py",
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
    "tests/scripts/test_bundle_one.py": (
        (
            "TestBundleCompiles::test_every_bundle_exposes_run",
            "TestBundleDetails",
            "test_raster_module_entry_point_matches_the_library",
            "test_package_bundle_also_supports_text_without_pillow",
            "test_raster_package_bundles_from_raw_http_sources",
        ),
        ("src/", "scripts/bundle_one.py", "scripts/install_one.sh", "tests/pick.py"),
    ),
    "tests/scripts/test_ci_coverage.py": (
        ("test_combining_shards_retains_every_branch",),
        (
            ".github/workflows/",
            "scripts/pytest_shard.py",
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


if __name__ == "__main__":
    print(runtime_digest(sys.argv[1]))


EXCERPT_BYTES = 32 * 1024


@dataclass
class Log:
    path: Path
    reader: threading.Thread | None = None
    overflow: bool = False


_LOGS: WeakKeyDictionary[subprocess.Popen[str], Log] = WeakKeyDictionary()


@dataclass
class Cleanup:
    lock: threading.Lock = field(default_factory=threading.Lock)
    complete: bool = False


_CLEANUPS: WeakKeyDictionary[
    subprocess.Popen[str] | subprocess.Popen[bytes], Cleanup
] = WeakKeyDictionary()
_CLEANUP_LOCK = threading.Lock()


def start_logged(
    cmd: list[str], name: str, env: dict[str, str], root: Path, *, stream: bool
) -> subprocess.Popen[str]:
    """Spool complete step output to a unique ignored file; optionally tee it."""
    directory = root / "notes" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:48] + "-"
    fd, filename = tempfile.mkstemp(prefix=prefix, suffix=".log", dir=directory)
    log = Log(Path(filename))
    os.close(fd)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name == "posix",
    )

    def copy() -> None:
        assert proc.stdout is not None
        reader = cast("io.BufferedReader", cast("io.TextIOWrapper", proc.stdout).buffer)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def tee(raw: bytes) -> None:
            with suppress(BrokenPipeError):
                sys.stdout.write(decoder.decode(raw))
                sys.stdout.flush()

        def stop() -> None:
            log.overflow = True
            stop_process_tree(proc)

        spool(reader, log.path, MAX_LOG_BYTES, stop, tee if stream else None)
        if stream:
            with suppress(BrokenPipeError):
                sys.stdout.write(decoder.decode(b"", final=True))
                sys.stdout.flush()

    log.reader = threading.Thread(target=copy, daemon=True)
    log.reader.start()
    _LOGS[proc] = log
    return proc


def excerpt(proc: subprocess.Popen[str]) -> str:
    """Return a bounded tail and the path to its persistent complete log."""
    log = _LOGS[proc]
    if log.reader is not None:
        log.reader.join(5)
    with log.path.open("rb") as output:
        output.seek(max(0, log.path.stat().st_size - EXCERPT_BYTES))
        tail = output.read(EXCERPT_BYTES).decode("utf-8", errors="replace")
    return f"[log] {log.path}\n" + tail


def stop_process_tree(proc: subprocess.Popen[str] | subprocess.Popen[bytes]) -> None:
    """Kill the step's process tree and reap its direct child."""
    with _CLEANUP_LOCK:
        cleanup = _CLEANUPS.setdefault(proc, Cleanup())
    with cleanup.lock:
        if cleanup.complete:
            return
        if os.name == "posix":
            if proc.poll() is None:
                descendants = []
                pending = [proc.pid]
                while pending:
                    parent = pending.pop()
                    children = child_pids(parent)
                    descendants.extend(children)
                    pending.extend(children)
                # Nested benchmark/reference workers own sessions; kill leaves first.
                for pid in reversed(descendants):
                    with suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)
            # Reap exited leaders before signalling; Darwin rejects zombie groups.
            proc.poll()
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
        else:
            # Discard taskkill's output rather than capturing it: a killed
            # descendant can inherit the stdout pipe's write end and keep it
            # open, so ``capture_output``'s reader thread blocks in join()
            # until the whole test times out.  A timeout guarantees cleanup
            # cannot hang even if taskkill does.
            with suppress(subprocess.TimeoutExpired):
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=30,
                )
            if proc.poll() is None:
                proc.kill()
        proc.wait()
        # Overflow logging and the caller can discover the same exit concurrently.
        cleanup.complete = True


def wait_with_heartbeat(
    proc: subprocess.Popen[str], name: str, start: float, limit: float, heartbeat: float
) -> tuple[str, int]:
    """Collect output until the step's deadline; kill descendants on timeout."""
    deadline = start + limit
    try:
        while True:
            remaining = deadline - time.monotonic()
            try:
                wait = max(0.0, min(heartbeat, remaining))
                if proc in _LOGS:
                    proc.wait(timeout=wait)
                    output = excerpt(proc)
                    return output, 125 if _LOGS[proc].overflow else proc.returncode
                output, _ = proc.communicate(timeout=wait)
                return output or "", proc.returncode
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    stop_process_tree(proc)
                    if proc in _LOGS:
                        output = excerpt(proc)
                    else:
                        output, _ = proc.communicate()
                    return (
                        output or ""
                    ) + f"\n{name}: deadline exceeded ({limit:g}s)\n", 124
                print(
                    f"[....] {name} still running "
                    f"({time.monotonic() - start:.0f}s elapsed)"
                )
    except BaseException:
        stop_process_tree(proc)
        raise


def run_bounded(
    cmd: list[str],
    *,
    timeout: float = 60,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = True,
    check: bool = False,
    stdout: int | None = None,
    stderr: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run preflight probes with the same descendant cleanup as check steps."""
    with subprocess.Popen(
        cmd,
        start_new_session=os.name == "posix",
        cwd=cwd,
        env=env,
        text=text,
        stdout=subprocess.PIPE if capture_output else stdout,
        stderr=subprocess.PIPE if capture_output else stderr,
    ) as proc:
        try:
            output, error = proc.communicate(timeout=timeout)
        except BaseException:
            stop_process_tree(proc)
            raise
        result = subprocess.CompletedProcess(cmd, proc.returncode, output, error)
        if check:
            result.check_returncode()
        return result


def write_text(path: Path, text: str) -> None:
    """Flush a sibling temporary file and replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # newline="" keeps the bytes exactly as written: on Windows the
        # default text mode translates "\n" to "\r\n", which would make a
        # content hash (durations_sha256) disagree with the file it names.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


MAX_LOG_BYTES = 8 * 1024 * 1024
MARKER = b"\n[diagnostic byte limit exceeded]\n"


def spool(
    stream: BinaryIO,
    path: Path,
    limit: int,
    stop: Callable[[], None],
    tee: Callable[[bytes], None] | None = None,
) -> None:
    """Keep a bounded prefix and overflow excerpt, then stop the process tree."""
    written = 0
    with path.open("wb") as output:
        while chunk := cast(bytes, getattr(stream, "read1", stream.read)(8192)):
            if written + len(chunk) > limit - len(MARKER):
                available = max(0, limit - written - len(MARKER))
                excerpt = chunk[-available:] if available else b""
                output.write(excerpt)
                output.write(MARKER)
                output.flush()
                if tee is not None:
                    tee(MARKER)
                stop()
                return
            output.write(chunk)
            output.flush()
            written += len(chunk)
            if tee is not None:
                tee(chunk)


def child_pids(pid: int) -> list[int]:
    """Return direct child PIDs; refuse truncated or unreadable process evidence."""
    platform = sys.platform
    if platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        list_children = library.proc_listchildpids
        list_children.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        list_children.restype = ctypes.c_int
        capacity = 65536
        buffer = (ctypes.c_int * capacity)()
        count = list_children(pid, buffer, ctypes.sizeof(buffer))
        if count < 0:
            raise OSError(ctypes.get_errno(), "cannot enumerate child processes")
        if count >= capacity:
            raise RuntimeError("child process enumeration exceeds capacity")
        return [value for value in buffer[:count] if value > 0]
    if platform.startswith("linux"):
        try:
            tasks = list(Path(f"/proc/{pid}/task").iterdir())
        except FileNotFoundError:
            return []
        found: set[int] = set()
        for task in tasks:
            try:
                found.update(
                    int(value) for value in (task / "children").read_text().split()
                )
            except FileNotFoundError:
                continue
        return sorted(found)
    raise RuntimeError("child process enumeration is unavailable on this platform")
