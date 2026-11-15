"""Unit tests for the shared interpreter ``__main__`` body."""

import gzip
import os
from pathlib import Path
from typing import Any

import pytest

from esolangs import ArgumentError, ProgramError
from esolangs.runtime._entry import script_main
from esolangs.runtime._source import (
    compressed_text_source,
    native_text_source,
    text_source,
)
from esolangs.runtime.io import IO

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


@pytest.mark.parametrize(
    ("shape", "expected"),
    [("text", PROGRAM), ("keep", ["one\n", "two\n"]), ("strip", ["one", "two"])],
)
def test_source_shape(tmp_path, monkeypatch, shape, expected):
    seen, run = _spy()
    path = tmp_path / "source"
    monkeypatch.setattr("sys.argv", ["prog", str(path)])
    for newline in ("\n", "\r\n", "\r"):
        for compressed in (False, True):
            source = PROGRAM.replace("\n", newline).encode()
            path.write_bytes(gzip.compress(source, mtime=0) if compressed else source)
            seen.clear()
            script_main(run, shape=shape)
            assert seen == [expected]
    for invalid, reason in (
        (b"\x1f\x8b", "truncated gzip"),
        (gzip.compress(b"\xff"), "invalid UTF-8"),
        (b"\x89PNG\r\n\x1a\n", "the program is a PNG"),
    ):
        path.write_bytes(invalid)
        seen.clear()
        with pytest.raises(ProgramError, match=reason) as failure:
            script_main(run, shape=shape)
        assert str(path) in str(failure.value)
        assert not seen


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


def test_loader_receives_the_path_and_owns_source_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen, run = _spy()
    path = tmp_path / "program.bin"
    source = object()

    def loader(actual: Path) -> object:
        assert actual == path
        assert isinstance(actual, Path)
        return source

    monkeypatch.setattr("sys.argv", ["prog", str(path)])
    script_main(run, loader=loader)
    assert seen == [source]

    path.write_bytes(gzip.compress(b"one\r\n", mtime=0))
    for reader in (None, text_source, native_text_source, compressed_text_source):
        monkeypatch.setattr("sys.argv", ["prog", str(path)])
        script_main(run, loader=reader)
        wanted = {None: "one\n", native_text_source: "one"}.get(reader, "one\r\n")
        assert str(seen.pop()) == wanted
        if os.name == "posix":
            for suffix in ("/", "/."):
                rejected = f"{path}{suffix}"
                monkeypatch.setattr("sys.argv", ["prog", rejected])
                with pytest.raises(ProgramError, match="Not a directory") as failed:
                    script_main(run, loader=reader)
                assert rejected in str(failed.value)
        monkeypatch.setattr("sys.argv", ["prog", ""])
        with pytest.raises(ArgumentError, match="path must not be empty"):
            script_main(run, loader=reader)
    assert seen == [source]
