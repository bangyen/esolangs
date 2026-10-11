"""Touched files and partial-run additions meet the same 90% coverage floor."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.scripts.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_diff_coverage.py"


def load_script() -> Any:
    return load(SCRIPT)


def run_gate(
    tmp_path: Path,
    files: dict[str, dict[str, Any]],
    added: dict[str, set[int]],
    *,
    partial: bool = False,
) -> tuple[int, str]:
    """Run ``main`` against a stubbed diff and stubbed coverage payload."""
    gate = load_script()
    gate._added_lines = lambda _base: added  # noqa: SLF001
    gate._diff_base = lambda: "BASE"  # noqa: SLF001
    gate._coverage_json = lambda _data_file, _targets: files  # noqa: SLF001

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


def test_deletion_only_diff_keeps_surviving_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = load_script()
    diff = (
        f"--- a/{PATH}\n+++ b/{PATH}\n@@ -20 +19,0 @@\n-removed()\n"
        "--- a/src/esolangs/deleted.py\n+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n-removed()\n-removed()\n"
    )
    monkeypatch.setattr(gate, "diff_paths", lambda *_args: [PATH])
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, diff.encode(), b""
        ),
    )
    added = gate._added_lines("BASE")  # noqa: SLF001
    assert added == {PATH: set()}
    code, out = run_gate(tmp_path, {PATH: record([1], [2])}, added)
    assert code == 1
    assert f"{PATH}: 2" in out


def test_non_python_package_data_is_outside_coverage(tmp_path: Path) -> None:
    """Generated examples cannot have Python execution coverage."""
    example = "src/esolangs/examples/demo.txt"
    code, out = run_gate(tmp_path, {}, {example: {1}})
    assert code == 0
    assert "branch touched no files" in out


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
        assert "1 branch(es) never taken" in out
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

    def test_an_untaken_arc_outside_the_diff_still_fails_the_file(
        self, tmp_path: Path
    ) -> None:
        """Touching a file answers for its one-sided branches too."""
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
        assert code == 1
        assert "line 40 never continues to line 42" in out

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
        """``pytest --cov`` without ``--cov-branch`` must still pass the gate."""
        files = {PATH: record([10, 11], [])}
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}})
        assert code == 0
        assert "branch(es)" not in out

    def test_an_uncovered_line_still_fails(self, tmp_path: Path) -> None:
        """The line rule is unchanged by the arc rule."""
        files = {PATH: record([10], [11])}
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}})
        assert code == 1
        assert "1 statement(s) never executed" in out


class TestPartial:
    def test_partial_fails_on_an_added_untaken_branch(self, tmp_path: Path) -> None:
        """An added branch is cheap evidence the PR must supply."""
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
        assert code == 1
        assert "never taken" in out
        assert "require at least 90%" in out

    def test_partial_does_not_fail_on_a_gap_outside_the_diff(
        self, tmp_path: Path
    ) -> None:
        """A deselected slow test may be the evidence for an old line."""
        files = {PATH: record([10], [40])}
        code, out = run_gate(tmp_path, files, {PATH: {10}}, partial=True)
        assert code == 0
        assert "line(s)" not in out
        assert "not failing on gaps outside added lines" in out

    def test_partial_fails_on_an_uncovered_added_statement(
        self, tmp_path: Path
    ) -> None:
        files = {PATH: record([10], [11])}
        code, out = run_gate(tmp_path, files, {PATH: {10, 11}}, partial=True)
        assert code == 1
        assert "require at least 90%" in out


class TestTheGateRuns:
    @pytest.mark.slow
    def test_the_script_executes_against_the_real_repository(self) -> None:
        """A smoke test that the module's own wiring still runs end to end."""
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
        """The stubbed record above has to look like the real payload."""
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


@pytest.mark.parametrize("failure", ["base", "diff", "coverage", "branches"])
@pytest.mark.parametrize("strict", [False, True])
def test_missing_evidence_fails_only_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    *,
    strict: bool,
) -> None:
    gate = load_script()
    monkeypatch.setattr(
        gate, "_diff_base", lambda: None if failure == "base" else "BASE"
    )
    monkeypatch.setattr(
        gate,
        "_added_lines",
        lambda _base: None if failure == "diff" else {"src/esolangs/a.py": {1}},
    )
    monkeypatch.setattr(
        gate,
        "_coverage_json",
        lambda _data, _targets: (
            None
            if failure == "coverage"
            else {
                "src/esolangs/a.py": record(
                    [1], [], branches=None if failure == "branches" else 0
                )
            }
        ),
    )
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *(["--strict"] if strict else [])])
    assert gate.main() == int(strict)


def test_strict_gate_allows_a_diff_without_measured_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = load_script()
    monkeypatch.setattr(gate, "_diff_base", lambda: "BASE")
    monkeypatch.setattr(gate, "_added_lines", lambda _base: {"README.md": {1}})
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--strict"])
    assert gate.main() == 0


@pytest.mark.parametrize("partial", [False])
@pytest.mark.parametrize("kind", ["statements", "branches"])
@pytest.mark.parametrize(("covered", "expected"), [(8, 1), (9, 0)])
def test_per_file_coverage_floor(tmp_path, partial, kind, covered, expected):
    lines = list(range(1, 11))
    if kind == "statements":
        data = record(lines[:covered], lines[covered:])
    else:
        arcs = [[1, target] for target in range(2, 12)]
        data = record(
            [1],
            [],
            branches=10,
            executed_branches=arcs[:covered],
            missing_branches=arcs[covered:],
        )
    code, _ = run_gate(tmp_path, {PATH: data}, {PATH: set(lines)}, partial=partial)
    assert code == expected


def test_one_well_covered_file_cannot_hide_another(tmp_path):
    files = {
        PATH: record([1], [2]),
        "src/esolangs/large.py": record(list(range(100)), []),
    }
    code, _ = run_gate(tmp_path, files, {path: {1, 2} for path in files})
    assert code == 1


@pytest.mark.parametrize(
    "name",
    [
        "space name.py",
        'quote"name.py',
        "line\nname.py",
        "line\r\nname.py",
        "[literal]*.py",
        "unicode-é.py",
    ],
)
def test_diff_uses_exact_git_paths(tmp_path, monkeypatch, name):
    gate = load_script()
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / name
    path.write_text("first = 1\n")
    subprocess.run(["git", "add", "--", name], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    path.write_text("first = 1\nsecond = 2\n")
    assert gate._added_lines("HEAD") == {name: {2}}  # noqa: SLF001
