"""The local gate may skip work, but only work CI is known to redo."""

import importlib.util
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify.py"


def load_script() -> object:
    """Import the verifier as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("verify", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
