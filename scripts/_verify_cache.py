"""Remember clean companion checks only while their complete inputs match."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _verify_process import run_bounded

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
