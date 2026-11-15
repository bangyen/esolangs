"""Malformed documents and stdin fail before interpreter execution."""

from __future__ import annotations

import io
import os
import select
import subprocess
import sys
import threading
from contextvars import ContextVar

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


def test_stdin_reads_prefetched_file_bytes(tmp_path, monkeypatch) -> None:
    path = tmp_path / "stdin"
    path.write_bytes(b"12")
    with path.open() as stdin:
        assert stdin.buffer.peek(1).startswith(b"1")
        monkeypatch.setattr(sys, "stdin", stdin)
        assert _read_stdin(1) == "12"


@pytest.mark.parametrize("use_poll", [False, True])
def test_stdin_reads_prefetched_pipe_bytes(monkeypatch, use_poll) -> None:
    if use_poll and not hasattr(select, "poll"):
        pytest.skip("poll unavailable")
    if not use_poll:
        monkeypatch.delattr(select, "poll", raising=False)
    reader, writer = os.pipe()
    encoded = "λ".encode()
    with os.fdopen(reader) as stdin, os.fdopen(writer, "wb", buffering=0) as feed:
        feed.write(encoded[:1])
        assert stdin.buffer.peek(1) == encoded[:1]
        feed.write(encoded[1:])
        feed.close()
        monkeypatch.setattr(sys, "stdin", stdin)
        assert _read_stdin(1) == "λ"
        assert os.get_blocking(reader)


@pytest.mark.medium
def test_prefetched_stdin_exits_cleanly_with_writer_open() -> None:
    code = """
import sys
from esolangs.cli.io import _read_stdin
assert sys.stdin.buffer.peek(1) == b'x'
_read_stdin(0.15)
"""
    with subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        assert child.stdin is not None
        assert child.stderr is not None
        child.stdin.write(b"x")
        child.stdin.flush()
        try:
            assert child.wait(6) == 124
            assert b"stdin did not reach EOF" in child.stderr.read()
        finally:
            if child.poll() is None:
                child.kill()


def test_reader_thread_inherits_the_callers_context(monkeypatch) -> None:
    supplied = ContextVar("supplied", default="default")

    class ContextInput(io.StringIO):
        def read(self, *_args, **_kwargs):
            return supplied.get()

    monkeypatch.setattr(sys, "stdin", ContextInput())
    token = supplied.set("caller")
    try:
        assert _read_stdin(1) == "caller"
    finally:
        supplied.reset(token)


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
