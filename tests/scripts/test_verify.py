"""The local gate may skip work, but only work CI is known to redo.

``scripts/verify.py`` deselects the ``slow`` marker from a default run in both
test suites -- pytest's and ``extra/line``'s -- on the standing argument that
CI runs those tests on every push, so skipping them locally costs no coverage.
That argument only holds while the skip is exactly as narrow as it claims, so
the two halves are pinned here: the filter must reach the line step *and* it
must step aside for a caller who asked for something else, since a silently
discarded ``-m`` would turn someone's explicit selection into a different run
than the one they asked for.
"""

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

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


class TestLineAddopts:
    """``PYTEST_ADDOPTS`` for the line step composes, never clobbers."""

    def test_an_empty_environment_gets_the_filter(self) -> None:
        """The default case: nothing set, so the step deselects slow tests."""
        verify = load_script()
        assert verify._line_addopts({}) == "-m 'not slow'"  # noqa: SLF001

    def test_an_unrelated_flag_is_kept(self) -> None:
        """A caller's own option survives having the filter added to it."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-x"})  # noqa: SLF001
        assert got == "-x -m 'not slow'"

    def test_a_callers_own_marker_expression_wins(self) -> None:
        """``-m slow`` asks for the opposite set, and must not be overridden.

        Appending a second ``-m`` would leave the last one winning, so a run
        asking *for* the slow tests would silently execute none of them --
        the failure this guard exists to prevent.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m slow"})  # noqa: SLF001
        assert got == "-m slow"

    def test_the_filter_is_not_applied_twice(self) -> None:
        """Re-applying to an already-filtered environment is a no-op."""
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-m 'not slow'"})  # noqa: SLF001
        assert got == "-m 'not slow'"

    def test_the_attached_marker_spelling_also_counts(self) -> None:
        """pytest reads ``-mslow`` too, so it is just as much a choice.

        Only the separated form shows up as a bare ``-m`` token, so a plain
        membership test would miss this and append a competing expression.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "-mslow"})  # noqa: SLF001
        assert got == "-mslow"

    def test_a_long_option_is_not_mistaken_for_a_marker(self) -> None:
        """``--maxfail`` starts with neither ``-m`` nor a marker expression.

        The guard matches on the short-option prefix, and ``-m`` is pytest's
        only short option beginning that way, so a double-dashed option must
        still receive the filter.
        """
        verify = load_script()
        got = verify._line_addopts({"PYTEST_ADDOPTS": "--maxfail=1"})  # noqa: SLF001
        assert got == "--maxfail=1 -m 'not slow'"


class TestLineStepIsNamedOnce:
    """The step name is a key in three places; a typo would go unnoticed."""

    def test_the_constant_matches_the_step_table_and_its_scope(self) -> None:
        """``LINE_STEP`` is the name the table and the scope map both use.

        Each lookup is by string, so a name that drifted in one place would
        not raise -- the step would simply stop being scoped, or stop being
        filtered, with nothing to say so.
        """
        verify = load_script()
        names = [name for name, _ in verify.STEPS]
        assert verify.LINE_STEP in names
        assert verify.LINE_STEP in verify.STEP_SCOPE


class TestPytestScopeCollects:
    """A scoped path pytest collects nothing from fails the run it narrows.

    Scoping may only drop work that provably could not have broken, so a
    changed file whose tests live elsewhere has to widen rather than be run
    as though it were the test.
    """

    def test_a_helper_module_widens(self) -> None:
        """A non-collected module under ``tests/`` is imported, not run.

        Aimed at itself it collects nothing, which pytest exits non-zero for
        -- the failure this guards against -- and the tests that import it
        are not named by the path, so only the whole suite covers it.
        """
        verify = load_script()
        scope = verify._pytest_scope(["tests/tools/boolean_oracles.py"])  # noqa: SLF001
        assert scope == verify.WHOLE_SUITE

    def test_a_test_module_stays_scoped(self) -> None:
        """The widening is narrow: a real test module still runs alone."""
        verify = load_script()
        scope = verify._pytest_scope(["tests/test_vm.py"])  # noqa: SLF001
        assert scope == ["tests/test_vm.py"]

    def test_the_patterns_match_pyproject(self) -> None:
        """``COLLECTED_PATTERNS`` is pytest's ``python_files``, not a guess.

        A pattern here that pyproject does not share would either widen for
        files pytest collects or, worse, scope to files it does not.
        """
        verify = load_script()
        config = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = config["tool"]["pytest"]["ini_options"]["python_files"]
        assert list(verify.COLLECTED_PATTERNS) == patterns


CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _signature(cmd: list[str]) -> str:
    """The token that identifies one ``STEPS`` command inside ``ci.yml``.

    A step is identified by what it *runs*, not by its display name: the two
    files name the same check differently ("docstring check" against "Check
    interpreter docstrings"), so matching on names would pin the prose and
    miss the thing that matters.  ``--directory`` comes before ``--with``
    because the line step carries both and its directory is the distinctive
    half; a bare ``-q`` tail is not distinctive at all.
    """
    joined = " ".join(cmd)
    found = re.search(r"scripts/[a-z_0-9]+\.py", joined)
    if found:
        return found.group(0)
    for flag in ("--directory", "--with", "-m"):
        if flag in cmd:
            return cmd[cmd.index(flag) + 1].replace("_", "-")
    return cmd[-1]


class TestCiRedoesEveryLocalStep:
    """The standing argument this module opens with, checked against CI.

    ``verify.py`` narrows a default run -- it deselects ``slow`` and skips
    :data:`FULL_ONLY` outright -- and every one of those subtractions is
    justified by CI redoing the work on every push.  That argument is only
    sound while CI actually runs each step, and nothing enforced it: a check
    added to ``STEPS`` and not to ``ci.yml`` would leave the local gate
    skipping work in the belief that CI covers it, with no failure anywhere.
    """

    def test_every_step_is_also_run_by_ci(self) -> None:
        verify = load_script()
        workflow = CI.read_text(encoding="utf-8")
        missing = [
            name for name, cmd in verify.STEPS if _signature(cmd) not in workflow
        ]
        assert not missing, f"steps CI does not run: {missing}"

    def test_a_step_ci_does_not_run_is_reported(self) -> None:
        """The positive control: the check above must be able to fail.

        Every signature matching is the expected result, so the assertion
        proves nothing on its own -- a derivation that silently produced an
        empty list, or a token as common as ``-q``, would pass it just as
        well.
        """
        workflow = CI.read_text(encoding="utf-8")
        bogus = _signature(["uv", "run", "python", "scripts/no_such_check.py"])
        assert bogus not in workflow

    def test_the_skipped_step_is_one_ci_re_derives(self) -> None:
        """``FULL_ONLY`` is skipped locally *because* CI redoes it.

        This is the subtraction with the least margin -- the step does not
        run at push time at all -- so it is pinned by name rather than left
        to the sweep above.
        """
        verify = load_script()
        workflow = CI.read_text(encoding="utf-8")
        by_name = dict(verify.STEPS)
        for name in verify.FULL_ONLY:
            assert _signature(by_name[name]) in workflow, name


class TestHeavyStepsAreNotRunInPytestsShadow:
    """The shadow is only free for steps that use one core.

    Filling it with everything was the whole cost of a push: measured alone,
    pytest took 39.8s and the leak sweep 35.6s, and run together they took
    137.3s and 85.4s.  Neither step was slow; they were fighting each other
    for a 10-core machine.  So a step that is parallel in its own right waits
    for pytest to join, and the ordering that makes that true is pinned here.
    """

    def test_the_heavy_names_are_real_steps(self) -> None:
        """A name that drifted would stop deferring, silently.

        ``HEAVY_STEPS`` is matched against the step table by string, so a
        renamed step would not raise -- it would quietly go back to running
        beside pytest, which is the thing this exists to prevent.
        """
        verify = load_script()
        names = {name for name, _ in verify.STEPS}
        assert names >= verify.HEAVY_STEPS
        assert verify.LEAK_STEP in verify.HEAVY_STEPS

    def test_a_heavy_step_runs_after_pytest_not_beside_it(self) -> None:
        """Order: tree-mutating, then the cheap steps, then pytest, then heavy.

        The timings come back in completion order, so this reads the schedule
        off the result rather than off the source.  ``pytest`` landing before
        the leak sweep is the point: in the old runner it landed last, because
        it had been left racing everything else.
        """
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
        """The gate reads the data file pytest writes, so it waits for it.

        It also has to come *before* the heavy steps: it is 0.2s, it unblocks
        nothing, and running it last would add that wait to a push for no
        reason.
        """
        verify = load_script()
        noop = [sys.executable, "-c", ""]
        runnable = [(name, noop, {}) for name in ("pytest", "bandit", verify.LEAK_STEP)]
        gate = (verify.DIFF_COVERAGE_STEP, noop, {})
        _, timings, _ = verify._run_steps(runnable, stream=False, gate=gate)  # noqa: SLF001
        order = [name for name, _ in timings]
        assert order.index("pytest") < order.index(verify.DIFF_COVERAGE_STEP)
        assert order.index(verify.DIFF_COVERAGE_STEP) < order.index(verify.LEAK_STEP)


class TestOutputIsReplayedNotStreamed:
    """A passing stack says nothing; a failing one says why.

    The hook runs the whole stack, where streaming every step buries the one
    line that matters.  A run of a single step is the opposite case, and the
    two flags are the override in each direction.
    """

    def test_a_stack_replays_only_failures(self) -> None:
        verify = load_script()
        assert not verify._should_stream(5, quiet=False, verbose=False)  # noqa: SLF001

    def test_a_single_step_streams(self) -> None:
        """`just test-py` is asking to watch pytest run."""
        verify = load_script()
        assert verify._should_stream(1, quiet=False, verbose=False)  # noqa: SLF001

    def test_quiet_forbids_streaming_even_alone(self) -> None:
        """`just test-quick` passes --quiet and means it."""
        verify = load_script()
        assert not verify._should_stream(1, quiet=True, verbose=False)  # noqa: SLF001

    def test_verbose_streams_the_whole_stack(self) -> None:
        verify = load_script()
        assert verify._should_stream(5, quiet=False, verbose=True)  # noqa: SLF001
