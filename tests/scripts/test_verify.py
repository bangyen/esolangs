"""The local gate may skip work, but only work CI is known to redo."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from tests.scripts.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify.py"


def load_script() -> Any:
    return load(SCRIPT)


class TestPytestScopeCollects:
    """A scoped path pytest collects nothing from fails the run it narrows."""

    def test_a_helper_module_widens(self) -> None:
        """A non-collected module under ``tests/`` is imported, not run."""
        verify = load_script()
        scope = verify._pytest_scope(["tests/tools/boolean_oracles.py"])  # noqa: SLF001
        assert scope == verify.WHOLE_SUITE

    def test_a_test_module_stays_scoped(self) -> None:
        """The widening is narrow: a real test module still runs alone."""
        verify = load_script()
        scope = verify._pytest_scope(["tests/test_vm.py"])  # noqa: SLF001
        assert scope == ["tests/test_vm.py"]

    def test_a_package_helper_widens_despite_a_matching_test_name(self) -> None:
        verify = load_script()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/interpreters/other/demo/brainfuck.py"]
        )
        assert scope == verify.WHOLE_SUITE

    def test_an_interpreter_runs_shared_contracts_and_its_generator(self) -> None:
        verify = load_script()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/interpreters/tape_based/brainfuck.py"]
        )
        assert isinstance(scope, list)
        assert set(verify.INTERPRETER_CONTRACT_TESTS) <= set(scope)
        assert "tests/interpreters/test_brainfuck.py" in scope
        assert "tests/tools/test_boolean_brainfuck.py" in scope
        assert all((REPO_ROOT / path).is_file() for path in scope)

    def test_shared_interpreter_code_still_widens(self) -> None:
        verify = load_script()
        assert verify._pytest_scope(["src/esolangs/interpreters/io.py"]) == (  # noqa: SLF001
            verify.WHOLE_SUITE
        )

    def test_the_patterns_match_pyproject(self) -> None:
        """``COLLECTED_PATTERNS`` is pytest's ``python_files``, not a guess."""
        verify = load_script()
        config = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = config["tool"]["pytest"]["ini_options"]["python_files"]
        assert list(verify.COLLECTED_PATTERNS) == patterns


class TestScopedCoverageMeasuresTheTouchedFiles:
    """A scoped run measures only what the touched-file gate will read."""

    COV = ("python", "-m", "pytest", "-q", "--cov", "--cov-branch", "--cov-report=")

    def test_touched_source_files_become_an_include_rc(self) -> None:
        """The rc names exactly the touched ``src/esolangs`` files."""
        verify = load_script()
        cmd = verify._scoped_coverage(  # noqa: SLF001
            list(self.COV),
            ["src/esolangs/vm.py", "tests/test_vm.py", "src/esolangs/tools/x.py"],
        )
        assert "--cov" in cmd
        assert "--cov-branch" not in cmd  # the rc carries branch=True
        rc = next(c for c in cmd if c.startswith("--cov-config=")).split("=", 1)[1]
        text = Path(rc).read_text(encoding="utf-8")
        assert "include =" in text
        assert "src/esolangs/vm.py" in text
        assert "src/esolangs/tools/x.py" in text
        assert "tests/test_vm.py" not in text
        assert "branch = True" in text
        assert "source" not in text  # coverage ignores include beside source

    def test_no_touched_source_file_measures_nothing(self) -> None:
        """Nothing for the gate to read means no coverage flags at all."""
        verify = load_script()
        cmd = verify._scoped_coverage(list(self.COV), ["tests/test_vm.py"])  # noqa: SLF001
        assert not any(c.startswith("--cov") for c in cmd)
        assert cmd == ["python", "-m", "pytest", "-q"]

    def test_a_command_without_coverage_is_left_alone(self) -> None:
        """The narrowing has nothing to say to a step that never measured."""
        verify = load_script()
        bare = ["python", "-m", "pytest", "-q"]
        assert verify._scoped_coverage(bare, ["src/esolangs/vm.py"]) == bare  # noqa: SLF001

    def test_the_whole_suite_fallback_still_narrows(self) -> None:
        """Widening the *tests* run does not widen the *measurement*."""
        verify = load_script()
        cmd = verify._scoped_cmd(  # noqa: SLF001
            "pytest",
            list(self.COV),
            ["tests/tools/boolean_oracles.py", "src/esolangs/vm.py"],
        )
        assert cmd is not None
        assert any(c.startswith("--cov-config=") for c in cmd)
        assert not any(c.startswith("tests/") for c in cmd)


CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _signature(cmd: list[str]) -> str:
    """The token that identifies one ``STEPS`` command inside ``ci.yml``."""
    joined = " ".join(cmd)
    found = re.search(r"scripts/[a-z_0-9]+\.py", joined)
    if found:
        return found.group(0)
    for flag in ("--directory", "--with", "-m"):
        if flag in cmd:
            return cmd[cmd.index(flag) + 1].replace("_", "-")
    return cmd[-1]


class TestCiRedoesEveryLocalStep:
    """The standing argument this module opens with, checked against CI."""

    def test_every_step_is_also_run_by_ci(self) -> None:
        verify = load_script()
        workflow = CI.read_text(encoding="utf-8")
        missing = [
            name for name, cmd in verify.STEPS if _signature(cmd) not in workflow
        ]
        assert not missing, f"steps CI does not run: {missing}"

    def test_a_step_ci_does_not_run_is_reported(self) -> None:
        """The positive control: the check above must be able to fail."""
        workflow = CI.read_text(encoding="utf-8")
        bogus = _signature(["uv", "run", "python", "scripts/no_such_check.py"])
        assert bogus not in workflow


def test_local_runs_exclude_the_weekly_band() -> None:
    """Default and full local runs leave weekly probes to the scheduler."""
    verify = load_script()
    assert verify.LOCAL_PYTEST_MARKS == "not slow and not weekly"
    assert verify.FULL_PYTEST_MARKS == "not weekly"


class TestZeroStepsIsNotAPass:
    """A run that checked nothing must not print what a green run prints."""

    @staticmethod
    def _parse(argv: list[str]) -> object:
        verify = load_script()
        with mock.patch.object(sys, "argv", ["verify.py", *argv]):
            return verify._parse_only_skip()  # noqa: SLF001

    @pytest.mark.parametrize("flag", ["--only", "--skip"])
    def test_an_unknown_step_name_is_rejected(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            self._parse([flag, "pytest-typo"])
        assert caught.value.code == 2
        assert "unknown step(s) pytest-typo" in capsys.readouterr().err

    def test_a_real_name_is_accepted(self) -> None:
        """The positive control: validation does not reject the names in use."""
        only, skip, *_ = self._parse(["--only", "pre-commit,pytest"])  # type: ignore[misc]
        assert only == {"pre-commit", "pytest"}
        assert skip is None

    def test_filters_that_cancel_out_fail(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both names are real, so validation passes and the guard catches it."""
        verify = load_script()
        monkeypatch.setenv("VERIFY_NO_SYNC", "1")
        monkeypatch.setattr(
            sys, "argv", ["verify.py", "--only", "pytest", "--skip", "pytest"]
        )
        monkeypatch.setattr(
            verify.subprocess,
            "run",
            lambda *a, **_: subprocess.CompletedProcess(a[0] if a else [], 0),
        )
        assert verify.main() == 1
        out = capsys.readouterr().out
        assert "all local checks passed" not in out
        assert "zero steps" in out


@pytest.mark.parametrize("tool", ["uv", "pylint"])
@pytest.mark.parametrize("allow", [False, True])
def test_missing_tools_never_report_complete_verification(
    tool, allow, monkeypatch, capsys
):
    verify = load_script()
    step = "bandit" if tool == "uv" else "duplicate-code check (pylint)"
    monkeypatch.setattr(
        verify, "STEPS", [(step, ["unused"]), ("available", ["unused"])]
    )
    monkeypatch.setenv("VERIFY_NO_SYNC", "1")
    argv = ["verify.py", "--only", f"{step},available"]
    if allow:
        argv.append("--allow-incomplete")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        verify.shutil, "which", lambda _: None if tool == "uv" else "/uv"
    )
    monkeypatch.setattr(
        verify.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], int(tool == "pylint")
        ),
    )
    runs = []

    def run_steps(steps, **_kwargs):
        runs.extend(name for name, _, _ in steps)
        return 0, [], 0.0

    monkeypatch.setattr(verify, "_run_steps", run_steps)
    assert verify.main() == (0 if allow else 1)
    text = capsys.readouterr().out
    assert "all local checks passed" not in text
    assert f"{tool} not installed" in text
    assert runs == (["available"] if allow else [])
    assert ("incomplete verification" if allow else "verification failed") in text


def test_shared_changes_keep_all_tests_but_measure_only_touched_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = load_script()
    monkeypatch.setattr(verify, "_ensure_dev_deps", lambda: None)
    monkeypatch.setattr(
        verify, "_parse_only_skip", lambda: (None, None, False, True, False, False)
    )
    monkeypatch.setattr(
        verify, "_scope_plan", lambda **_: (None, "verification tooling changed")
    )
    monkeypatch.setattr(
        verify,
        "_scope_changed_files",
        lambda: ("scripts/verify.py", "src/esolangs/tools/vandevelo.py"),
    )
    monkeypatch.setattr(
        verify.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0),
    )
    with mock.patch.object(verify, "_run_steps", return_value=(0, [], 0.0)) as run:
        assert verify.main() == 0
    runnable = run.call_args.args[0]
    cmd = next(cmd for name, cmd, _ in runnable if name == "pytest")
    assert not any(arg.startswith("tests/") for arg in cmd)
    rc = next(arg for arg in cmd if arg.startswith("--cov-config=")).split("=", 1)[1]
    assert "src/esolangs/tools/vandevelo.py" in Path(rc).read_text()
    assert "--cov" in cmd


def test_shadow_uv_command_cannot_resync_the_active_test_environment() -> None:
    verify = load_script()
    cmd = next(cmd for name, cmd in verify.STEPS if name == "bandit")
    assert cmd[:3] == ["uv", "run", "--no-sync"]
    assert "--with" in cmd
    assert "bandit" in cmd


@pytest.mark.medium
@pytest.mark.parametrize("returncode", [0, 3])
def test_long_step_output_is_drained_while_shadow_checks_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], returncode: int
) -> None:
    verify = load_script()
    ready = tmp_path / "ready"
    producer = (
        "import sys; from pathlib import Path; "
        "print('START' + 'x' * 1000000 + 'END', flush=True); "
        f"Path({str(ready)!r}).touch(); sys.exit({returncode})"
    )
    consumer = f"""
import time
from pathlib import Path
ready = Path({str(ready)!r})
deadline = time.monotonic() + 3
while not ready.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
assert ready.exists(), 'producer stalled on captured output'
"""
    runnable = [
        ("pytest", [sys.executable, "-c", producer], {}),
        ("shadow", [sys.executable, "-c", consumer], {}),
    ]
    failures, timings, _ = verify._run_steps(runnable, stream=False)  # noqa: SLF001
    assert failures == int(returncode != 0)
    assert {name for name, _ in timings} == {"pytest", "shadow"}
    output = capsys.readouterr().out
    if returncode:
        assert "START" + "x" * 1000000 + "END" in output
    else:
        assert "START" not in output
