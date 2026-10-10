"""Clean certificates require identical inputs and successful executions."""

import json
import subprocess
from pathlib import Path

import pytest

from tests.scripts.script_support import load

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "_verify_cache.py"


@pytest.fixture
def cache_repo(tmp_path, monkeypatch):
    module = load(SCRIPT)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".cache/\n")
    (tmp_path / "input.py").write_text("value = 1\n")
    original = module.subprocess.run
    runtime = ["a" * 64]

    def run(cmd, **kwargs):
        if str(SCRIPT) in cmd:
            return subprocess.CompletedProcess(cmd, 0, runtime[0], "")
        return original(cmd, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", run)
    cache = module.VerifiedCache(tmp_path)
    return module, tmp_path, cache, runtime


class TestCertificates:
    @pytest.mark.parametrize(
        "change", ["source", "config", "command", "environment", "runtime", None]
    )
    def test_only_success_with_identical_inputs_is_reused(self, cache_repo, change):
        module, root, cache, runtime = cache_repo
        cmd, env = ["python", "check.py"], {}
        key = cache.key("generator size baseline", cmd, env)
        cache.remember(key, "failed", 1)
        assert cache.finish()
        assert cache.load(key) is None
        cache.remember(key, "passed", 0)
        if change in ("source", "config"):
            (root / ("input.py" if change == "source" else ".pylintrc")).write_text(
                "changed\n"
            )
        elif change == "command":
            cmd.append("--full")
        elif change == "environment":
            env["OPTION"] = "changed"
        elif change == "runtime":
            runtime[0] = "b" * 64
        stable = change not in ("source", "config", "runtime")
        assert cache.finish() is stable
        assert cache.load(key) == ("passed" if stable else None)
        fresh = module.VerifiedCache(root).key("generator size baseline", cmd, env)
        assert (fresh == key) is (change is None)

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
            target.mkdir()
            (target / "sample.py").write_text("original\n")
        (root / "examples").symlink_to(target)
        if external:
            with pytest.raises(OSError, match="external input"):
                module.VerifiedCache(root)
        else:
            cache = module.VerifiedCache(root)
            (target / "sample.py").write_text("changed\n")
            assert not cache.finish()
