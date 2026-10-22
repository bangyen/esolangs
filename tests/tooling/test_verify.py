"""The local gate may skip work, but only work CI is known to redo."""

import errno
import io
import os
import re
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify" / "gate.py"
SCOPE_SCRIPT = REPO_ROOT / "scripts" / "verify" / "scope.py"


def load_script() -> Any:
    return load(SCRIPT)


def load_scope() -> Any:
    return load(SCOPE_SCRIPT)


class TestPytestScopeCollects:
    @pytest.mark.parametrize(
        ("path", "scoped"),
        [
            ("src/esolangs/languages/polynomial/tests/polynomial_support.py", False),
            ("tests/runtime/test_vm.py", True),
            ("src/esolangs/runtime/demo/brainfuck.py", False),
            ("src/esolangs/runtime/io.py", False),
        ],
    )
    def test_only_collected_leaf_modules_are_scoped(self, path, scoped) -> None:
        verify = load_scope()
        scope = verify._pytest_scope([path])  # noqa: SLF001
        assert scope == ([path] if scoped else verify.WHOLE_SUITE)

    def test_an_interpreter_runs_shared_contracts_and_its_generator(self) -> None:
        verify = load_scope()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/languages/brainfuck/interpreter.py"]
        )
        assert isinstance(scope, list)
        assert set(verify.INTERPRETER_CONTRACT_TESTS) <= set(scope)
        assert "src/esolangs/languages/brainfuck/tests/test_brainfuck.py" in scope
        assert (
            "src/esolangs/languages/brainfuck/tests/test_boolean_brainfuck.py" in scope
        )
        assert all((REPO_ROOT / path).is_file() for path in scope)

    def test_the_patterns_match_pyproject(self) -> None:
        config = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = config["tool"]["pytest"]["ini_options"]["python_files"]
        assert list(load_scope().COLLECTED_PATTERNS) == patterns


CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _signature(cmd: list[str]) -> str:
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
        workflow = CI.read_text(encoding="utf-8") + (
            CI.with_name("weekly.yml").read_text(encoding="utf-8")
        )
        missing = [
            name for name, cmd in verify.STEPS if _signature(cmd) not in workflow
        ]
        assert not missing, f"steps CI does not run: {missing}"

    def test_diff_coverage_step_matches_ci_and_is_manual_only(self) -> None:
        verify = load_script()
        assert "diff coverage" in verify.MANUAL_ONLY
        cmd = dict(verify.STEPS)["diff coverage"]
        assert cmd[-3:] == [
            "checks/check_diff_coverage.py",
            "--partial",
            "--strict",
        ]
        assert "check_diff_coverage.py --partial --strict" in CI.read_text(
            encoding="utf-8"
        )

    def test_a_step_ci_does_not_run_is_reported(self) -> None:
        workflow = CI.read_text(encoding="utf-8") + (
            CI.with_name("weekly.yml").read_text(encoding="utf-8")
        )
        bogus = _signature(["uv", "run", "python", "scripts/no_such_check.py"])
        assert bogus not in workflow


@pytest.mark.parametrize(("path", "size"), [("", 0), ("README.md", 1), ("src/x.py", 1)])
def test_local_test_selection(path, size) -> None:
    verify = load_script()
    assert verify.LOCAL_PYTEST_MARKS == "not slow and not weekly"
    assert verify.FULL_PYTEST_MARKS == "not weekly"
    assert len(verify.local_tooling_deselections([path] if path else [])) == size


class TestZeroStepsIsNotAPass:
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
        only, skip, *_ = self._parse(["--only", "pre-commit,pytest"])
        assert only == {"pre-commit", "pytest"}
        assert skip is None

    def test_filters_that_cancel_out_fail(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
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


@pytest.mark.parametrize("allow", [False, True])
def test_missing_tools_never_report_complete_verification(
    allow, monkeypatch, capsys
) -> None:
    verify = load_script()
    step = "duplicate-code check (pylint)"
    monkeypatch.setattr(
        verify, "STEPS", [(step, ["unused"]), ("available", ["unused"])]
    )
    monkeypatch.setenv("VERIFY_NO_SYNC", "1")
    argv = ["verify.py", "--only", f"{step},available"]
    if allow:
        argv.append("--allow-incomplete")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        verify,
        "run_bounded",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1),
    )
    runs = []

    def run_steps(steps, **_kwargs):
        runs.extend(name for name, _, _ in steps)
        return [], [], 0.0

    monkeypatch.setattr(verify, "_run_steps", run_steps)
    assert verify.main() == (0 if allow else 1)
    text = capsys.readouterr().out
    assert "all local checks passed" not in text
    assert "pylint not installed" in text
    assert runs == (["available"] if allow else [])
    assert ("incomplete verification" if allow else "verification failed") in text


@pytest.mark.parametrize("full", [False, True])
def test_shared_changes_keep_all_tests_without_local_coverage(
    monkeypatch: pytest.MonkeyPatch,
    full,
) -> None:
    verify = load_script()
    monkeypatch.setattr(verify, "_ensure_dev_deps", lambda: None)
    monkeypatch.setattr(
        verify, "_parse_only_skip", lambda: (None, None, full, True, False, False)
    )
    monkeypatch.setattr(
        verify, "_scope_plan", lambda **_: (None, "verification tooling changed")
    )
    monkeypatch.setattr(
        verify,
        "_scope_changed_files",
        lambda: ("scripts/verify/gate.py", "src/esolangs/generation/vandevelo.py"),
    )
    monkeypatch.setattr(
        verify,
        "run_bounded",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0),
    )
    with mock.patch.object(verify, "_run_steps", return_value=([], [], 0.0)) as run:
        assert verify.main() == 0
    runnable = run.call_args.args[0]
    cmd = next(cmd for name, cmd, _ in runnable if name == "pytest")
    assert not any(arg.startswith("tests/") for arg in cmd)
    assert not any(arg.startswith("--cov") for arg in cmd)
    assert {name for name, _, _ in runnable} == {
        "pre-commit",
        "mypy (src + scripts)",
        "pytest",
    }


def test_failures_close_the_run_with_their_cause(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verify = load_script()
    monkeypatch.setattr(verify, "_ensure_dev_deps", lambda: None)
    monkeypatch.setattr(
        verify, "_parse_only_skip", lambda: (None, None, True, True, False, False)
    )
    monkeypatch.setattr(verify, "_scope_plan", lambda **_: (None, "test"))
    monkeypatch.setattr(verify, "_scope_changed_files", lambda: ())
    monkeypatch.setattr(
        verify, "run_bounded", lambda *_a, **_kw: subprocess.CompletedProcess([], 0)
    )
    result = ([("pytest", 124, None), ("mypy", 1, None)], [("pytest", 9.0)], 9.0)
    with mock.patch.object(verify, "_run_steps", return_value=result):
        assert verify.main() == 1
    tail = capsys.readouterr().out.split("WALL")[1]
    assert "[FAIL] pytest: deadline exceeded" in tail
    assert "[FAIL] mypy: exit 1" in tail
    assert tail.rstrip().endswith("2 check(s) failed")


def test_a_failure_names_its_log_and_failing_tests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without these a reader reran a full-tree pytest to learn one test's name."""
    verify = load_script()
    monkeypatch.setattr(verify, "_ensure_dev_deps", lambda: None)
    monkeypatch.setattr(
        verify, "_parse_only_skip", lambda: (None, None, True, True, False, False)
    )
    monkeypatch.setattr(verify, "_scope_plan", lambda **_: (None, "test"))
    monkeypatch.setattr(verify, "_scope_changed_files", lambda: ())
    monkeypatch.setattr(
        verify, "run_bounded", lambda *_a, **_kw: subprocess.CompletedProcess([], 0)
    )
    many = "".join(f"FAILED tests/t.py::test_{i} - boom\n" for i in range(12))
    output = "[log] notes/verification/pytest-x.log\nnoise\n" + many
    result = ([("pytest", 1, output)], [("pytest", 9.0)], 9.0)
    with mock.patch.object(verify, "_run_steps", return_value=result):
        assert verify.main() == 1
    summary = capsys.readouterr().out.split("[FAIL] pytest: exit 1")[1]
    assert "  [log] notes/verification/pytest-x.log" in summary
    assert "  FAILED tests/t.py::test_0 - boom" in summary
    assert "test_10" not in summary
    assert "... and 2 more in the log" in summary
    assert "noise" not in summary


def _run_gate(monkeypatch: pytest.MonkeyPatch, verify: Any, failures: list) -> int:
    """Drive ``verify.main`` with ``_run_steps`` returning canned *failures*."""
    monkeypatch.setattr(verify, "_ensure_dev_deps", lambda: None)
    monkeypatch.setattr(
        verify, "_parse_only_skip", lambda: (None, None, True, True, False, False)
    )
    monkeypatch.setattr(verify, "_scope_plan", lambda **_: (None, "test"))
    monkeypatch.setattr(verify, "_scope_changed_files", lambda: ())
    monkeypatch.setattr(
        verify, "run_bounded", lambda *_a, **_kw: subprocess.CompletedProcess([], 0)
    )
    result = (failures, [("pytest", 9.0)], 9.0)
    with mock.patch.object(verify, "_run_steps", return_value=result):
        return verify.main()


def _pytest_output(*sections: tuple[str, str]) -> str:
    """Assemble a pytest -q log: FAILURES sections, then the summary lines.

    The summary's FAILED lines carry no reason -- pytest drops a
    manufactured failure's message there -- so a duration violation's text
    lives in its section.  The ``[log]`` path names no real file, so the
    gate classifies from this excerpt rather than a complete log.
    """
    lines = ["[log] notes/verification/pytest-canned.log", "=== FAILURES ==="]
    for title, body in sections:
        lines += [f"____ {title} ____", body]
    lines.append("=== short test summary info ===")
    lines += [f"FAILED tests/t.py::{title}" for title, _ in sections]
    return "\n".join(lines) + "\n"


_DURATION_A = (
    "test_a",
    "1.23s exceeds the fast band limit of 1s; "
    "optimize, delete, or mark this test medium. Under -n load ...",
)
_DURATION_B = (
    "test_b",
    "12.34s exceeds the medium band limit of 10s; "
    "optimize, delete, or mark this test slow. Under -n load ...",
)


def test_solo_rerun_pass_turns_duration_failures_into_a_load_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verify = load_script()
    seen: list[list[str]] = []

    def rerun_alone(ids: list[str]) -> tuple[int, str]:
        seen.append(ids)
        return 0, ""

    monkeypatch.setattr(verify, "_rerun_alone", rerun_alone)
    output = _pytest_output(_DURATION_A, _DURATION_B)
    assert _run_gate(monkeypatch, verify, [("pytest", 1, output)]) == 0
    assert seen == [["tests/t.py::test_a", "tests/t.py::test_b"]]
    out = capsys.readouterr().out
    assert "[load] pytest: all 2 failed tests passed alone" in out
    assert "rerun the gate on a quiet machine before pushing" in out
    tail = out.split("WALL")[1]
    assert "[FAIL] pytest" not in tail
    assert out.rstrip().endswith("all local checks passed")


def test_solo_rerun_failure_keeps_the_step_failed_and_names_the_real_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verify = load_script()
    monkeypatch.setattr(
        verify,
        "_rerun_alone",
        lambda _ids: (1, "FAILED tests/t.py::test_b\n"),
    )
    output = _pytest_output(_DURATION_A, _DURATION_B)
    assert _run_gate(monkeypatch, verify, [("pytest", 1, output)]) == 1
    out = capsys.readouterr().out
    assert "[load] pytest: 1 of 2 failures still fail alone: tests/t.py::test_b" in out
    assert "[FAIL] pytest: exit 1" in out.split("WALL")[1]
    assert out.rstrip().endswith("1 check(s) failed")


def test_real_failures_are_not_rerun(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    verify = load_script()

    def rerun_alone(_ids: list[str]) -> tuple[int, str]:
        raise AssertionError("a real failure must not engage the load verdict")

    monkeypatch.setattr(verify, "_rerun_alone", rerun_alone)
    output = _pytest_output(("test_a", "assert 1 == 2"))
    assert _run_gate(monkeypatch, verify, [("pytest", 1, output)]) == 1
    out = capsys.readouterr().out
    assert "[load]" not in out
    assert "[FAIL] pytest: exit 1" in out


def test_failures_whose_sections_were_cut_are_not_rerun(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bounded excerpt can keep the summary and lose the FAILURES sections.

    Without the sections nothing proves the failures were duration overruns,
    so the verdict must not engage -- the failure stands as reported.
    """
    verify = load_script()

    def rerun_alone(_ids: list[str]) -> tuple[int, str]:
        raise AssertionError("an unprovable failure must not engage the verdict")

    monkeypatch.setattr(verify, "_rerun_alone", rerun_alone)
    output = "[log] notes/verification/pytest-canned.log\nFAILED tests/t.py::test_a\n"
    assert _run_gate(monkeypatch, verify, [("pytest", 1, output)]) == 1
    out = capsys.readouterr().out
    assert "[load]" not in out
    assert "[FAIL] pytest: exit 1" in out


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
    assert len(failures) == int(returncode != 0)
    assert {name for name, _ in timings} == {"pytest", "shadow"}
    output = capsys.readouterr().out
    if returncode:
        assert "END" in output
        assert len(output) < 40000
        log = next(
            line.removeprefix("[log] ")
            for line in output.splitlines()
            if line.startswith("[log] ")
        )
        assert "START" + "x" * 1000000 + "END" in Path(log).read_text()
    else:
        assert "START" not in output


class TestGeneratorScope:
    def test_leaf_generator_keeps_shared_contracts_and_its_suites(self) -> None:
        verify = load_scope()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/languages/bfstack/generator.py"]
        )
        assert isinstance(scope, list)
        assert "src/esolangs/languages/bfstack/tests/test_boolean_bfstack.py" in scope
        assert "src/esolangs/languages/bfstack/tests/test_bfstack.py" in scope
        assert "tests/generators/test_boolean_contract.py" in scope
        assert "tests/proofs/test_execution_formulas.py" in scope
        assert "src/esolangs/languages/line/tests/test_boolean_line.py" not in scope
        assert (
            "src/esolangs/languages/malbolge/tests/test_boolean_malbolge.py"
            not in scope
        )

    @pytest.mark.parametrize("module", ["helpers.py", "line/render.py", "__init__.py"])
    def test_shared_or_package_generator_changes_keep_the_whole_suite(
        self, module
    ) -> None:
        verify = load_scope()
        assert (
            verify._pytest_scope(  # noqa: SLF001
                [f"src/esolangs/generation/{module}"]
            )
            == verify.WHOLE_SUITE
        )

    def test_explicitly_changed_language_tests_are_never_dropped(self) -> None:
        verify = load_scope()
        scope = verify._pytest_scope(  # noqa: SLF001
            [
                "src/esolangs/languages/bfstack/generator.py",
                "src/esolangs/languages/line/tests/test_boolean_line.py",
            ]
        )
        assert "src/esolangs/languages/line/tests/test_boolean_line.py" in scope


@pytest.mark.parametrize("package", [False, True])
def test_generator_scope_keeps_transitive_dependents(
    tmp_path, monkeypatch, *, package
) -> None:
    from types import SimpleNamespace

    from esolangs import registry

    verify = load_scope()
    verify.ROOT = tmp_path
    languages = {}
    for name in ("target", "consumer", "unrelated"):

        def build():
            return ""

        build.__module__ = f"esolangs.languages.{name}.generator"
        build.__name__ = name
        languages[name] = SimpleNamespace(id=name, name=name, aliases=(), boolean=build)
    monkeypatch.setattr(registry, "LANGUAGES", languages)
    consumer = (
        "src/esolangs/languages/consumer/generator/__init__.py"
        if package
        else "src/esolangs/languages/consumer/generator.py"
    )
    for path, text in {
        "src/esolangs/languages/target/generator.py": "",
        "src/esolangs/generation/dependency.py": (
            "from esolangs.languages.target.generator import build\n"
        ),
        consumer: "from esolangs.generation import dependency\n",
        "src/esolangs/languages/target/tests/test_boolean_target.py": "",
        "src/esolangs/languages/consumer/tests/test_boolean_consumer.py": "",
        "src/esolangs/languages/unrelated/tests/test_boolean_unrelated.py": "",
        "tests/generators/test_contracts.py": "",
    }.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    assert verify._pytest_scope(  # noqa: SLF001
        ["src/esolangs/languages/target/generator.py"]
    ) == [
        "src/esolangs/languages/consumer/tests/test_boolean_consumer.py",
        "src/esolangs/languages/target/tests/test_boolean_target.py",
        "tests/generators/test_contracts.py",
    ]


def test_exception_sweep_scope_includes_helpers_outside_interpreters() -> None:
    verify = load_scope()
    assert any(
        "src/esolangs/runtime/_traits.py".startswith(prefix)
        for prefix in verify.STEP_SCOPE["exception leaks"]
    )


def test_leak_step_covers_shipped_examples() -> None:
    from scripts.verify.scope import STEP_SCOPE

    assert "src/esolangs/languages/fixture/fixture.txt".startswith(
        STEP_SCOPE["exception leaks"]
    )


@pytest.mark.medium
def test_leak_sweep_starts_before_pytest_finishes(tmp_path) -> None:
    verify = load_script()
    ready = tmp_path / "leaks-started"
    script = (
        "from pathlib import Path; import time; "
        f"ready = Path({str(ready)!r}); deadline = time.monotonic() + 2\n"
        "while not ready.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
        "assert ready.exists(), 'leak sweep was serialized after pytest'"
    )
    runnable = [
        ("pytest", [sys.executable, "-c", script], {}),
        (
            "exception leaks",
            [
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(ready)!r}).touch()",
            ],
            {},
        ),
    ]
    failures, timings, _ = verify._run_steps(runnable, stream=False)  # noqa: SLF001
    assert len(failures) == 0
    assert {name for name, _ in timings} == {"pytest", "exception leaks"}


@pytest.mark.medium
def test_companion_checks_share_one_serial_lane(monkeypatch) -> None:
    from threading import Event

    verify = load_script()
    started, attempted, released, finished = (Event() for _ in range(4))

    def wait(_process, name, _start):
        if name == "pytest":
            assert started.wait(2)
            attempted.wait(0.2)
            released.set()
        elif name == "first":
            started.set()
            assert released.wait(2)
            finished.set()
        elif name == "second":
            attempted.set()
            assert finished.is_set(), "companion checks overlapped"
        return "", 0

    monkeypatch.setattr(verify, "_wait_with_heartbeat", wait)
    monkeypatch.setattr(
        verify.subprocess,
        "Popen",
        lambda *_args, **_kwargs: mock.Mock(stdout=io.TextIOWrapper(io.BytesIO())),
    )
    runnable = [(name, [name], {}) for name in ("pytest", "first", "second")]
    failures, timings, _ = verify._run_steps(runnable, stream=False)  # noqa: SLF001
    assert len(failures) == 0
    assert {name for name, _ in timings} == {"pytest", "first", "second"}


@pytest.mark.parametrize(
    ("stream", "shadow"), [(False, False), (True, False), (False, True)]
)
def test_deadline_kills_step_and_its_worker(
    tmp_path, monkeypatch, capsys, stream, shadow
) -> None:
    v = load_script()
    monkeypatch.setattr(v, "STEP_DEADLINES", {"pytest": 0.5})
    marker = tmp_path / "worker"
    worker = f"""
import time
from pathlib import Path
path = Path({str(marker)!r})
while True:
    path.write_text(str(time.monotonic()))
    time.sleep(0.01)
"""
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {worker!r}]); "
        "print('worker started', flush=True); time.sleep(30)"
    )
    steps = [("pytest", [sys.executable, "-c", parent], dict(os.environ))]
    if shadow:
        steps.append(("shadow", [sys.executable, "-c", "pass"], dict(os.environ)))
    start = time.monotonic()
    failures, _, _ = v._run_steps(steps, stream=stream)  # noqa: SLF001
    assert len(failures) == 1
    assert time.monotonic() - start < 3
    value = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == value
    assert "deadline exceeded (0.5s)" in capsys.readouterr().out


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.skipif(os.name != "posix", reason="worker inherits a POSIX session")
def test_deadline_includes_output_from_an_exited_leaders_worker(
    tmp_path, monkeypatch, capsys, stream
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    monkeypatch.setattr(verify, "STEP_DEADLINES", {"pytest": 0.2})
    marker = tmp_path / "worker"
    worker = f"""
import time
from pathlib import Path
marker = Path({str(marker)!r})
deadline = time.monotonic() + 1
while time.monotonic() < deadline:
    marker.write_text(str(time.monotonic()))
    time.sleep(0.01)
print('late worker output', flush=True)
"""
    parent = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {worker!r}]); "
        "print('leader exited', flush=True)"
    )
    start = time.monotonic()
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("pytest", [sys.executable, "-c", parent], dict(os.environ))], stream=stream
    )
    assert len(failures) == 1
    assert time.monotonic() - start < 0.9
    output = capsys.readouterr().out
    assert "leader exited" in output
    assert "deadline exceeded (0.2s)" in output
    assert "late worker output" not in output
    value = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == value


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.skipif(os.name != "posix", reason="worker inherits a POSIX session")
def test_exited_leaders_worker_can_finish_within_the_deadline(
    tmp_path, monkeypatch, capsys, stream
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    monkeypatch.setattr(verify, "STEP_DEADLINES", {"pytest": 1})
    worker = "import time; time.sleep(0.1); print('worker finished', flush=True)"
    parent = (
        f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {worker!r}])"
    )
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("pytest", [sys.executable, "-c", parent], dict(os.environ))], stream=stream
    )
    assert len(failures) == 0
    logs = list((tmp_path / "notes/verification").glob("*.log"))
    assert logs[0].read_text() == "worker finished\n"
    assert "deadline exceeded" not in capsys.readouterr().out


@pytest.mark.parametrize("parent_exit", [0.0, 0.9])
@pytest.mark.parametrize("reader_exit", [2.2, None])
def test_logged_parent_and_reader_share_heartbeat_intervals(
    tmp_path, monkeypatch, parent_exit, reader_exit
) -> None:
    verify = load_script()
    process = sys.modules[verify.start_logged.__module__]
    now = [0.0]
    heartbeats = []
    stopped = []

    class Parent:
        args = ("probe",)
        returncode = 0

        def wait(self, timeout):
            elapsed = max(0.0, parent_exit - now[0])
            now[0] += min(elapsed, timeout)
            if elapsed > timeout:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return self.returncode

    class Reader:
        done = False

        def join(self, timeout):
            if not self.done:
                until = now[0] + timeout
                now[0] = min(until, reader_exit) if reader_exit is not None else until
                self.done = reader_exit is not None and now[0] >= reader_exit

        def is_alive(self):
            return not self.done

    parent, reader = Parent(), Reader()
    path = tmp_path / "log"
    path.write_text("worker output\n")
    monkeypatch.setattr(process, "_LOGS", {parent: process.Log(path, reader=reader)})
    monkeypatch.setattr(process.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        process, "print", lambda *_: heartbeats.append(now[0]), raising=False
    )

    def stop(_proc):
        stopped.append(now[0])
        reader.done = True

    monkeypatch.setattr(process, "stop_process_tree", stop)
    output, code = process.wait_with_heartbeat(parent, "probe", 0.0, 2.5, 1.0)
    assert heartbeats == pytest.approx([1.0, 2.0])
    assert "worker output" in output
    if reader_exit is None:
        assert code == 124
        assert stopped == [2.5]
        assert "deadline exceeded" in output
    else:
        assert code == 0
        assert now[0] == reader_exit
        assert not stopped


@pytest.mark.skipif(os.name != "posix", reason="closes POSIX stdout descriptors")
def test_closed_stdout_does_not_skip_heartbeats_or_the_leaders_deadline(
    tmp_path, monkeypatch, capsys
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    monkeypatch.setattr(verify, "STEP_DEADLINES", {"pytest": 0.2})
    monkeypatch.setattr(verify, "HEARTBEAT_SECONDS", 0.05)
    parent = "import os, time; os.close(1); os.close(2); time.sleep(1)"
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("pytest", [sys.executable, "-c", parent], dict(os.environ))], stream=False
    )
    assert len(failures) == 1
    output = capsys.readouterr().out
    assert output.count("still running") >= 2
    assert "deadline exceeded (0.2s)" in output


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX")
def test_a_zombie_group_counts_as_stopped_but_a_live_one_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Darwin's killpg says EPERM once the leader exits; that raced 1 run in 15."""
    verify = load_script()
    process = sys.modules[verify.start_logged.__module__]

    def refuse(_pid: int, _signal: int) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(process.os, "killpg", refuse)
    exited = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    exited.wait()
    process.stop_process_tree(exited)
    live = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        with pytest.raises(PermissionError):
            process.stop_process_tree(live)
    finally:
        live.kill()
        live.wait()


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("running", [False, True])
def test_log_writer_errors_fail_the_check_and_stop_running_steps(
    tmp_path, monkeypatch, capsys, stream, running
) -> None:
    verify = load_script()
    process = sys.modules[verify.start_logged.__module__]
    verify.ROOT = tmp_path
    monkeypatch.setattr(verify, "STEP_DEADLINES", {"probe": 5})
    uncaught = []
    injected = []
    monkeypatch.setattr(threading, "excepthook", uncaught.append)

    def fail_spool(reader, path, *_args):
        reader.read1(8192)
        path.write_bytes(b"partial log\n")
        injected.append(True)
        raise OSError(errno.ENOSPC, "injected disk full")

    monkeypatch.setattr(process, "spool", fail_spool)
    script = "import time; print('first output', flush=True)"
    if running:
        script += "; time.sleep(10)"
    start = time.monotonic()
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("probe", [sys.executable, "-c", script], dict(os.environ))], stream=stream
    )
    assert injected == [True]
    assert len(failures) == 1
    # Margins sized for a loaded machine: a subprocess start overran 0.9 s.
    assert time.monotonic() - start < 5
    output = capsys.readouterr().out
    assert "partial log" in output
    assert "injected disk full" in output
    assert "log error" in output
    assert "deadline exceeded" not in output
    assert not uncaught


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("timeout", [False, True])
def test_unreadable_log_fails_with_a_diagnostic(
    tmp_path, monkeypatch, capsys, stream, timeout
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    original_open = Path.open

    def open_log(path, mode="r", *args, **kwargs):
        if mode == "rb" and path.parent == tmp_path / "notes" / "verification":
            raise PermissionError("injected unreadable log")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_log)
    monkeypatch.setattr(verify, "STEP_DEADLINES", {"probe": 0.2})
    script = "import time; print('output', flush=True)"
    if timeout:
        script += "; time.sleep(2)"
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("probe", [sys.executable, "-c", script], dict(os.environ))],
        stream=stream,
    )
    assert len(failures) == 1
    output = capsys.readouterr().out
    assert "log error" in output
    assert "injected unreadable log" in output
    assert ("deadline exceeded" in output) is timeout


def test_broken_streamed_stdout_does_not_fail_complete_logs(
    tmp_path, monkeypatch
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    output = sys.stdout
    injected = []

    class Stream:
        def write(self, text):
            # Unbuffered children write the newline separately.
            if "tee output" in text and not injected:
                injected.append(True)
                raise BrokenPipeError("injected closed stdout")
            return output.write(text)

        def flush(self):
            output.flush()

    monkeypatch.setattr(sys, "stdout", Stream())
    failures, _, _ = verify._run_steps(  # noqa: SLF001
        [("probe", [sys.executable, "-c", "print('tee output')"], dict(os.environ))],
        stream=True,
    )
    assert injected == [True]
    assert len(failures) == 0
    logs = list((tmp_path / "notes/verification").glob("*.log"))
    assert logs[0].read_text() == "tee output\n"


@pytest.mark.parametrize("stream", [False, True])
def test_step_logs_persist_for_streamed_and_captured_output(
    tmp_path, capsys, stream
) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    steps = [("probe", [sys.executable, "-c", "print('log marker')"], dict(os.environ))]
    assert verify._run_steps(steps, stream=stream)[0] == []  # noqa: SLF001
    logs = list((tmp_path / "notes/verification").glob("*.log"))
    assert len(logs) == 1
    assert logs[0].read_text() == "log marker\n"
    assert ("log marker" in capsys.readouterr().out) is stream


@pytest.mark.medium
def test_streamed_logs_deliver_short_flushes_before_exit(tmp_path, monkeypatch) -> None:
    verify = load_script()
    verify.ROOT = tmp_path
    marker = tmp_path / "received"
    output = sys.stdout

    class Stream:
        def write(self, text):
            if "live marker" in text:
                marker.touch()
            return output.write(text)

        def flush(self):
            output.flush()

    monkeypatch.setattr(sys, "stdout", Stream())
    script = f"""
import time
from pathlib import Path
print('live marker', flush=True)
deadline = time.monotonic() + 1
while not Path({str(marker)!r}).exists() and time.monotonic() < deadline:
    time.sleep(0.01)
assert Path({str(marker)!r}).exists(), 'stream withheld a flushed short line'
"""
    assert (
        verify._run_steps(  # noqa: SLF001
            [("probe", [sys.executable, "-c", script], dict(os.environ))], stream=True
        )[0]
        == []
    )


@pytest.fixture
def colocated_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from types import SimpleNamespace

    from esolangs import registry

    verify = load_scope()
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    languages = {}
    for slug in ("target", "unrelated"):

        def generate(table: str) -> str:
            return table

        generate.__module__ = f"esolangs.languages.{slug}.generator"
        languages[slug] = SimpleNamespace(
            id=slug, name=slug, aliases=(), boolean=generate
        )
        for relative in (
            f"src/esolangs/languages/{slug}/generator.py",
            f"src/esolangs/languages/{slug}/tests/test_{slug}.py",
            f"src/esolangs/languages/{slug}/tests/test_boolean_{slug}.py",
        ):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
    monkeypatch.setattr(registry, "LANGUAGES", languages)
    (tmp_path / "tests/generators").mkdir(parents=True)
    (tmp_path / "tests/generators/test_contracts.py").write_text("")
    return verify


@pytest.mark.parametrize(
    "implementation",
    ["interpreter.py", "interpreter/__init__.py", "interpreter/index.py"],
)
def test_colocated_interpreter_scope_keeps_language_and_shared_tests(
    colocated_scope: Any, implementation: str
) -> None:
    verify = colocated_scope
    scope = verify._pytest_scope(  # noqa: SLF001
        [f"src/esolangs/languages/target/{implementation}"]
    )
    assert isinstance(scope, list)
    assert "src/esolangs/languages/target/tests/test_target.py" in scope
    assert "src/esolangs/languages/target/tests/test_boolean_target.py" in scope
    assert set(verify.INTERPRETER_CONTRACT_TESTS) <= set(scope)


@pytest.mark.parametrize("slug", ["target", "unrelated"])
def test_colocated_generator_scope_keeps_its_tests(
    colocated_scope: Any, slug: str
) -> None:
    verify = colocated_scope
    scope = verify._pytest_scope(  # noqa: SLF001
        [f"src/esolangs/languages/{slug}/generator.py"]
    )
    assert isinstance(scope, list)
    assert f"src/esolangs/languages/{slug}/tests/test_boolean_{slug}.py" in scope
    other = "unrelated" if slug == "target" else "target"
    assert f"src/esolangs/languages/{other}/tests/test_boolean_{other}.py" not in scope


def test_colocated_test_changes_run_directly_and_helpers_widen(
    colocated_scope: Any,
) -> None:
    verify = colocated_scope
    test = "src/esolangs/languages/target/tests/test_target.py"
    assert verify._pytest_scope([test]) == [test]  # noqa: SLF001
    assert (
        verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/languages/target/tests/__init__.py"]
        )
        == verify.WHOLE_SUITE
    )
    assert verify._pytest_scope(["conftest.py"]) == verify.WHOLE_SUITE  # noqa: SLF001


def test_a_failed_pre_commit_skips_pytest_but_not_the_cheap_steps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Six sessions waited ~150 s of pytest for a one-line ruff fix."""
    verify = load_script()

    def wait(_process, name, _start):
        return "", int(name == "pre-commit")

    monkeypatch.setattr(verify, "_wait_with_heartbeat", wait)
    monkeypatch.setattr(
        verify.subprocess,
        "Popen",
        lambda *_args, **_kwargs: mock.Mock(stdout=io.TextIOWrapper(io.BytesIO())),
    )
    runnable = [(name, [name], {}) for name in ("pre-commit", "pytest", "mypy")]
    failures, timings, _ = verify._run_steps(runnable, stream=False)  # noqa: SLF001
    assert [name for name, *_ in failures] == ["pre-commit"]
    assert {name for name, _ in timings} == {"pre-commit", "mypy"}
    assert "[skip] pytest: pre-commit failed" in capsys.readouterr().out


def test_a_failed_hook_names_its_cause_in_the_summary() -> None:
    verify = load_script()
    output = (
        "[log] notes/verification/pre-commit-x.log\n"
        "check yaml.......Passed\n"
        "ruff (legacy alias).......Failed\n"
        "- hook id: ruff\n- exit code: 1\n\n"
        "E501 Line too long (95 > 88)\n   --> gate.py:240:89\n"
        "check-yaml.......Failed\n"
        "- hook id: check-yaml\n"
        "check-toml.......Passed\n"
    )
    assert verify._located(output) == [  # noqa: SLF001
        "  [log] notes/verification/pre-commit-x.log",
        "  ruff (legacy alias): E501 Line too long (95 > 88)",
        "  check-yaml",
    ]


def test_a_stale_artifact_failure_prints_the_whole_regeneration() -> None:
    verify = load_script()
    stale = "FAILED tests/tooling/test_examples.py::test_x[kiss] - stale\n"
    hint = "\n".join(verify._rerun_hint("pytest", stale))  # noqa: SLF001
    assert hint.index("generate.py docs") < hint.index("generate.py examples")
    assert "check_generator_sizes.py --update" in hint
    other = "FAILED tests/t.py::test_y - boom\n"
    assert "fix:" not in "\n".join(verify._rerun_hint("pytest", other))  # noqa: SLF001
