r"""The local gate may skip work, but only work CI is known to redo."""

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify.py"


def load_script() -> object:
    r"""Import the verifier as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("verify", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLineAddopts:
    r"""``PYTEST_ADDOPTS`` for the line step composes, never clobbers."""

    def test_an_empty_environment_gets_the_filter(self) -> None:
        r"""The default case: nothing set, so the step deselects slow tests."""
        verify = load_script()
        assert verify._line_addopts({}) == "-m 'not slow'"  # noqa: SLF001

    def test_an_unrelated_flag_is_kept(self) -> None:
        r"""A caller's own option survives having the filter added to it."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-x"})  # noqa: SLF001
        assert got == "-x -m 'not slow'"

    def test_a_callers_own_marker_expression_wins(self) -> None:
        r"""``-m slow`` asks for the opposite set, and must not be overridden."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m slow"})  # noqa: SLF001
        assert got == "-m slow"

    def test_the_filter_is_not_applied_twice(self) -> None:
        r"""Re-applying to an already-filtered environment is a no-op."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m 'not slow'"})  # noqa: SLF001
        assert got == "-m 'not slow'"

    def test_the_attached_marker_spelling_also_counts(self) -> None:
        r"""pytest reads ``-mslow`` too, so it is just as much a choice."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-mslow"})  # noqa: SLF001
        assert got == "-mslow"

    def test_a_long_option_is_not_mistaken_for_a_marker(self) -> None:
        r"""``--maxfail`` starts with neither ``-m`` nor a marker expression."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "--maxfail=1"})  # noqa: SLF001
        assert got == "--maxfail=1 -m 'not slow'"


class TestLineStepIsNamedOnce:
    r"""The step name is a key in three places; a typo would go unnoticed."""

    def test_the_constant_matches_the_step_table_and_its_scope(self) -> None:
        r"""``LINE_STEP`` is the name the table and the scope map both use."""
        verify = load_script()
        names = [name for name, _ in verify.STEPS]
        assert verify.LINE_STEP in names
        assert verify.LINE_STEP in verify.STEP_SCOPE


class TestPytestScopeCollects:
    r"""A scoped path pytest collects nothing from fails the run it narrows."""

    def test_a_helper_module_widens(self) -> None:
        r"""A non-collected module under ``tests/`` is imported, not run."""
        verify = load_script()
        scope = verify._pytest_scope(["tests/tools/boolean_oracles.py"])  # noqa: SLF001
        assert scope == verify.WHOLE_SUITE

    def test_a_test_module_stays_scoped(self) -> None:
        r"""The widening is narrow: a real test module still runs alone."""
        verify = load_script()
        scope = verify._pytest_scope(["tests/test_vm.py"])  # noqa: SLF001
        assert scope == ["tests/test_vm.py"]

    def test_the_patterns_match_pyproject(self) -> None:
        r"""``COLLECTED_PATTERNS`` is pytest's ``python_files``, not a guess."""
        verify = load_script()
        config = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = config["tool"]["pytest"]["ini_options"]["python_files"]
        assert list(verify.COLLECTED_PATTERNS) == patterns


CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _signature(cmd: list[str]) -> str:
    r"""The token that identifies one ``STEPS`` command inside ``ci.yml``."""
    joined = " ".join(cmd)
    found = re.search(r"scripts/[a-z_0-9]+\.py", joined)
    if found:
        return found.group(0)
    for flag in ("--directory", "--with", "-m"):
        if flag in cmd:
            return cmd[cmd.index(flag) + 1].replace("_", "-")
    return cmd[-1]


class TestCiRedoesEveryLocalStep:
    r"""The standing argument this module opens with, checked against CI."""

    def test_every_step_is_also_run_by_ci(self) -> None:
        verify = load_script()
        workflow = CI.read_text(encoding="utf-8")
        missing = [
            name for name, cmd in verify.STEPS if _signature(cmd) not in workflow
        ]
        assert not missing, f"steps CI does not run: {missing}"

    def test_a_step_ci_does_not_run_is_reported(self) -> None:
        r"""The positive control: the check above must be able to fail."""
        workflow = CI.read_text(encoding="utf-8")
        bogus = _signature(["uv", "run", "python", "scripts/no_such_check.py"])
        assert bogus not in workflow

    def test_the_skipped_step_is_one_ci_re_derives(self) -> None:
        r"""``FULL_ONLY`` is skipped locally *because* CI redoes it."""
        verify = load_script()
        workflow = CI.read_text(encoding="utf-8")
        by_name = dict(verify.STEPS)
        for name in verify.FULL_ONLY:
            assert _signature(by_name[name]) in workflow, name


# 6.2s over 9 tests: spawns.
@pytest.mark.medium
# 6.2s over 9 tests: spawns.
@pytest.mark.medium
class TestHeavyStepsAreNotRunInPytestsShadow:
    r"""The shadow is only free for steps that use one core."""

    def test_the_heavy_names_are_real_steps(self) -> None:
        r"""A name that drifted would stop deferring, silently."""
        verify = load_script()
        names = {name for name, _ in verify.STEPS}
        assert names >= verify.HEAVY_STEPS
        assert verify.LEAK_STEP in verify.HEAVY_STEPS

    def test_a_heavy_step_runs_after_pytest_not_beside_it(self) -> None:
        r"""Order: tree-mutating, then the cheap steps, then pytest, then heavy."""
        verify = load_script()
        noop = [sys.executable, "-c", ""]
        runnable = [
            (name, noop, {})
            for name in ("pre-commit", verify.LEAK_STEP, "bandit", "pytest")
        ]
        failures, timings, _ = verify._run_steps(runnable, stream=False)  # noqa: SLF001
        assert failures == 0
        assert [name for name, _ in timings] == [
            "pre-commit",
            "bandit",
            "pytest",
            verify.LEAK_STEP,
        ]

    def test_the_coverage_gate_still_follows_pytest(self) -> None:
        r"""The gate reads the data file pytest writes, so it waits for it."""
        verify = load_script()
        noop = [sys.executable, "-c", ""]
        runnable = [(name, noop, {}) for name in ("pytest", "bandit", verify.LEAK_STEP)]
        gate = (verify.DIFF_COVERAGE_STEP, noop, {})
        _, timings, _ = verify._run_steps(runnable, stream=False, gate=gate)  # noqa: SLF001
        order = [name for name, _ in timings]
        assert order.index("pytest") < order.index(verify.DIFF_COVERAGE_STEP)
        assert order.index(verify.DIFF_COVERAGE_STEP) < order.index(verify.LEAK_STEP)


class TestOutputIsReplayedNotStreamed:
    r"""A passing stack says nothing; a failing one says why."""

    def test_a_stack_replays_only_failures(self) -> None:
        verify = load_script()
        assert not verify._should_stream(5, quiet=False, verbose=False)  # noqa: SLF001

    def test_a_single_step_streams(self) -> None:
        r"""`just test-py` is asking to watch pytest run."""
        verify = load_script()
        assert verify._should_stream(1, quiet=False, verbose=False)  # noqa: SLF001

    def test_quiet_forbids_streaming_even_alone(self) -> None:
        r"""`just test-quick` passes --quiet and means it."""
        verify = load_script()
        assert not verify._should_stream(1, quiet=True, verbose=False)  # noqa: SLF001

    def test_verbose_streams_the_whole_stack(self) -> None:
        verify = load_script()
        assert verify._should_stream(5, quiet=False, verbose=True)  # noqa: SLF001
