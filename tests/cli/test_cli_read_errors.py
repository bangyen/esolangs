"""Malformed documents and stdin fail before interpreter execution."""

from __future__ import annotations

import io
import os
import select
import signal
import subprocess
import sys
import threading
from collections.abc import Buffer, Iterator
from contextvars import ContextVar
from pathlib import Path

import pytest

import esolangs
from esolangs.cli import io as cli_io
from esolangs.cli import main
from esolangs.cli.io import (
    _bounded_read,
    _read_stdin,
    _write_output,
)
from tests.support.reference import REFERENCE


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


def test_managed_stdin_uses_library_input_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    subtests: pytest.Subtests,
) -> None:
    class Text(str):
        def encode(self, *_args: str, **_options: str) -> bytes:
            raise AssertionError("a stream's str subclass must be normalized")

    class TextStream(io.StringIO):
        def read(self, size: int = -1) -> str:
            return Text(super().read(size))

    class BrokenStream(io.StringIO):
        def read(self, _size: int = -1) -> str:
            raise ValueError("input adapter was closed by its owner")

    class Reader:
        def __init__(self, value):
            self.value = value

        def read(self):
            return self.value

    class FailedProbe(Reader):
        def isatty(self):
            raise OSError("terminal detection unavailable")

    program = tmp_path / "echo.txt"
    program.write_text(",.")
    monkeypatch.setattr(sys, "argv", ["esolangs", "run", REFERENCE, str(program)])
    for make in (
        lambda: io.BytesIO(b"A"),
        lambda: TextStream("A"),
        lambda: Reader("A"),
        lambda: FailedProbe("A"),
    ):
        with subtests.test(stream=type(make()).__name__):
            monkeypatch.setattr(sys, "stdin", make())
            main()
            expected = esolangs.run(REFERENCE, program, stdin=make()).output
            assert expected == "A"
            assert capsys.readouterr() == (expected, "")

    with monkeypatch.context() as patch:
        patch.setattr(sys, "argv", ["esolangs", "read-answer", REFERENCE])
        for adapter in (Reader("1"), FailedProbe("1")):
            patch.setattr(sys, "stdin", adapter)
            main()
            assert capsys.readouterr() == ("1\n", "")

    for make in (BrokenStream, lambda: io.BytesIO(b"A\xff")):
        with subtests.test(stream=type(make()).__name__):
            monkeypatch.setattr(sys, "stdin", make())
            with pytest.raises(SystemExit) as exited:
                main()
            assert exited.value.code == 2
            output, diagnostic = capsys.readouterr()
            assert not output
            with pytest.raises(esolangs.ArgumentError) as error:
                esolangs.run(REFERENCE, program, stdin=make())
            message = str(error.value)
            if isinstance(error.value.__cause__, UnicodeDecodeError):
                message = "cannot read stdin: not text (invalid UTF-8 at byte 1)"
            assert diagnostic.splitlines() == [message, *error.value.__notes__]

    budget = esolangs.ExecutionTimeoutError("input adapter expired")
    budget.bound = "preparation_timeout"
    budget.partial_output = "inner invocation"

    class ExpiredStream(io.StringIO):
        def read(self, _size: int = -1) -> str:
            raise budget

    monkeypatch.setattr(sys, "stdin", ExpiredStream())
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 124
    output, diagnostic = capsys.readouterr()
    assert output == ""
    assert "input adapter expired" in diagnostic
    assert budget.partial_output == "inner invocation"


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
@pytest.mark.skipif(not hasattr(select, "poll"), reason="requires POSIX pipe polling")
def test_previously_read_stdin_keeps_decoder_state_and_wait_policy(
    tmp_path: Path, subtests: pytest.Subtests
) -> None:
    path = tmp_path / "echo.txt"
    path.write_text(",.,.,.,.")
    script = """
import os
import sys
from codecs import getincrementaldecoder
from io import TextIOWrapper
from esolangs.cli import io, main
if os.environ.get("ESOLANGS_TEST_STDIN_SUBCLASS") == "yes":
    class Wrapped(TextIOWrapper):
        __slots__ = ("other_decoder",)
    sys.stdin = Wrapped(sys.stdin.detach(), encoding="utf-8", newline=None)
    sys.stdin.other_decoder = getincrementaldecoder("utf-8")()
assert sys.stdin.read(1) == "A"
stream = sys.stdin.buffer
read = stream.read
stream.read = read
io._WAITING_NOTICE_AFTER = 0.05
main()
assert stream.read is read
assert sys.stdin.read() == ""
"""
    cases = (
        ("utf-8", "eof", b"AB\xc3", b"\xa9\r\n"),
        ("ascii:strict", "eof", b"AB", "é\r\n".encode()),
        ("latin-1", "eof", b"AB\xc3", b"\xa9\r\n"),
        ("utf-8", "subclass", b"AB\xc3", b"\xa9\r\n"),
        ("utf-8:replace", "invalid", b"AB", b"\xff"),
        ("utf-8:replace", "invalid", b"AB", b"\xbd"),
        ("utf-8:ignore", "invalid", b"AB", b"\xbd"),
        ("utf-8:replace", "replacement", b"AB\xef\xbf", b"\xbd\r\n"),
        ("utf-8:ignore", "eof", b"AB\xc3", b"\xa9\r\n"),
        ("utf-8:replace", "extra", b"AB\xe0\xa0", b"\xa0\xa0"),
        ("utf-8", "timeout", b"AB\xc3", b""),
        ("utf-8", "interrupt", b"AB\xc3", b""),
    )
    for encoding, action, prefix, suffix in cases:
        with subtests.test(encoding=encoding, action=action):
            options = ["--preparation-timeout", "1"] if action == "timeout" else []
            command = [
                sys.executable,
                "-c",
                script,
                "run",
                *options,
                REFERENCE,
                str(path),
            ]
            reader, writer = os.pipe()
            with (
                os.fdopen(reader, "rb", buffering=0) as source,
                os.fdopen(writer, "wb", buffering=0) as feed,
            ):
                feed.write(prefix)
                with subprocess.Popen(
                    command,
                    stdin=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={
                        **os.environ,
                        "PYTHONIOENCODING": encoding,
                        "ESOLANGS_TEST_STDIN_SUBCLASS": (
                            "yes" if action == "subclass" else "no"
                        ),
                    },
                ) as child:
                    try:
                        assert child.stderr is not None
                        assert select.select([child.stderr], [], [], 5)[0]
                        assert child.stderr.readline().startswith(
                            b"still waiting for input"
                        )
                        if action in {
                            "eof",
                            "subclass",
                            "invalid",
                            "replacement",
                            "extra",
                        }:
                            feed.write(suffix)
                            feed.close()
                        elif action == "interrupt":
                            child.send_signal(signal.SIGINT)
                        output, diagnostic = child.communicate(timeout=5)
                    finally:
                        if child.poll() is None:
                            child.kill()
            if action in {"eof", "subclass", "replacement"}:
                # The reference interpreter stores the low byte of U+FFFD.
                scalar = "\xfd" if action == "replacement" else "é"
                assert (child.returncode, output, diagnostic) == (
                    0,
                    f"B{scalar}\r\n".encode(),
                    b"",
                )
            elif action in {"invalid", "extra"}:
                assert (child.returncode, output) == (2, b"")
                offset = 4 if action == "extra" else 1
                message = (
                    f"cannot read stdin: not text (invalid UTF-8 at byte {offset})"
                )
                assert diagnostic.splitlines()[0].decode() == message
            elif action == "timeout":
                assert (child.returncode, output) == (124, b"")
                assert b"stdin did not reach EOF" in diagnostic
                assert b"--preparation-timeout" in diagnostic
            else:
                assert (child.returncode, output, diagnostic) == (
                    130,
                    b"",
                    b"interrupted\n",
                )


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


@pytest.mark.medium
@pytest.mark.skipif(
    not hasattr(signal, "pthread_kill"), reason="requires POSIX signals"
)
def test_sigint_delivered_to_the_stdin_reader_exits_130() -> None:
    code = r"""
import os
import signal
import threading
from esolangs.cli import io, main

read = io._read_buffered_stdin

def signal_reader(*args):
    target = threading.get_ident()
    assert target != threading.main_thread().ident

    def interrupt():
        os.write(1, b"sending SIGINT\n")
        signal.pthread_kill(target, signal.SIGINT)

    sender = threading.Timer(0.2, interrupt)
    sender.daemon = True
    sender.start()
    return read(*args)

io._read_buffered_stdin = signal_reader
main()
"""
    with subprocess.Popen(
        [sys.executable, "-c", code, "read-answer", REFERENCE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            assert child.wait(timeout=5) == 130
            assert child.stdout is not None
            assert child.stdout.read() == b"sending SIGINT\n"
            assert child.stderr is not None
            assert child.stderr.read() == b"interrupted\n"
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


@pytest.fixture
def terminal_stdin() -> Iterator[tuple[int, int]]:
    if not hasattr(os, "openpty"):
        pytest.skip("requires a POSIX pseudo-terminal")
    import termios

    terminal, stdin = os.openpty()
    try:
        settings = termios.tcgetattr(stdin)
        settings[3] |= termios.ICANON
        settings[3] &= ~termios.ECHO
        settings[6][termios.VEOF] = b"\x04"
        termios.tcsetattr(stdin, termios.TCSANOW, settings)
        yield terminal, stdin
    finally:
        os.close(stdin)
        os.close(terminal)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("data", "code", "answer"),
    [
        pytest.param(b"0\n1\n\x04", 0, b"1\n", id="lines"),
        pytest.param(b"1\x04\x04", 0, b"1\n", id="partial-line"),
        pytest.param(b"\x04", 1, b"", id="empty"),
    ],
)
def test_read_answer_accepts_terminal_eof(
    terminal_stdin: tuple[int, int], data: bytes, code: int, answer: bytes
) -> None:
    terminal, stdin = terminal_stdin
    os.write(terminal, data)
    got = subprocess.run(
        [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
        stdin=stdin,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (got.returncode, got.stdout) == (code, answer)
    assert b"send EOF with Ctrl-D" in got.stderr
    assert (b"nothing on stdin" in got.stderr) == (code == 1)


@pytest.mark.medium
def test_read_answer_waits_for_terminal_eof_and_handles_interrupt(
    terminal_stdin: tuple[int, int],
) -> None:
    terminal, stdin = terminal_stdin
    os.write(terminal, b"1\n")
    with subprocess.Popen(
        [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            assert child.stderr is not None
            assert child.stdout is not None
            assert select.select([child.stderr], [], [], 10)[0]
            assert b"send EOF with Ctrl-D" in child.stderr.readline()
            assert not select.select([child.stdout], [], [], 0.1)[0]
            child.send_signal(signal.SIGINT)
            output, diagnostic = child.communicate(timeout=10)
        finally:
            if child.poll() is None:
                child.kill()
    assert (child.returncode, output, diagnostic) == (130, b"", b"interrupted\n")


def test_closed_stdin_supplies_no_terminal_input(monkeypatch, capsys) -> None:
    stream = io.StringIO("unused")
    stream.close()
    monkeypatch.setattr(sys, "stdin", stream)
    assert _read_stdin(terminal_prompt="unused") == ""
    assert capsys.readouterr().err == ""


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
def test_blocked_readers_obey_their_deadline(
    monkeypatch, capsys, reader, tmp_path
) -> None:
    released = threading.Event()

    class BlockedInput(io.StringIO):
        def read(self, *_args, **_kwargs):
            released.wait()
            return ""

    with monkeypatch.context() as patch:
        stream = BlockedInput()
        patch.setattr(sys, "stdin", stream)
        patch.setattr("esolangs.cli.io.open", lambda *_a: stream, raising=False)
        try:
            call = (
                (lambda: _read_stdin(0.01))
                if reader == "stdin"
                else (lambda: _bounded_read("blocked", 0.01))
            )
            with pytest.raises(SystemExit) as caught:
                call()
            assert caught.value.code == 124
            assert (
                "stdin" if reader == "stdin" else "blocked"
            ) in capsys.readouterr().err
        finally:
            released.set()

    path = tmp_path / "program"
    path.write_bytes(b"A")
    assert _bounded_read(str(path), 1) == b"A"
    for target in ("buffer", "read") if reader == "stdin" else ("open",):
        _check_late_reader_does_not_probe(monkeypatch, capsys, path, target)


def _check_late_reader_does_not_probe(monkeypatch, capsys, path, target) -> None:
    released = threading.Event()
    threads = []
    probes = []

    def delay():
        threads.append(threading.current_thread())
        assert released.wait(3)

    class TrackedFile(io.FileIO):
        def fileno(self):
            probes.append("fileno")
            return super().fileno()

    class LateRead(io.BytesIO):
        @property
        def read(self):
            delay()
            return self._consume

        def _consume(self):
            probes.append("read")
            return super().read()

    with io.BufferedReader(TrackedFile(path)) as file, LateRead(b"A") as binary:
        probes.clear()

        class Input:
            closed = False

            def isatty(self):
                return False

            @property
            def buffer(self):
                if target == "buffer":
                    delay()
                    return file
                return binary

        def open_late(*_args):
            delay()
            return file

        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdin", Input())
            patch.setattr("esolangs.cli.io.open", open_late, raising=False)
            call = (
                (lambda: _bounded_read(str(path), 0.1))
                if target == "open"
                else (lambda: _read_stdin(0.1))
            )
            try:
                with pytest.raises(SystemExit) as caught:
                    call()
                assert caught.value.code == 124
                assert len(threads) == 1
            finally:
                released.set()
                for thread in threads:
                    thread.join(1)
                    assert not thread.is_alive()
        assert probes == []
        assert binary.tell() == 0
        if target != "open":
            assert file.tell() == 0
    capsys.readouterr()


@pytest.mark.parametrize("gzip_export", [False, True], ids=["display", "gzip"])
def test_cli_completes_short_raw_adapter_writes(tmp_path, monkeypatch, gzip_export):
    class ShortRaw(io.RawIOBase):
        def __init__(self, limit: int | None = None) -> None:
            super().__init__()
            self.data = bytearray()
            self.limit = limit

        def writable(self) -> bool:
            return True

        def write(self, data: Buffer) -> int:
            size = 2
            if self.limit is not None:
                size = min(size, self.limit - len(self.data))
            segment = memoryview(data)[:size]
            self.data.extend(segment)
            return len(segment)

    raw = ShortRaw()
    with (
        io.TextIOWrapper(raw, encoding="utf-16-le", newline="\r") as stdout,
        monkeypatch.context() as patch,
    ):
        patch.setattr(sys, "stdout", stdout)
        if gzip_export:
            patch.setattr(
                sys, "argv", ["esolangs", "generate", "--gzip", REFERENCE, "01"]
            )
            main()
        else:
            patch.setattr(sys, "argv", ["esolangs", "--version"])
            with pytest.raises(SystemExit) as exited:
                main()
            assert exited.value.code == 0
    data = bytes(raw.data)
    if gzip_export:
        expected = tmp_path / "expected.gz"
        esolangs.to_file(
            REFERENCE,
            esolangs.generate(REFERENCE, "01"),
            expected,
            gzip=True,
            normalize=True,
        )
        assert data == expected.read_bytes()
        assert (
            esolangs.read_answer(
                REFERENCE, esolangs.run(REFERENCE, data, stdin="1").output
            )
            == "1"
        )
    else:
        assert data == f"esolangs {esolangs.__version__}\r".encode("utf-16-le")
        for encoding, limit, expected in (
            ("utf-8", None, "unknown option: --élan\n".encode()),
            ("ascii", None, b"unknown option: --\\xe9lan\n"),
            ("utf-8", 19, "unknown option: --é".encode()[:19]),
        ):
            raw = ShortRaw(limit)
            with (
                io.TextIOWrapper(raw, encoding=encoding, write_through=True) as stderr,
                monkeypatch.context() as patch,
            ):
                patch.setattr(sys, "stderr", stderr)
                patch.setattr(sys, "argv", ["esolangs", "list", "--élan"])
                with pytest.raises(SystemExit) as exited:
                    main()
                assert exited.value.code == 2
                assert bytes(raw.data) == expected

        raw = ShortRaw()
        with (
            io.TextIOWrapper(raw, encoding="utf-8", write_through=True) as stderr,
            monkeypatch.context() as patch,
        ):
            patch.setattr(sys, "stderr", stderr)
            patch.setattr(cli_io, "_output_ready", lambda _stream: not raw.data)
            with cli_io._complete_stderr_writes():
                cli_io._diagnostic("optional notice\n", ready_only=True)
                assert bytes(raw.data) == b"op"
                cli_io._diagnostic("required notice\n")
            assert bytes(raw.data) == b"oprequired notice\n"


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
