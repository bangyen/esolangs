"""Unit tests for the shared interpreter ``__main__`` body.

Every interpreter's entry point is two lines delegating to
:func:`script_main`, and coverage's ``exclude_lines`` drops those two lines
-- so this file is the only thing that measures what a bare
``python esolangs_<lang>.py program.txt`` does.  The three source shapes are
not interchangeable, which is what most of these assert.
"""

from pathlib import Path
from typing import Any

import pytest

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

PROGRAM = "one\ntwo\n"


def _spy() -> tuple[list[Any], Any]:
    """Return a list and a ``run`` that records what it was handed."""
    seen: list[Any] = []

    def run(source: Any, _io: IO) -> None:
        seen.append(source)

    return seen, run


def _written(tmp_path: Path) -> Path:
    path = tmp_path / "program.txt"
    path.write_text(PROGRAM, encoding="utf-8")
    return path


class TestSourceShape:
    """Each shape hands ``run`` the form that language's parser expects."""

    def test_text_is_the_whole_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        script_main(run)
        assert seen == [PROGRAM]

    def test_keep_retains_the_newlines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        script_main(run, shape="keep")
        assert seen == [["one\n", "two\n"]]

    def test_strip_drops_the_newlines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        script_main(run, shape="strip")
        assert seen == [["one", "two"]]

    def test_keep_matches_readlines(self, tmp_path: Path) -> None:
        """The form the copies produced with ``file.readlines()``."""
        path = _written(tmp_path)
        with open(path, encoding="utf-8") as file:
            assert file.readlines() == path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )


class TestArgumentHandling:
    """A missing path is a no-op; a returned code becomes the exit status."""

    def test_no_argument_runs_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog"])
        script_main(run)
        assert seen == []

    def test_a_returned_code_exits_with_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def run(_source: Any, _io: IO) -> int:
            return 3

        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        with pytest.raises(SystemExit) as caught:
            script_main(run)
        assert caught.value.code == 3

    def test_none_exits_normally(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        script_main(run)

    def test_the_file_is_read_as_utf8(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Not the locale encoding, so a program means the same everywhere."""
        seen, run = _spy()
        path = tmp_path / "program.txt"
        path.write_bytes("◘\n".encode())
        monkeypatch.setattr("sys.argv", ["prog", str(path)])
        script_main(run)
        assert seen == ["◘\n"]
