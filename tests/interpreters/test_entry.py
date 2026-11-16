"""Unit tests for the shared interpreter ``__main__`` body."""

import gzip
import io
import os
import subprocess
import sys
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
from tests.support.reference import REFERENCE

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
        seen, run = _spy()
        monkeypatch.setattr("sys.argv", ["prog", str(_written(tmp_path))])
        script_main(run)
        closed = io.StringIO()
        closed.close()
        monkeypatch.setattr(sys, "stdin", closed)
        script_main(run)
        assert seen == [PROGRAM, PROGRAM]
        _check_redirected_stdin(monkeypatch)
        _check_reference_script(tmp_path)

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


def _check_redirected_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    # This wrapper already owns decoded, prefetched input when the script starts.
    payload = io.BytesIO(b"X  42\r\nline\r\nlast\r")
    with io.TextIOWrapper(payload, encoding="utf-8", newline="\n") as stream:
        assert stream.read(1) == "X"
        monkeypatch.setattr(sys, "stdin", stream)

        def consume(_source, port: IO) -> None:
            assert port.input_token() == "42"
            assert port.input_char() == ord("\r")
            assert port.input_char() == ord("\n")
            assert port.input_str() == "line"
            assert port.input_all() == "last\r"
            with pytest.raises(EOFError):
                port.input_char()

        script_main(consume)
        assert not stream.closed

    monkeypatch.setattr(sys, "stdin", None)

    def no_stdin(_source, port: IO) -> None:
        assert port.input_all() == ""
        with pytest.raises(EOFError):
            port.input_str()

    script_main(no_stdin)


def _check_reference_script(tmp_path: Path) -> None:
    path = tmp_path / "echo"
    path.write_text(",.,.", encoding="utf-8")
    command = [sys.executable, "-m", f"esolangs.languages.{REFERENCE}.interpreter"]
    for data in (b"A", b"AB", b"A\r\n"):
        run = subprocess.run(
            [*command, str(path)],
            input=data,
            capture_output=True,
            timeout=5,
            check=False,
        )
        assert run.stdout == b"Input: " + data[:2]
        assert (run.returncode != 0) == (len(data) == 1)
    path.write_text(",.", encoding="utf-8")
    with subprocess.Popen(
        [*command, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as child:
        assert child.stdin is not None
        assert child.stdout is not None
        try:
            child.stdin.write(b"Z")
            child.stdin.flush()
            assert child.wait(timeout=5) == 0
            assert child.stdout.read() == b"Input: Z"
        finally:
            if child.poll() is None:
                child.kill()


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
