"""The assembly cache must never serve a binary for different assembly.

``scripts/riscv_elf_runner.assemble_source`` caches assembled ELFs on disk,
which takes the 121-case unicorn round-trip from 31s to 0.08s once warm.  The
round-trip it feeds is the only check that can see a compiler emitting output
which assembles, runs, and computes the wrong thing -- so a cache that could
return a stale ELF would retire that check while leaving it green.

What that costs is a key strong enough to make staleness impossible: the
assembly text (so any codegen change misses) and the toolchain version (so a
gcc upgrade re-assembles, since the text alone cannot notice the assembler
changing underneath it).  These tests pin both, plus the fallbacks that keep
the cache an optimisation rather than a correctness dependency.

No cross-compiler is needed: every test here drives the caching layer with a
stub compile, so they run on any machine.
"""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "riscv_elf_runner.py"

pytest.importorskip("unicorn", reason="riscv_elf_runner imports unicorn at import")


def load_script() -> Any:
    """Import the runner as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("riscv_elf_runner", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The runner with its cache pointed at a scratch directory.

    ``XDG_CACHE_HOME`` rather than patching ``_cache_dir``: it is the same
    switch a user has, so the test exercises the real lookup path.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("ESOLANGS_NO_ELF_CACHE", raising=False)
    module = load_script()
    monkeypatch.setattr(module, "_toolchain_id", lambda: "stub-gcc 1.0")
    return module


def _counting_compile(module: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the real compile with one that records what it assembled."""
    seen: list[str] = []

    def fake(assembly: str) -> bytes:
        seen.append(assembly)
        return f"ELF:{assembly}".encode()

    monkeypatch.setattr(module, "_compile", fake)
    return seen


class TestCacheHits:
    """A hit must mean the bytes gcc produced for this exact input."""

    def test_second_call_does_not_reassemble(
        self, runner: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same assembly is compiled once and served from disk after."""
        seen = _counting_compile(runner, monkeypatch)
        first = runner.assemble_source("nop\n")
        second = runner.assemble_source("nop\n")
        assert first == second == b"ELF:nop\n"
        assert seen == ["nop\n"], "the second call re-assembled"

    def test_a_codegen_change_misses(
        self, runner: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Different assembly never resolves to an existing entry.

        The case the cache exists to not break: a compiler whose codegen
        changed emits different text, so the old ELF must not come back.
        """
        seen = _counting_compile(runner, monkeypatch)
        runner.assemble_source("addi a0, a0, 1\n")
        changed = runner.assemble_source("addiw a0, a0, 1\n")
        assert changed == b"ELF:addiw a0, a0, 1\n"
        assert len(seen) == 2, "a codegen change was served from cache"

    def test_a_toolchain_upgrade_misses(
        self, runner: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new gcc re-assembles identical text.

        The content key cannot see the assembler change underneath it, so
        the version rides in the key: otherwise an upgrade would be proven
        only against ELFs the previous gcc produced.
        """
        seen = _counting_compile(runner, monkeypatch)
        runner.assemble_source("nop\n")
        monkeypatch.setattr(runner, "_toolchain_id", lambda: "stub-gcc 2.0")
        runner.assemble_source("nop\n")
        assert len(seen) == 2, "a toolchain upgrade was served from cache"


class TestCacheIsOptional:
    """The cache is a speedup; nothing may depend on it working."""

    def test_the_opt_out_always_compiles(
        self, runner: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ESOLANGS_NO_ELF_CACHE`` bypasses both read and write."""
        seen = _counting_compile(runner, monkeypatch)
        monkeypatch.setenv("ESOLANGS_NO_ELF_CACHE", "1")
        runner.assemble_source("nop\n")
        runner.assemble_source("nop\n")
        assert len(seen) == 2, "the opt-out still read the cache"

    def test_an_unwritable_cache_still_returns_the_binary(
        self, runner: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cache directory that cannot be created is not an error.

        Read-only home, full disk, sandbox: the compile already succeeded,
        so the caller gets its ELF and only the speedup is lost.
        """
        seen = _counting_compile(runner, monkeypatch)

        def refuse(*_args: object, **_kwargs: object) -> None:
            raise OSError("read-only file system")

        monkeypatch.setattr(Path, "mkdir", refuse)
        assert runner.assemble_source("nop\n") == b"ELF:nop\n"
        assert seen == ["nop\n"]
