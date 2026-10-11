"""The scoping rule narrows a check without ever narrowing what it proves."""

import subprocess
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from tests.scripts.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "_lib" / "scope.py"


def load_script() -> Any:
    return load(SCRIPT)


# 2.9s over 6 tests: shells out to git.
@pytest.mark.medium
class TestChangedFiles:
    """The list handed to a checker has to be one a checker can accept."""

    def test_paths_are_not_repeated(self) -> None:
        """A file both committed and dirty appears once, not twice."""
        scope = load_script()
        names = scope.changed_files()  # type: ignore[attr-defined]
        assert len(names) == len(set(names))

    def test_returns_repo_relative_paths(self) -> None:
        """Paths are repo-relative, which is what the prefix matching assumes."""
        scope = load_script()
        for name in scope.changed_files():  # type: ignore[attr-defined]
            assert not name.startswith("/")


class TestWidensToEverything:
    """Scoping may only ever subtract work that provably could not break."""

    def test_unreadable_diff_widens(self) -> None:
        """No diff means no evidence, so everything runs."""
        scope = load_script()
        assert scope.widens_to_everything([]) is not None  # type: ignore[attr-defined]

    def test_shared_interpreter_machinery_widens(self) -> None:
        """The shared IO layer can move every interpreter at once."""
        scope = load_script()
        changed = ["src/esolangs/interpreters/io.py"]
        assert scope.widens_to_everything(changed) is not None  # type: ignore[attr-defined]

    def test_every_registry_module_widens(self) -> None:
        """The registry package is shared machinery under any filename."""
        scope = load_script()
        names = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in sorted((REPO_ROOT / "src/esolangs/registry").rglob("*.py"))
        ]
        assert names, "registry package has no modules"
        for name in names:
            assert scope.widens_to_everything([name]) is not None  # type: ignore[attr-defined]

    def test_verification_tooling_widens(self) -> None:
        """A scoped run cannot be trusted to validate the scoping code itself."""
        scope = load_script()
        for name in ("scripts/verify.py", "scripts/_lib/scope.py"):
            assert scope.widens_to_everything([name]) is not None  # type: ignore[attr-defined]

    def test_ordinary_interpreter_does_not_widen(self) -> None:
        """A single interpreter is the case scoping exists to narrow."""
        scope = load_script()
        changed = ["src/esolangs/interpreters/tape_based/brainfuck.py"]
        assert scope.widens_to_everything(changed) is None  # type: ignore[attr-defined]


def test_empty_branch_diff_does_not_fall_back_to_previous_commit() -> None:
    scope = load_script()
    responses = [
        subprocess.CompletedProcess([], 0, stdout=b"", stderr=""),
        subprocess.CompletedProcess(
            [], 0, stdout=b" M src/esolangs/tools/vandevelo.py\0", stderr=""
        ),
    ]
    with mock.patch.object(scope.subprocess, "run", side_effect=responses) as run:
        assert scope.changed_files() == ["src/esolangs/tools/vandevelo.py"]
    assert run.call_count == 2
    assert run.call_args_list[0].args[0][-1] == "main...HEAD"


def test_missing_branch_refs_still_fall_back_to_previous_commit() -> None:
    scope = load_script()
    responses = [
        subprocess.CompletedProcess([], 128, stdout=b"", stderr="missing local ref"),
        subprocess.CompletedProcess([], 128, stdout=b"", stderr="missing remote ref"),
        subprocess.CompletedProcess([], 0, stdout=b"src/esolangs/vm.py\0", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=b"", stderr=""),
    ]
    with mock.patch.object(scope.subprocess, "run", side_effect=responses):
        assert scope.changed_files() == ["src/esolangs/vm.py"]


def test_missing_local_main_uses_remote_main() -> None:
    scope = load_script()
    responses = [
        subprocess.CompletedProcess([], 128, stdout=b"", stderr="missing local ref"),
        subprocess.CompletedProcess([], 0, stdout=b"src/esolangs/vm.py\0", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=b"", stderr=""),
    ]
    with mock.patch.object(scope.subprocess, "run", side_effect=responses) as run:
        assert scope.changed_files() == ["src/esolangs/vm.py"]
    assert run.call_args_list[1].args[0][-1] == "origin/main...HEAD"


@pytest.mark.parametrize("bad", [False, True])
def test_nul_paths_and_rename_sources_are_preserved(bad):
    scope = load_script()
    names = [
        "space name.py",
        'quote"name.py',
        "newline\nname.py",
        "carriage\r\nname.py",
        "deleted.py",
    ]
    diff = subprocess.CompletedProcess([], 0, stdout=("\0".join(names) + "\0").encode())
    status = subprocess.CompletedProcess(
        [], 0, stdout=b"R  new name.py\0old name.py\0?? sub/fresh\nfile.py\0"
    )
    if bad:
        status.stdout = b"R  new name.py\0"
    with mock.patch.object(scope.subprocess, "run", side_effect=[diff, status]) as run:
        expected = (
            [] if bad else [*names, "new name.py", "old name.py", "sub/fresh\nfile.py"]
        )
        assert scope.changed_files() == expected
    assert "-z" in run.call_args_list[0].args[0]
    assert "--untracked-files=all" in run.call_args_list[1].args[0]
