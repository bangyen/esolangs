"""The local gate may skip work, but only work CI is known to redo."""

import io
import os
import re
import subprocess
import sys
import time
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
    @pytest.mark.parametrize(
        ("path", "scoped"),
        [
            ("tests/tools/polynomial_support.py", False),
            ("tests/test_vm.py", True),
            ("src/esolangs/interpreters/other/demo/brainfuck.py", False),
            ("src/esolangs/interpreters/io.py", False),
        ],
    )
    def test_only_collected_leaf_modules_are_scoped(self, path, scoped):
        verify = load_script()
        scope = verify._pytest_scope([path])  # noqa: SLF001
        assert scope == ([path] if scoped else verify.WHOLE_SUITE)

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

    def test_the_patterns_match_pyproject(self) -> None:
        verify = load_script()
        config = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        patterns = config["tool"]["pytest"]["ini_options"]["python_files"]
        assert list(verify.COLLECTED_PATTERNS) == patterns


LEAF = "src/esolangs/interpreters/register_based/addsubjump.py"
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
        workflow = CI.read_text(encoding="utf-8")
        missing = [
            name for name, cmd in verify.STEPS if _signature(cmd) not in workflow
        ]
        assert not missing, f"steps CI does not run: {missing}"

    def test_a_step_ci_does_not_run_is_reported(self) -> None:
        workflow = CI.read_text(encoding="utf-8")
        bogus = _signature(["uv", "run", "python", "scripts/no_such_check.py"])
        assert bogus not in workflow


@pytest.mark.parametrize(("path", "size"), [("", 0), ("README.md", 6), ("src/x.py", 1)])
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
        only, skip, *_ = self._parse(["--only", "pre-commit,pytest"])  # type: ignore[misc]
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
        verify,
        "run_bounded",
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
        verify = load_script()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/tools/bfstack.py"]
        )
        assert isinstance(scope, list)
        assert "tests/tools/test_boolean_bfstack.py" in scope
        assert "tests/interpreters/test_bfstack.py" in scope
        assert "tests/tools/test_boolean_contract.py" in scope
        assert "tests/proofs/test_execution_formulas.py" in scope
        assert "tests/tools/test_boolean_line.py" not in scope
        assert "tests/tools/test_boolean_malbolge.py" not in scope

    @pytest.mark.parametrize("module", ["helpers.py", "line/render.py", "__init__.py"])
    def test_shared_or_package_generator_changes_keep_the_whole_suite(
        self, module
    ) -> None:
        verify = load_script()
        assert (
            verify._pytest_scope(  # noqa: SLF001
                [f"src/esolangs/tools/{module}"]
            )
            == verify.WHOLE_SUITE
        )

    def test_explicitly_changed_language_tests_are_never_dropped(self) -> None:
        verify = load_script()
        scope = verify._pytest_scope(  # noqa: SLF001
            ["src/esolangs/tools/bfstack.py", "tests/tools/test_boolean_line.py"]
        )
        assert "tests/tools/test_boolean_line.py" in scope


def test_generator_scope_keeps_transitive_dependents(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from esolangs import registry

    verify = load_script()
    verify.ROOT = tmp_path
    languages = {}
    for name in ("target", "consumer", "unrelated"):

        def build():
            return ""

        build.__module__ = "esolangs.tools." + (
            "package.consumer" if name == "consumer" else name
        )
        build.__name__ = name
        languages[name] = SimpleNamespace(id=name, name=name, aliases=(), boolean=build)
    monkeypatch.setattr(registry, "LANGUAGES", languages)
    for path, text in {
        "src/esolangs/tools/target.py": "",
        "src/esolangs/tools/package/dependency.py": (
            "from esolangs.tools.target import build\n"
        ),
        "src/esolangs/tools/package/consumer.py": ("from . import dependency\n"),
        "tests/tools/test_boolean_target.py": "",
        "tests/tools/test_boolean_consumer.py": "",
        "tests/tools/test_boolean_unrelated.py": "",
        "tests/tools/test_contracts.py": "",
    }.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    assert verify._pytest_scope(["src/esolangs/tools/target.py"]) == [  # noqa: SLF001
        "tests/tools/test_boolean_consumer.py",
        "tests/tools/test_boolean_target.py",
        "tests/tools/test_contracts.py",
    ]


def test_exception_sweep_scope_includes_helpers_outside_interpreters() -> None:
    verify = load_script()
    assert any(
        "src/esolangs/_traits.py".startswith(prefix)
        for prefix in verify.STEP_SCOPE["exception leaks"]
    )


def test_leak_step_covers_shipped_examples():
    from scripts.verify import STEP_SCOPE

    assert "src/esolangs/examples/fixture.txt".startswith(STEP_SCOPE["exception leaks"])


@pytest.mark.medium
def test_leak_sweep_starts_before_pytest_finishes(tmp_path):
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
    assert failures == 0
    assert {name for name, _ in timings} == {"pytest", "exception leaks"}


@pytest.mark.medium
def test_companion_checks_share_one_serial_lane(monkeypatch):
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
    assert failures == 0
    assert {name for name, _ in timings} == {"pytest", "first", "second"}


@pytest.mark.parametrize(
    ("stream", "shadow"), [(False, False), (True, False), (False, True)]
)
def test_deadline_kills_step_and_its_worker(
    tmp_path, monkeypatch, capsys, stream, shadow
):
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
    assert failures == 1
    assert time.monotonic() - start < 3
    value = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == value
    assert "deadline exceeded (0.5s)" in capsys.readouterr().out


@pytest.mark.parametrize("stream", [False, True])
def test_step_logs_persist_for_streamed_and_captured_output(tmp_path, capsys, stream):
    verify = load_script()
    verify.ROOT = tmp_path
    steps = [("probe", [sys.executable, "-c", "print('log marker')"], dict(os.environ))]
    assert verify._run_steps(steps, stream=stream)[0] == 0  # noqa: SLF001
    logs = list((tmp_path / "notes/verification").glob("*.log"))
    assert len(logs) == 1
    assert logs[0].read_text() == "log marker\n"
    assert ("log marker" in capsys.readouterr().out) is stream


@pytest.mark.medium
def test_streamed_logs_deliver_short_flushes_before_exit(tmp_path, monkeypatch):
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
        == 0
    )
