"""The scoping rule narrows a check without ever narrowing what it proves.

``scripts/_scope.py`` decides which files a branch touched, and every local
check consults it to skip work that branch could not have broken.  That makes
two properties worth pinning: the file list it hands a checker must be usable
(no repeats -- mypy rejects a repeated path as a duplicate module), and every
"widen back to everything" escape hatch must actually fire, since a missed one
silently turns a correctness gate off.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "_scope.py"


def load_script() -> object:
    """Import the scoping helper as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("_scope", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestChangedFiles:
    """The list handed to a checker has to be one a checker can accept."""

    def test_paths_are_not_repeated(self) -> None:
        """A file both committed and dirty appears once, not twice.

        ``changed_files`` unions the branch diff with ``git status``, so a file
        that is committed *and* has uncommitted edits comes back from both.
        Passing the repeat through to mypy fails the run outright ("Duplicate
        module named ..."), which would turn a scoped pre-commit into a hard
        error rather than a faster check.
        """
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

    def test_verification_tooling_widens(self) -> None:
        """A scoped run cannot be trusted to validate the scoping code itself."""
        scope = load_script()
        for name in ("scripts/verify.py", "scripts/_scope.py"):
            assert scope.widens_to_everything([name]) is not None  # type: ignore[attr-defined]

    def test_ordinary_interpreter_does_not_widen(self) -> None:
        """A single interpreter is the case scoping exists to narrow."""
        scope = load_script()
        changed = ["src/esolangs/interpreters/tape_based/brainfuck.py"]
        assert scope.widens_to_everything(changed) is None  # type: ignore[attr-defined]
