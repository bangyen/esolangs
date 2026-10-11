import json
import subprocess
from pathlib import Path

import pytest

from tests.scripts.script_support import load

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify" / "scope.py"


@pytest.fixture
def cache_repo(tmp_path, monkeypatch):
    module = load(SCRIPT)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".cache/\n*.egg-info/\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/input.py").write_text("value = 1\n")
    original = module.run_bounded
    runtime = ["a" * 64]

    def run(cmd, **kwargs):
        if str(SCRIPT) in cmd:
            return subprocess.CompletedProcess(cmd, 0, runtime[0], "")
        return original(cmd, **kwargs)

    monkeypatch.setattr(module, "run_bounded", run)
    cache = module.VerifiedCache(tmp_path)
    return module, tmp_path, cache, runtime


class TestCertificates:
    @pytest.mark.parametrize(
        "change",
        ["source", "config", "command", "environment", "runtime", "unrelated", None],
    )
    @pytest.mark.parametrize("step", ["generator size baseline", "bandit"])
    def test_certificate_inputs(self, cache_repo, change, step):
        module, root, cache, runtime = cache_repo
        command = "uv run --no-sync --with bandit bandit -r src -q"
        cmd = command.split() if step == "bandit" else ["python", "check.py"]
        env = {}
        key = cache.key(step, cmd, env)
        cache.remember(key, "failed", 1)
        assert cache.finish()
        assert cache.load(key) is None
        cache.remember(key, "passed", 0)
        if change in ("source", "config", "unrelated"):
            paths = ["src/input.py", "src/.bandit", "script.py"]
            index = ["source", "config", "unrelated"].index(change)
            (root / paths[index]).write_text("changed\n")
        elif change == "command":
            cmd.append("--full")
        elif change == "environment":
            env["OPTION"] = "changed"
        elif change == "runtime":
            runtime[0] = "b" * 64
        stable = change not in ("source", "config", "runtime", "unrelated")
        assert cache.finish() is stable
        assert cache.load(key) == ("passed" if stable else None)
        fresh = module.VerifiedCache(root).key(step, cmd, env)
        reused = change is None or (step == "bandit" and change == "unrelated")
        assert (fresh == key) is reused

    @pytest.mark.parametrize(
        "entry", ["invalid", {"returncode": 1}, {"returncode": False}]
    )
    def test_corrupt_entries_miss(self, cache_repo, entry):
        _, _, cache, _ = cache_repo
        key = "a" * 64
        path = cache.path(key)
        path.parent.mkdir(parents=True)
        if isinstance(entry, dict):
            entry.update(key=key, output="passed")
        path.write_text(json.dumps(entry))
        assert cache.load(key) is None

    @pytest.mark.parametrize("external", [False, True])
    def test_directory_links(self, cache_repo, *, external):
        module, root, _, _ = cache_repo
        target = root.parent if external else root / "src"
        if not external:
            (target / "sample.py").write_text("original\n")
        (root / "examples").symlink_to(target)
        if external:
            with pytest.raises(OSError, match="external input"):
                module.VerifiedCache(root)
        else:
            cache = module.VerifiedCache(root)
            (target / "sample.py").write_text("changed\n")
            assert not cache.finish()


def test_runtime_timeout_declines_certificate(cache_repo, monkeypatch):
    module, _, cache, _ = cache_repo

    def timeout(cmd, **_kwargs):
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(module, "run_bounded", timeout)
    assert cache.key("generator size baseline", ["python", "check.py"], {}) is None
    assert not cache.finish()


def test_a_gitignored_artifact_under_src_is_not_an_input(cache_repo):
    """A rebuilt ``src/*.egg-info`` must not invalidate an otherwise clean run.

    The fingerprint once walked ``src`` and ``scripts`` and swept gitignored
    build artifacts in, so a ``uv run`` in another shell rewrote one mid-gate
    and the run's own stability check rejected a clean result.
    """
    _, root, cache, _ = cache_repo
    assert cache.finish()
    artifact = root / "src" / "esolangs.egg-info"
    artifact.mkdir()
    (artifact / "PKG-INFO").write_text("Name: esolangs\n")
    assert cache.finish()
