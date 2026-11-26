"""Reading a program and stdin, and writing what came back."""

import gzip
import json
import os
import select
import signal
import subprocess
import sys
from collections.abc import Buffer, Iterator
from contextlib import suppress
from io import BytesIO, FileIO, StringIO, TextIOWrapper
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO
from unittest.mock import patch

import pytest

import esolangs
from esolangs import serialization
from esolangs.cli import io as cli_io
from esolangs.cli import main
from esolangs.cli.io import (
    _bounded_read,
    _complete_stdout_writes,
    _write_output,
)
from tests.support.cli_support import PACKAGE, call_main, run_cli
from tests.support.pick import languages, one_where
from tests.support.reference import REFERENCE

#: A language whose input bits are not spelled 0 and 1, if one is registered.
_SPELLED = one_where(lambda d: d.input_encoding != ("0", "1"), reads_input=True)


class TestTheStdinReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    def test_an_unanswerable_run_is_refused_before_source_or_stdin_is_read(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        subtests: pytest.Subtests,
    ) -> None:
        """It read stdin first, so these answers waited on input forever."""
        path = tmp_path / "p.txt"
        path.write_text("+.")

        class _NeverEnding:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:  # pragma: no cover - must not be called
                raise AssertionError("stdin was read before the refusal")

        cases = (
            (["NotALang"], "unknown language"),
            (["--seed", "1", REFERENCE], "hint: omit --seed"),
            (["--seed", "2.5", REFERENCE], "--seed must be a whole number"),
            (["--seed", "\x1c1", REFERENCE], "--seed must be a whole number"),
            (["--scale", "1", REFERENCE], "scale is only supported for raster"),
            (["--scale", "0", REFERENCE], "--scale must be a positive integer"),
            (
                ["--execution-timeout", "0", REFERENCE],
                "--execution-timeout must be positive",
            ),
            (["--total-timeout", "nan", REFERENCE], "--total-timeout must be finite"),
            (
                ["--preparation-timeout", "1e10", REFERENCE],
                "--preparation-timeout must be at most",
            ),
            (["--max-steps", "-1", REFERENCE], "--max-steps must not be negative"),
            (
                ["--max-output", "1.5", REFERENCE],
                "--max-output must be a non-negative integer",
            ),
            (
                ["--max-memory", "0", REFERENCE],
                "--max-memory must be a positive integer",
            ),
        )
        scale_refusal = "scale is only supported for raster interpreters"
        combined = []
        for flags in ([], ["--isolated"]):
            outcome = esolangs.Language(REFERENCE).run(
                path, scale=2, seed=1, isolated=bool(flags)
            )
            assert outcome.status == "rejected"
            assert isinstance(outcome.error, esolangs.ArgumentError)
            assert str(outcome.error) == scale_refusal
            assert outcome.observation.steps is None
            options = [*flags, "--seed", "1", "--scale", "2"]
            combined.extend(
                (
                    ([*options, REFERENCE], scale_refusal),
                    ([*options, "--settings", "{}", REFERENCE], scale_refusal),
                    (
                        [*options, "--settings", '{"unknown":1}', REFERENCE],
                        "unknown dialect setting",
                    ),
                )
            )
        with (
            patch(
                "esolangs.cli.run._read_program",
                side_effect=AssertionError("read file"),
            ),
            patch.object(sys, "stdin", _NeverEnding()),
        ):
            for args, error in (*cases, *combined):
                with subtests.test(args=args):
                    argv = ["esolangs", "run", *args, str(path)]
                    with (
                        patch.object(sys, "argv", argv),
                        pytest.raises(SystemExit) as exc,
                    ):
                        main()
                    assert exc.value.code == 2
                    assert error in capsys.readouterr().err


# 6.0s over 12 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestNonTextInputIsRefusedNotCrashed:
    """Pointing `run` at a PNG dumped a traceback with internal paths in it."""

    def test_a_binary_program_file_is_refused(self, tmp_path: Path) -> None:
        """Reachable by a newcomer pointing `run` at the wrong file."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        result = run_cli("run", REFERENCE, str(path))
        assert result.returncode == 2
        assert "not text" in result.stderr
        assert "Traceback" not in result.stderr
        # It named the file by its bytes: 100 KB of stderr for a 100 KB file.
        assert str(path) in result.stderr
        assert len(result.stderr) < 500

    @pytest.mark.parametrize("data", [b"\x80\x81", b"\xed\xa0\x80"])
    def test_binary_stdin_is_refused(self, data: bytes) -> None:
        """A program's binary output piped into `read-answer`."""
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
            input=data,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 2
        assert b"not text" in result.stderr
        assert b"Traceback" not in result.stderr

    def test_binary_stdin_is_refused_under_latin1_io_encoding(self) -> None:
        """Pipes have the same UTF-8 input contract as binary Python streams."""
        env = {**os.environ, "PYTHONIOENCODING": "latin1"}
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
            input=b"\x80\x81",
            capture_output=True,
            timeout=60,
            check=False,
            env=env,
        )
        assert result.returncode == 2
        assert b"not text" in result.stderr
        assert b"Traceback" not in result.stderr

    @pytest.mark.parametrize("isolated", [False, True], ids=["native", "isolated"])
    def test_run_stdin_failures_keep_python_repair_hint(
        self, tmp_path: Path, *, isolated: bool
    ) -> None:
        program = tmp_path / "echo.bf"
        program.write_text(",.")
        route = ["--isolated"] if isolated else []
        argv = [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            *route,
            REFERENCE,
            str(program),
        ]

        with (tmp_path / "writeonly.txt").open("wb") as source:
            unreadable = subprocess.run(
                argv, stdin=source, capture_output=True, timeout=10, check=False
            )
            with os.fdopen(os.dup(source.fileno()), "rb") as python_stdin:
                bad_fd = esolangs.run(
                    REFERENCE, program, stdin=python_stdin, isolated=isolated
                ).error
        assert isinstance(bad_fd, esolangs.ArgumentError)
        assert (unreadable.returncode, unreadable.stdout) == (2, b"")
        assert unreadable.stderr.decode().splitlines() == [
            str(bad_fd),
            *bad_fd.__notes__,
        ]

        invalid = b"Q\xff"
        undecodable = subprocess.run(
            argv, input=invalid, capture_output=True, timeout=10, check=False
        )
        bad_text = esolangs.run(
            REFERENCE, program, stdin=invalid, isolated=isolated
        ).error
        assert isinstance(bad_text, esolangs.ArgumentError)
        assert str(bad_text) == "cannot read stdin: not text (invalid UTF-8 at byte 1)"
        assert (undecodable.returncode, undecodable.stdout) == (2, b"")
        assert undecodable.stderr.decode().splitlines() == [
            str(bad_text),
            *bad_text.__notes__,
        ]

    def test_the_library_names_it_as_a_program_error(self, tmp_path: Path) -> None:
        """``check_program`` decodes a Path and had the same gap."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(esolangs.ProgramError, match="not text"):
            esolangs.run(REFERENCE, path).unwrap()


@pytest.fixture
def nonblocking_pipe() -> Iterator[tuple[FileIO, FileIO]]:
    reader, writer = os.pipe()
    with (
        os.fdopen(reader, "rb", buffering=0) as source,
        os.fdopen(writer, "wb", buffering=0) as feed,
    ):
        os.set_blocking(source.fileno(), False)
        yield source, feed


@pytest.mark.medium
@pytest.mark.skipif(not hasattr(select, "poll"), reason="requires POSIX pipe polling")
@pytest.mark.parametrize("prefix", [b"", b"\xc3"], ids=["empty", "split-utf8"])
def test_nonblocking_stdin_reads_delayed_utf8(
    nonblocking_pipe: tuple[FileIO, FileIO], prefix: bytes, tmp_path: Path
) -> None:
    source, feed = nonblocking_pipe
    path = tmp_path / "echo.txt"
    path.write_text(",.", encoding="utf-8")
    payload = "é".encode()
    feed.write(prefix)
    script = (
        "import threading\n"
        "from esolangs.cli import io, main\n"
        "io._WAITING_NOTICE_AFTER = 0.1\n"
        "diagnostic = io._diagnostic\n"
        "background_notice = False\n"
        "def announce(*args, **kwargs):\n"
        "    global background_notice\n"
        "    if threading.current_thread() is not threading.main_thread():\n"
        "        background_notice = True\n"
        "    diagnostic(*args, **kwargs)\n"
        "io._diagnostic = announce\n"
        "main()\n"
        "assert not background_notice\n"
    )
    with subprocess.Popen(
        [sys.executable, "-c", script, "run", REFERENCE, str(path)],
        stdin=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            assert child.stderr is not None
            assert select.select([child.stderr], [], [], 10)[0]
            assert child.stderr.readline().startswith(b"still waiting for input")
            feed.write(payload[len(prefix) :])
            feed.close()
            output, diagnostic = child.communicate(timeout=10)
        finally:
            if child.poll() is None:
                child.kill()
    assert (child.returncode, output, diagnostic) == (0, payload, b"")
    assert not os.get_blocking(source.fileno())


@pytest.mark.medium
@pytest.mark.skipif(not hasattr(select, "poll"), reason="requires POSIX pipe polling")
@pytest.mark.parametrize("ingress", ["stdin", "source"])
def test_nonblocking_pipe_requires_eof_before_running(
    nonblocking_pipe: tuple[FileIO, FileIO], ingress: str, tmp_path: Path
) -> None:
    source, feed = nonblocking_pipe
    if ingress == "source":
        path = Path("/dev/fd/0")
        if not path.exists():
            pytest.skip("no /dev/fd")
        feed.write(b"+")
        diagnostic = b"gave up reading /dev/fd/0"
    else:
        path = tmp_path / "echo.txt"
        path.write_text(",.", encoding="utf-8")
        feed.write(b"A")
        diagnostic = b"stdin did not reach EOF"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            "--total-timeout",
            "1",
            REFERENCE,
            str(path),
        ],
        stdin=source,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert (result.returncode, result.stdout) == (124, b"")
    assert diagnostic in result.stderr
    assert b"--total-timeout" in result.stderr
    assert not os.get_blocking(source.fileno())


@pytest.mark.medium
def test_piped_text_is_utf8_across_cli_commands(tmp_path: Path) -> None:
    def call(*args: str, stdin: bytes = b"") -> bytes:
        return subprocess.run(
            [sys.executable, "-m", "esolangs", *args],
            input=stdin,
            capture_output=True,
            timeout=30,
            check=True,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
        ).stdout

    encoded = one_where(
        lambda facts: (
            facts.input_encoding is not None
            and any(not bit.isascii() for bit in facts.input_encoding)
        ),
        input_shape="char_stream",
    )
    if not encoded:
        pytest.skip("no non-ASCII character-stream alphabet")
    encoding_language = encoded[0]
    bit = next(
        bit
        for bit in "01"
        if not esolangs.encode_inputs(encoding_language, [int(bit)]).isascii()
    )
    payload = call("encode-inputs", encoding_language, bit)
    assert payload == esolangs.encode_inputs(encoding_language, [int(bit)]).encode()
    echo = tmp_path / "echo.bf"
    echo.write_text(",.,.,.")
    payload += b"\r\n"
    assert call("run", REFERENCE, str(echo), stdin=payload) == payload

    readers = languages(
        source_kind="text", parameterized=False, reads_input=True, answer_mode="output"
    )
    for language in readers:
        source = esolangs.generate(language, "01").source
        if isinstance(source, str) and not source.isascii():
            break
    else:
        pytest.skip("no Unicode program from a text stdin generator")
    source = call("generate", language, "01")
    assert not source.isascii()
    program = tmp_path / "generated.txt"
    program.write_bytes(source)
    stdin = call("encode-inputs", language, "1")
    output = call("run", language, str(program), stdin=stdin)
    assert call("read-answer", language, stdin=output) == b"1\n"


@pytest.mark.medium
def test_isolated_cli_uses_utf8_with_a_different_configured_encoding(
    tmp_path: Path,
) -> None:
    echo = tmp_path / "echo.bf"
    echo.write_text(",.")
    payload = "é".encode()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            "--execution-timeout",
            "5",
            REFERENCE,
            str(echo),
        ],
        input=payload,
        capture_output=True,
        timeout=15,
        check=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-16"},
    )
    assert result.stdout == payload


@pytest.mark.medium
def test_catalog_json_uses_utf8_on_a_pipe() -> None:
    for command in (
        ["list", "--json"],
        ["list", "--json", "--details"],
        ["describe", "--json", REFERENCE],
        ["describe", "--json", "--spec", REFERENCE],
    ):
        report = subprocess.run(
            [sys.executable, "-m", "esolangs", *command],
            capture_output=True,
            timeout=30,
            check=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-16"},
        )
        assert json.loads(report.stdout.decode("utf-8"))


def test_ascii_stderr_adapter_keeps_usage_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AsciiStderr(StringIO):
        encoding = "ascii"

        def write(self, data: str) -> int:
            segment = data[:3]
            segment.encode(self.encoding)
            return super().write(segment)

    stream = AsciiStderr()
    monkeypatch.setattr(sys, "stderr", stream)
    monkeypatch.setattr(sys, "argv", ["esolangs", "list", "--élan"])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 2
    assert stream.getvalue() == "unknown option: --\\xe9lan\n"

    stream.seek(0)
    stream.truncate()
    monkeypatch.setattr(cli_io, "_output_ready", lambda adapter: not adapter.getvalue())
    cli_io._diagnostic("optional notice\n", ready_only=True)
    assert stream.getvalue() == "opt"
    cli_io._diagnostic("required notice\n")
    assert stream.getvalue() == "optrequired notice\n"


@pytest.mark.medium
@pytest.mark.parametrize("destination", ["read-only", "broken-pipe"])
@pytest.mark.parametrize(
    ("source", "options", "code", "output"),
    [
        ("", [], 0, b""),
        ("[", [], 2, b""),
        ("+.,.", [], 1, b"\x01"),
        ("+.,.", ["--max-steps", "2"], 124, b"\x01"),
    ],
)
def test_unwritable_stderr_preserves_status_and_output(
    destination: str,
    source: str,
    options: list[str],
    code: int,
    output: bytes,
    tmp_path: Path,
) -> None:
    path = tmp_path / "program.txt"
    path.write_text(source, encoding="utf-8")
    if destination == "read-only":
        stderr = os.open(os.devnull, os.O_RDONLY)
    else:
        reader, stderr = os.pipe()
        os.close(reader)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "run", *options, REFERENCE, str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr,
            timeout=15,
            check=False,
        )
    finally:
        os.close(stderr)
    assert (result.returncode, result.stdout) == (code, output)


# 8.5s over 9 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestReadingTheProgramFileIsBounded:
    """It was the one unguarded blocking call left in the command."""

    def test_a_character_device_is_refused_by_size(self) -> None:
        """`/dev/zero` reached 3.9 GB of resident memory and never returned."""
        result = run_cli("run", "--execution-timeout", "2", REFERENCE, "/dev/zero")
        assert result.returncode == 2
        assert "larger than" in result.stderr

    @pytest.mark.slow
    def test_a_fifo_with_no_writer_is_bounded(self, tmp_path: Path) -> None:
        """`--execution-timeout` bounds the *run*, and this happens before one."""
        import os

        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        result = run_cli("run", "--execution-timeout", "2", REFERENCE, str(fifo))
        assert result.returncode == 124
        assert "not delivering data" in result.stderr

    def test_an_ordinary_program_still_reads(self, tmp_path: Path) -> None:
        """The guard is worth nothing if it costs the normal path."""
        path = tmp_path / "p.txt"
        serialization.to_file(REFERENCE, esolangs.generate(REFERENCE, "0110"), path)
        result = run_cli("run", REFERENCE, str(path), stdin="10")
        expected = esolangs.run(REFERENCE, path, stdin="10").unwrap().output
        assert (result.returncode, result.stdout, result.stderr) == (0, expected, "")
        assert esolangs.read_answer(REFERENCE, expected) == "1"

    @pytest.mark.parametrize(
        ("directory", "error_type", "hint"),
        [
            (
                False,
                esolangs.ProgramNotFoundError,
                "check that the source path exists and names the intended program file",
            ),
            (
                True,
                esolangs.ProgramError,
                "check that the program file or stream is readable",
            ),
        ],
        ids=["missing", "directory"],
    )
    def test_source_open_error_keeps_python_repair_hint(
        self,
        tmp_path: Path,
        *,
        directory: bool,
        error_type: type[esolangs.ProgramError],
        hint: str,
    ) -> None:
        path = tmp_path / "native source"
        if directory:
            path.mkdir()
        with pytest.raises(error_type) as caught:
            esolangs.run(REFERENCE, path).unwrap()
        assert type(caught.value) is error_type
        opened = run_cli("run", REFERENCE, str(path))
        assert (opened.returncode, opened.stdout) == (2, "")
        assert opened.stderr.splitlines() == [str(caught.value), f"hint: {hint}"]


class TestTheBoundedReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    @pytest.mark.parametrize("offset", [0, 2, 10])
    def test_regular_file_stops_at_the_opening_end(
        self,
        tmp_path: Path,
        offset: int,
    ) -> None:
        """An fd alias can start inside or past the existing contents."""
        path = tmp_path / "source"
        original = b"abcd"
        path.write_bytes(original)
        fstat = os.fstat

        def append_after_stat(fd: int) -> os.stat_result:
            opened = fstat(fd)
            with path.open("ab") as writer:
                writer.write(b"efghijkl")
            return opened

        with path.open("rb") as handle:
            handle.seek(offset)
            with (
                patch("esolangs.cli.io.open", return_value=handle, create=True),
                patch("esolangs.cli.io.os.fstat", side_effect=append_after_stat),
            ):
                assert _bounded_read(str(path), 1.0, max_bytes=1) == original[offset:]

    @pytest.mark.parametrize("text", ["", "é", "€"])
    def test_zero_reported_size_still_uses_the_stream_cap(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
    ) -> None:
        """A pseudo-file can contain bytes despite reporting size zero."""
        path = tmp_path / "source"
        data = text.encode()
        path.write_bytes(data)
        opened = SimpleNamespace(st_mode=path.stat().st_mode, st_size=0)
        with patch("esolangs.cli.io.os.fstat", return_value=opened):
            if len(data) <= 2:
                assert _bounded_read(str(path), 1.0, max_bytes=2) == data
            else:
                with pytest.raises(SystemExit) as exc:
                    _bounded_read(str(path), 1.0, max_bytes=2)
                assert exc.value.code == 2
        assert ("larger than" in capsys.readouterr().err) == (len(data) > 2)


def test_unbuffered_stdout_retries_short_writes_and_restores_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "output"
    with (
        FileIO(path, "w") as raw,
        TextIOWrapper(
            raw, encoding="utf-16", newline="\r", write_through=True
        ) as stdout,
    ):
        stdout.write("before\n")
        write = raw.write
        writes: list[int | None] = []

        def short(data: Buffer) -> int | None:
            count = write(memoryview(data)[:2])
            writes.append(count)
            return count

        vars(raw)["write"] = short
        monkeypatch.setattr(sys, "stdout", stdout)
        with _complete_stdout_writes():
            _write_output("éλ\n", utf8=False)
        assert raw.write is short
    assert writes == [2, 2, 2]
    assert path.read_bytes() == "before\réλ\r".encode("utf-16")


@pytest.mark.medium
@pytest.mark.parametrize("blocked", [False, True])
def test_direct_binary_adapter_keeps_exact_utf8(tmp_path, monkeypatch, blocked):
    data = bytearray()

    def write(chunk: bytes) -> int | None:
        if blocked and data:
            return None
        data.extend(chunk[:2])
        return len(chunk[:2])

    class Capture:
        buffer = SimpleNamespace(write=write)

        def isatty(self) -> bool:
            raise OSError("terminal detection unavailable")

        def flush(self) -> None:
            pass

    path = tmp_path / "echo.bf"
    path.write_text(",.,.,.,.")
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", Capture())
        patch.setattr(sys, "stdin", StringIO("ABCé"))
        patch.setattr(
            sys, "argv", ["esolangs", "run", "--isolated", REFERENCE, str(path)]
        )
        if blocked:
            with pytest.raises(SystemExit) as exited:
                main()
            assert exited.value.code == 120
        else:
            main()
    assert data == (b"AB" if blocked else "ABCé".encode())


def test_gzip_reports_an_unavailable_binary_stdout(monkeypatch, capsys):
    output = StringIO()
    command = ["esolangs", "generate", REFERENCE, "01"]
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", output)
        patch.setattr(sys, "argv", [*command, "--gzip"])
        with pytest.raises(SystemExit) as exited:
            main()
        assert exited.value.code == 120
        assert output.getvalue() == ""
        patch.setattr(sys, "argv", command)
        main()
    assert "cannot write stdout: binary output requires" in capsys.readouterr().err
    assert esolangs.run(REFERENCE, output.getvalue(), stdin="1").unwrap().output == "1"


@pytest.fixture
def full_pipe() -> Iterator[tuple[BinaryIO, BinaryIO]]:
    if os.name != "posix":
        pytest.skip("requires a POSIX nonblocking pipe")
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "rb") as reader, os.fdopen(write_fd, "wb") as writer:
        fd = writer.fileno()
        os.set_blocking(fd, False)
        for block in (b"x" * 512, b"x"):
            with suppress(BlockingIOError):
                while True:
                    os.write(fd, block)
        yield reader, writer


@pytest.mark.medium
@pytest.mark.parametrize(
    "args", [("encode-inputs", REFERENCE, "01"), ("list",)], ids=["raw", "display"]
)
def test_unbuffered_stdout_refuses_a_full_pipe(
    args: tuple[str, ...], full_pipe: tuple[BinaryIO, BinaryIO]
) -> None:
    reader, writer = full_pipe
    result = subprocess.run(
        [sys.executable, "-u", "-m", "esolangs", *args],
        stdout=writer,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    assert not os.get_blocking(writer.fileno())
    writer.close()
    assert set(reader.read()) == {ord("x")}
    assert result.returncode == 120
    assert b"cannot write stdout:" in result.stderr


@pytest.mark.medium
@pytest.mark.parametrize(
    ("phase", "args"),
    [
        ("_flush_stdout", ("list",)),
        ("_write_output", ("encode-inputs", REFERENCE, "01" * 8192)),
    ],
    ids=["flush", "write"],
)
def test_interrupting_stdout_exits_without_draining_the_pipe(
    phase: str, args: tuple[str, ...], full_pipe: tuple[BinaryIO, BinaryIO]
) -> None:
    reader, writer = full_pipe
    os.set_blocking(writer.fileno(), True)
    # The raw hook signals readiness from inside the buffered I/O call.
    code = r"""
import os
import sys
from esolangs.cli import main

sys.stdout = open(sys.stdout.fileno(), "w", 8192, encoding="utf-8", closefd=False)
raw = sys.stdout.buffer.raw
write = raw.write
announce = True

def signal_ready(data):
    global announce
    if announce:
        announce = False
        frame = sys._getframe(1)
        while frame and frame.f_code.co_name not in ("_flush_stdout", "_write_output"):
            frame = frame.f_back
        phase = frame.f_code.co_name if frame else "unexpected"
        os.write(2, (phase + "\n").encode("ascii"))
    return write(data)

raw.write = signal_ready
main()
"""
    with subprocess.Popen(
        [sys.executable, "-c", code, *args],
        stdin=subprocess.DEVNULL,
        stdout=writer,
        stderr=subprocess.PIPE,
    ) as child:
        try:
            assert child.stderr is not None
            assert select.select([child.stderr], [], [], 10)[0]
            assert child.stderr.readline() == phase.encode("ascii") + b"\n"
            child.send_signal(signal.SIGINT)
            _, diagnostic = child.communicate(timeout=5)
        finally:
            if child.poll() is None:
                child.kill()
    assert (child.returncode, diagnostic) == (130, b"interrupted\n")
    assert os.get_blocking(writer.fileno())
    writer.close()
    assert set(reader.read()) == {ord("x")}


@pytest.mark.medium
def test_stderr_failure_does_not_change_usage_status(
    full_pipe: tuple[BinaryIO, BinaryIO],
) -> None:
    reader, writer = full_pipe
    command = [sys.executable, "-m", "esolangs", "list", "--bad"]
    control = subprocess.run(command, capture_output=True, timeout=5, check=False)
    assert (control.returncode, control.stdout, control.stderr) == (
        2,
        b"",
        b"unknown option: --bad\n",
    )
    blocked = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=writer, timeout=5, check=False
    )
    assert (blocked.returncode, blocked.stdout) == (2, b"")
    assert not os.get_blocking(writer.fileno())
    writer.close()
    assert set(reader.read()) == {ord("x")}


@pytest.mark.medium
@pytest.mark.parametrize(
    ("phase", "args"),
    [
        ("diagnostic", ("list", "--bad")),
        ("interrupt", ("read-answer", REFERENCE)),
        ("notice", ("read-answer", REFERENCE)),
    ],
)
def test_sigint_does_not_wait_on_full_stderr(
    phase: str, args: tuple[str, ...], full_pipe: tuple[BinaryIO, BinaryIO]
) -> None:
    reader, writer = full_pipe
    os.set_blocking(writer.fileno(), True)
    code = r"""
import os
import signal
import sys
from esolangs import cli
from esolangs.cli import io

phase = sys.argv.pop(1)

def ready():
    os.write(1, b"ready\n")

if phase == "diagnostic":
    sys.stderr = open(sys.stderr.fileno(), "w", 8192, encoding="utf-8", closefd=False)
    raw = sys.stderr.buffer.raw
    write = raw.write
    def blocked(data):
        raw.write = write
        ready()
        return write(data)
    raw.write = blocked
elif phase == "interrupt":
    def start(_thread):
        try:
            ready()
            signal.pause()
        except KeyboardInterrupt:
            # CPython can mask the interrupt while releasing its startup lock.
            raise RuntimeError("release unlocked lock") from None
    io.threading.Thread.start = start
else:
    io._WAITING_NOTICE_AFTER = 0.1
    diagnostic = io._diagnostic
    def announce(*args, **options):
        diagnostic(*args, **options)
        ready()
    io._diagnostic = announce

cli.main()
"""
    with subprocess.Popen(
        [sys.executable, "-c", code, phase, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=writer,
    ) as child:
        try:
            assert child.stdout is not None
            assert select.select([child.stdout], [], [], 10)[0]
            assert child.stdout.readline() == b"ready\n"
            child.send_signal(signal.SIGINT)
            assert child.wait(timeout=5) == 130
            assert child.stdout.read() == b""
        finally:
            if child.poll() is None:
                child.kill()
    assert os.get_blocking(writer.fileno())
    writer.close()
    assert set(reader.read()) == {ord("x")}


# 2.2s over 6 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestAClosedPipeIsNotAnError:
    """`esolangs generate ... | head` is an ordinary thing to type."""

    def test_closing_before_the_first_write_is_silent(self) -> None:
        """It printed "Exception ignored while flushing sys.stdout"."""
        import subprocess

        first = subprocess.Popen(
            [sys.executable, "-m", "esolangs", "generate", REFERENCE, "0110"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert first.stdout is not None
        first.stdout.close()
        first.wait(timeout=30)
        assert first.stderr is not None
        assert "BrokenPipeError" not in first.stderr.read()

    def test_a_closed_stdout_exits_120(self, monkeypatch, capsys) -> None:
        """``esolangs list >&-`` reported an internal error, exit 70."""
        import subprocess

        # Closed before Python starts, so ``sys.stdout`` is None.
        closed = subprocess.run(
            ["sh", "-c", f"'{sys.executable}' -m esolangs list >&-"],
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert closed.returncode == 120, closed.stderr
        both = subprocess.run(
            ["sh", "-c", f"'{sys.executable}' -m esolangs list >&- 2>&-"],
            timeout=30,
            check=False,
        )
        assert both.returncode == 120  # It wrote to a None stderr: exit 1.

        for operation in ("write", "flush"):
            stream = StringIO() if operation == "write" else TextIOWrapper(BytesIO())
            if operation == "flush":
                stream.reconfigure = lambda **_options: None
            selected = getattr(stream, operation)

            def close_then_use(
                *args, stream=stream, selected=selected, operation=operation
            ):
                setattr(stream, operation, selected)
                stream.close()
                return selected(*args)

            setattr(stream, operation, close_then_use)
            with monkeypatch.context() as active:
                active.setattr(sys, "stdout", stream)
                with pytest.raises(SystemExit) as exited:
                    call_main(["read-answer", REFERENCE], capsys, stdin="1")
            assert exited.value.code == 120
            assert "cannot write stdout:" in capsys.readouterr().err

        stream = StringIO()

        def broken(_data):
            raise ValueError("invalid writer callback")

        stream.write = broken
        with monkeypatch.context() as active:
            active.setattr(sys, "stdout", stream)
            with pytest.raises(SystemExit) as exited:
                call_main(["read-answer", REFERENCE], capsys, stdin="1")
        assert exited.value.code == 70
        assert "internal error: ValueError: invalid writer callback" in (
            capsys.readouterr().err
        )

    def test_unwritable_stdout_is_a_destination_error(self, tmp_path: Path) -> None:
        path = tmp_path / "readonly.txt"
        path.write_text("original")
        with path.open("rb") as destination:
            result = subprocess.run(
                [sys.executable, "-m", "esolangs", "describe", "--json", REFERENCE],
                stdout=destination,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
        assert result.returncode == 120, result.stderr
        assert result.stderr.startswith(b"cannot write stdout:")
        assert len(result.stderr.splitlines()) == 1
        assert path.read_text() == "original"

    def test_unreadable_stdin_is_a_usage_error(self, tmp_path: Path) -> None:
        with (tmp_path / "writeonly.txt").open("wb") as source:
            result = subprocess.run(
                [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
                stdin=source,
                capture_output=True,
                timeout=10,
                check=False,
            )
        assert result.returncode == 2, result.stderr
        assert not result.stdout
        assert result.stderr.startswith(b"cannot read stdin:")

    def test_a_closed_stderr_still_runs(self, tmp_path: Path) -> None:
        """``2>&-``: every note wrote to None, so `run` printed nothing, exit 1."""
        import subprocess

        path = tmp_path / "p.txt"
        path.write_text("+.")
        closed = subprocess.run(
            [
                "sh",
                "-c",
                f"'{sys.executable}' -m esolangs run {REFERENCE} '{path}' 2>&-",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        assert (closed.returncode, closed.stdout) == (0, b"\x01")

    def test_an_ascii_stdout_lists_language_selectors(
        self, monkeypatch, capsys
    ) -> None:
        """``PYTHONIOENCODING=ascii esolangs list`` died mid-line, exit 70."""
        import os
        import subprocess

        listed = subprocess.run(
            [sys.executable, "-m", "esolangs", "list"],
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert listed.returncode == 0, listed.stderr
        selectors = listed.stdout.decode("ascii").splitlines()
        assert [esolangs.Language(label).name for label in selectors] == sorted(
            esolangs.list_languages(), key=lambda n: not esolangs.describe(n).well_known
        )

        class Writer:
            def __init__(self, codec) -> None:
                self.codec = codec
                self.sink = StringIO()

            def write(self, data: str) -> int:
                data.encode(self.codec)
                return self.sink.write(data)

            def flush(self) -> None:
                self.sink.flush()

        class Unspecified(Writer):
            encoding = None

        for adapter in (Writer, Unspecified):
            stdout = adapter("ascii")
            with monkeypatch.context() as active:
                active.setattr(sys, "stdout", stdout)
                active.setattr(sys, "argv", ["esolangs", "list"])
                main()
            assert stdout.sink.getvalue().encode("ascii") == listed.stdout
            assert not capsys.readouterr().err

        description = call_main(["describe", REFERENCE], capsys)
        for stdout in (Writer("utf-8"), Unspecified("ascii")):
            with monkeypatch.context() as active:
                active.setattr(sys, "stdout", stdout)
                active.setattr(sys, "argv", ["esolangs", "describe", REFERENCE])
                main()
            assert stdout.sink.getvalue() == description
            assert not capsys.readouterr().err

    @pytest.mark.slow
    def test_an_isolated_worker_dies_with_its_parent(self, tmp_path: Path) -> None:
        """SIGTERM to the parent skipped its reap; the worker looped for hours."""
        import signal
        import subprocess
        import time

        path = tmp_path / "loop.txt"
        path.write_text("+[]")
        parent = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "esolangs",
                "run",
                "--isolated",
                "--execution-timeout",
                "60",
                REFERENCE,
                str(path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        workers = subprocess.run(
            ["pgrep", "-P", str(parent.pid)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        parent.send_signal(signal.SIGTERM)
        parent.wait()
        time.sleep(2)
        alive = [
            pid
            for pid in workers
            if subprocess.run(
                ["ps", "-p", pid], capture_output=True, check=False
            ).returncode
            == 0
        ]
        for pid in alive:
            subprocess.run(["kill", pid], check=False)
        assert workers
        assert not alive

    def test_a_closed_stdin_reads_as_empty(self) -> None:
        """``read-answer <&-`` reported an internal error, exit 70."""
        import subprocess

        closed = subprocess.run(
            ["sh", "-c", f"'{sys.executable}' -m esolangs read-answer {REFERENCE} <&-"],
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert closed.returncode == 1, closed.stderr
        assert "nothing on stdin" in closed.stderr


class TestProgramFilesLoad:
    """The newline a text file ends with is the file's, not the program's."""

    @pytest.mark.parametrize("gzip_output", [False, True])
    def test_emission_retains_terminal_source_cr(
        self, capsysbinary, tmp_path: Path, *, gzip_output: bool
    ) -> None:
        from esolangs.cli import _emit

        source = esolangs.from_source(REFERENCE, "+.\r")
        _emit(source, plain=False, gzip=gzip_output)
        path = tmp_path / "source"
        path.write_bytes(capsysbinary.readouterr().out)
        assert serialization.from_file(REFERENCE, path, normalize=True).source == "+.\n"
        if gzip_output:
            assert gzip.decompress(path.read_bytes()) == b"+.\r\r\n"

    @pytest.mark.parametrize("spelled", _SPELLED)
    def test_a_generated_file_runs_as_written(
        self, spelled: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``esolangs generate > f`` wrote a newline three interpreters reject."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate(spelled, "0110").source + "\n")
        stdin = esolangs.encode_inputs(spelled, [0, 1])
        out = call_main(["run", spelled, str(path)], capsys, stdin=stdin)
        assert esolangs.read_answer(spelled, out) == "1"

    @pytest.mark.parametrize(
        "name",
        [
            name
            for name in languages(
                source_kind="text", parameterized=False, answer_mode="output"
            )
            if esolangs.describe(name).examples
        ],
    )
    def test_the_committed_examples_run(
        self, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Three once failed on the newline their own file ends with."""
        path = PACKAGE / esolangs.describe(name).examples[0]
        stdin = esolangs.encode_inputs(name, [0, 1])
        assert call_main(["run", name, str(path)], capsys, stdin=stdin)


@pytest.mark.parametrize("filename", ["--execution-timeout", "--help"])
def test_run_flag_filename_after_separator(
    filename: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A positional filename must survive every option parser."""
    monkeypatch.chdir(tmp_path)
    Path(filename).write_text("+.")
    assert call_main(["run", REFERENCE, "--", filename], capsys) == "\x01"


@pytest.mark.parametrize(
    ("command", "filename"), [("list", "--json"), ("describe", "--spec")]
)
def test_bare_flags_after_separator_are_positional(
    command: str,
    filename: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The separator must not silently enable a display mode."""
    with (
        patch.object(sys, "argv", ["esolangs", command, "--", filename]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 2
    assert not capsys.readouterr().out


def test_width_after_separator_is_positional() -> None:
    from esolangs.cli.args import _pop_width

    assert _pop_width(["--", "--width", "80"]) == (["--", "--width", "80"], None, False)
