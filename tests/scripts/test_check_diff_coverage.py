"""The changed-line gate holds added branches to the rule it holds added lines to.

``scripts/check_diff_coverage.py`` fails a branch that adds a statement no test
runs.  It now does the same for an added *branch* that only ever goes one way,
which is a different failure: the line executed, so the line check passes, and
only the arc records that the other side was never taken.

Two properties matter as much as the check itself.  It has to stay fail-open --
a run that collected no branch data must skip the arc check rather than fail
every file for lacking it -- and it must judge only the arcs whose test is on a
line this branch added, since an untaken arc in untouched code is a debt the
branch did not create.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_diff_coverage.py"


def load_script() -> Any:
    """Import the gate as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("check_diff_coverage", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_gate(
    tmp_path: Path,
    files: dict[str, dict[str, Any]],
    added: dict[str, set[int]],
    *,
    partial: bool = False,
) -> tuple[int, str]:
    """Run ``main`` against a stubbed diff and stubbed coverage payload.

    The two inputs the gate reads from the outside -- the branch diff and the
    coverage JSON -- are replaced, so the test pins the gate's own decision
    rather than whatever the repository happens to look like.
    """
    gate = load_script()
    gate._added_lines = lambda _base: added  # noqa: SLF001
    gate._diff_base = lambda: "BASE"  # noqa: SLF001
    gate._coverage_json = lambda _data_file: files  # noqa: SLF001

    argv = [str(SCRIPT), "--data-file", str(tmp_path / "unused")]
    if partial:
        argv.append("--partial")
    old = sys.argv
    sys.argv = argv
    try:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = gate.main()
        return code, buffer.getvalue()
    finally:
        sys.argv = old


def record(
    executed: list[int],
    missing: list[int],
    *,
    branches: int | None = None,
    executed_branches: list[list[int]] | None = None,
    missing_branches: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Build one file's coverage record in the shape ``coverage json`` emits."""
    got: dict[str, Any] = {
        "executed_lines": executed,
        "missing_lines": missing,
        "summary": {} if branches is None else {"num_branches": branches},
    }
    if executed_branches is not None:
        got["executed_branches"] = executed_branches
    if missing_branches is not None:
        got["missing_branches"] = missing_branches
    return got


PATH = "src/esolangs/demo.py"


class TestAddedBranches:
    def test_an_added_one_sided_branch_fails(self, tmp_path: Path) -> None:
        """The line ran, so only the arc can report the untaken side."""
        files = {
            PATH: record(
                [10, 11],
                [],
                branches=2,
                executed_branches=[[10, 11]],
                missing_branches=[[10, 12]],
            )
        }
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}})
        assert code == 1
        assert "1 added branch(es) never taken" in out
        assert "line 10 never continues to line 12" in out

    def test_an_untaken_exit_is_named_as_one(self, tmp_path: Path) -> None:
        """Coverage spells "never left the function" as a negative target."""
        files = {
            PATH: record(
                [10],
                [],
                branches=2,
                executed_branches=[[10, 11]],
                missing_branches=[[10, -5]],
            )
        }
        code, out = run_gate(tmp_path, files, {PATH: {10}})
        assert code == 1
        assert "line 10 never continues to exit" in out

    def test_an_untaken_arc_outside_the_diff_is_not_this_branch_s(
        self, tmp_path: Path
    ) -> None:
        """A one-sided branch on an untouched line is a pre-existing debt."""
        files = {
            PATH: record(
                [10, 40],
                [],
                branches=2,
                executed_branches=[[10, 11]],
                missing_branches=[[40, 42]],
            )
        }
        code, out = run_gate(tmp_path, files, {PATH: {10}})
        assert code == 0
        assert "never taken" not in out

    def test_both_sides_taken_passes_and_counts_the_branches(
        self, tmp_path: Path
    ) -> None:
        files = {
            PATH: record(
                [10],
                [],
                branches=2,
                executed_branches=[[10, 11], [10, 12]],
                missing_branches=[],
            )
        }
        code, out = run_gate(tmp_path, files, {PATH: {10}})
        assert code == 0
        assert "2 branch(es)" in out


class TestWithoutBranchData:
    def test_a_line_only_run_skips_the_arc_check(self, tmp_path: Path) -> None:
        """``pytest --cov`` without ``--cov-branch`` must still pass the gate.

        The record carries no ``num_branches``, so there is nothing to judge
        -- failing here would block every run that did not ask for arcs.
        """
        files = {PATH: record([10, 11], [])}
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}})
        assert code == 0
        assert "branch(es)" not in out

    def test_an_uncovered_added_line_still_fails(self, tmp_path: Path) -> None:
        """The original line rule is unchanged by the arc rule."""
        files = {PATH: record([10], [11])}
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}})
        assert code == 1
        assert "1 added statement(s) never executed" in out


class TestPartial:
    def test_partial_reports_an_untaken_branch_without_failing(
        self, tmp_path: Path
    ) -> None:
        """A subset run cannot tell an untaken arc from a deselected test."""
        files = {
            PATH: record(
                [10],
                [],
                branches=2,
                executed_branches=[[10, 11]],
                missing_branches=[[10, 12]],
            )
        }
        code, out = run_gate(tmp_path, files, {PATH: {10}}, partial=True)
        assert code == 0
        assert "never taken" in out
        assert "not failing" in out


class TestTheGateRuns:
    def test_the_script_executes_against_the_real_repository(self) -> None:
        """A smoke test that the module's own wiring still runs end to end.

        It is fail-open by design, so the exit code is not asserted -- only
        that invoking it neither crashes nor hangs.
        """
        got = subprocess.run(
            [sys.executable, str(SCRIPT), "--partial"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
            timeout=120,
        )
        assert got.returncode in (0, 1), got.stderr
        assert got.stdout.strip()


class TestCoverageJsonShape:
    # 1.6s: it shells out to a real coverage run to compare the shapes.
    @pytest.mark.slow
    def test_the_stub_matches_what_coverage_actually_emits(self) -> None:
        """The stubbed record above has to look like the real payload.

        A test built on an invented shape would keep passing while the gate
        read fields coverage does not emit, so the field names are checked
        against a real ``coverage json`` document once.
        """
        got = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "json",
                "-o",
                "-",
                "--data-file",
                str(REPO_ROOT / ".coverage"),
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
            timeout=180,
        )
        if got.returncode != 0 or "{" not in got.stdout:
            import pytest

            pytest.skip("no coverage data file to read")
        payload = json.loads(got.stdout[got.stdout.find("{") :])
        one = next(iter(payload["files"].values()))
        assert "executed_lines" in one
        assert "missing_lines" in one
        assert "summary" in one
