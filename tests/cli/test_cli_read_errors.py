"""Malformed documents and stdin fail before interpreter execution."""

from __future__ import annotations

import io
import sys
import threading

import pytest

from esolangs.cli import main
from esolangs.cli.io import (
    _bounded_read,
    _read_stdin,
    _write_output,
)


@pytest.mark.parametrize("raw", [b"\xff", b"\x80"])
def test_stdin_rejects_surrogateescaped_binary(monkeypatch, capsys, raw) -> None:
    text = raw.decode("utf-8", "surrogateescape")
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    with pytest.raises(SystemExit) as caught:
        _read_stdin()
    assert caught.value.code == 2
    assert "cannot read stdin: not text" in capsys.readouterr().err


def test_stdin_preserves_surrogates_that_are_not_escaped_bytes(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("\ud800"))
    assert _read_stdin() == "\ud800"


def test_reader_threads_propagate_unexpected_errors(monkeypatch) -> None:
    class BrokenInput(io.StringIO):
        def read(self, *_args, **_kwargs):
            raise RuntimeError("reader failed")

    monkeypatch.setattr(sys, "stdin", BrokenInput())
    with pytest.raises(RuntimeError, match="reader failed"):
        _read_stdin()

    def broken_read(*_args, **_kwargs):
        raise RuntimeError("file reader failed")

    monkeypatch.setattr("esolangs.cli.io.open", broken_read, raising=False)
    with pytest.raises(RuntimeError, match="file reader failed"):
        _bounded_read("program.txt", None)


def test_terminal_stdin_returns_without_reading(monkeypatch) -> None:
    stream = io.StringIO("unused")
    monkeypatch.setattr(stream, "isatty", lambda: True)
    monkeypatch.setattr(sys, "stdin", stream)
    assert _read_stdin() == ""
    assert stream.tell() == 0


def test_stdin_reports_strict_decode_errors(monkeypatch, capsys) -> None:
    class BinaryInput(io.StringIO):
        def read(self, *_args, **_kwargs):
            return b"\xff".decode("utf-8")

    monkeypatch.setattr(sys, "stdin", BinaryInput())
    with pytest.raises(SystemExit) as caught:
        _read_stdin()
    assert caught.value.code == 2
    assert "cannot read stdin: not text" in capsys.readouterr().err


@pytest.mark.parametrize("reader", ["stdin", "file"])
def test_blocked_readers_obey_their_deadline(monkeypatch, capsys, reader) -> None:
    released = threading.Event()

    class BlockedInput(io.StringIO):
        def read(self, *_args, **_kwargs):
            released.wait()
            return ""

    stream = BlockedInput()
    monkeypatch.setattr(sys, "stdin", stream)
    monkeypatch.setattr("esolangs.cli.io.open", lambda *_a: stream, raising=False)
    try:
        call = (
            (lambda: _read_stdin(0.01))
            if reader == "stdin"
            else (lambda: _bounded_read("blocked", 0.01))
        )
        with pytest.raises(SystemExit) as caught:
            call()
        assert caught.value.code == 124
        assert ("stdin" if reader == "stdin" else "blocked") in capsys.readouterr().err
    finally:
        released.set()


def test_output_escapes_unencodable_text_without_a_binary_buffer(monkeypatch) -> None:
    class LimitedOutput(io.StringIO):
        def write(self, text):
            text.encode("ascii")
            return super().write(text)

    stream = LimitedOutput()
    monkeypatch.setattr(sys, "stdout", stream)
    _write_output("\ud800")
    assert stream.getvalue() == r"\ud800"


def test_conflicting_layout_options_fail_before_language_resolution(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["esolangs", "generate", "--balance", "--width", "10", "NotALang", "01"],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert "--balance and --width are mutually exclusive" in capsys.readouterr().err
