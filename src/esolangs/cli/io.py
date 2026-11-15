"""Reading a program and stdin under a bound, and writing the answer out.

Both can block forever (a fifo, a pipe nobody writes to), so every read
carries a size and a deadline, and two notices say why nothing happened.
"""

from __future__ import annotations

import os
import select
import stat
import sys
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from contextvars import copy_context
from io import BufferedReader, FileIO
from math import ceil
from time import monotonic, sleep
from typing import BinaryIO, cast

from esolangs.artifacts import ProgramArtifact
from esolangs.cli.args import _diagnostic, _fail
from esolangs.cli.hints import _TIMEOUT_EXIT, _decode_note
from esolangs.exceptions import EsolangError
from esolangs.operations.source import _check_program
from esolangs.registry import Catalog, get_catalog
from esolangs.runtime._files import (
    _BLOCK,
    StreamReadTimeoutError,
    _time_remaining,
    read_snapshot,
    stream_read_deadline,
)
from esolangs.runtime._program import Program
from esolangs.runtime._source import _FileSource
from esolangs.settings import DialectSettings

#: How long a blocking stdin read waits before it says that it is waiting.
#: Shorter than the run notice: a read that has not finished is far more
#: likely to be a mistake than a program that is still going.
_WAITING_NOTICE_AFTER = 3.0


#: Keep source reads bounded, including devices that never reach EOF.
_MAX_PROGRAM_BYTES = 1024 * 1024
#: A gzip-native runtime may also read the full raw export of its generator.
_MAX_GZIP_NATIVE_PROGRAM_BYTES = 32 * _MAX_PROGRAM_BYTES


#: Fallback deadline for reading a program file.
_READ_DEADLINE = 10.0


#: How long an unbounded run goes before it says that it is unbounded.
#: A constant so a test can shorten it rather than wait.
_UNBOUNDED_NOTICE_AFTER = 10.0


class _DelayedNotice:
    """Print one line if the wrapped wait is still going after a while.

    The timer fires once and is cancelled when the wait finishes,
    whether it finished or raised.
    """

    def __init__(self, after: float, message: str) -> None:
        """Arm the notice to write ``message`` after ``after`` seconds."""
        self._timer = threading.Timer(after, _diagnostic, args=(message,))
        self._timer.daemon = True

    def __enter__(self) -> None:
        """Start the timer."""
        self._timer.start()

    def __exit__(self, *_exc: object) -> None:
        """Cancel it."""
        self._timer.cancel()


def _unbounded_notice(command: str) -> _DelayedNotice:
    """Notice for an unbounded ``command`` run still going after a while."""
    return _DelayedNotice(
        _UNBOUNDED_NOTICE_AFTER,
        f"still running after {_UNBOUNDED_NOTICE_AFTER:.0f}s with no bound; "
        f"several of these languages loop forever by design -- "
        f"`esolangs {command} --execution-timeout SECONDS` stops one\n",
    )


def _waiting_notice(hint: str = "") -> _DelayedNotice:
    """Notice for stdin still not delivering after a while."""
    return _DelayedNotice(
        _WAITING_NOTICE_AFTER,
        f"still waiting for input on stdin after {_WAITING_NOTICE_AFTER:.0f}s; "
        f"nothing has closed it{hint}\n",
    )


def _read_program(
    path: str,
    timeout: float | None = None,
    *,
    language: str,
    timeout_flag: str = "",
    settings: DialectSettings | None = None,
    catalog: Catalog | None = None,
) -> ProgramArtifact[Program]:
    """Read bounded source, refusing a non-text or oversized file."""
    started = monotonic()
    catalog = get_catalog(catalog)
    gzip_native = catalog.languages[language].runtime.compressed_source
    data = _bounded_read(
        path,
        timeout,
        timeout_flag=timeout_flag,
        max_bytes=_MAX_GZIP_NATIVE_PROGRAM_BYTES if gzip_native else _MAX_PROGRAM_BYTES,
    )

    def decode() -> ProgramArtifact[Program]:
        return _check_program(
            language,
            _FileSource(path, data),
            normalize=True,
            settings=settings,
            catalog=catalog,
        )

    try:
        if timeout is None:
            return decode()
        remaining = timeout - (monotonic() - started)
        bound = f" ({timeout_flag})" if timeout_flag else ""

        def on_timeout() -> None:
            _fail(f"gave up decoding {path} after {timeout:g}s{bound}", _TIMEOUT_EXIT)

        if remaining <= 0:
            on_timeout()
        return _slurp_thread(decode, remaining, on_timeout=on_timeout)
    except EsolangError as exc:
        _fail(exc)
        raise  # pragma: no cover - _fail exits


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    _diagnostic(f"{message}\n")


def _slurp_thread[SlurpT](
    work: Callable[[], SlurpT],
    timeout: float | None,
    *,
    notice: AbstractContextManager[None] | None = None,
    on_timeout: Callable[[], None],
) -> SlurpT:
    """Run ``work`` on a daemon thread, abandoning it after ``timeout``.

    ``notice`` wraps the join when the wait deserves announcing; a slow
    thread is left to ``on_timeout`` (which exits).  An exception raised
    by ``work`` is re-raised on the caller's thread.
    """
    box: list[SlurpT | BaseException] = []

    def _slurp() -> None:
        try:
            box.append(work())
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=copy_context().run, args=(_slurp,), daemon=True)
    reader.start()
    if notice is None:
        reader.join(timeout)
    else:
        with notice:
            reader.join(timeout)
    if reader.is_alive():
        on_timeout()
    # A finished thread always appended; a live one exited above.
    result = box[0]
    if isinstance(result, StreamReadTimeoutError):
        on_timeout()
    if isinstance(result, BaseException):
        raise result
    return result


def _bounded_read(
    path: str,
    timeout: float | None,
    *,
    timeout_flag: str = "",
    max_bytes: int = _MAX_PROGRAM_BYTES,
) -> bytes:
    """Open and read ``path`` with a size cap and a deadline."""
    waited = timeout if timeout is not None else _READ_DEADLINE
    deadline = monotonic() + waited

    def _read_file() -> bytes:
        try:
            with open(path, "rb") as handle, stream_read_deadline(deadline):
                return read_snapshot(handle, size=max_bytes + 1)
        except StreamReadTimeoutError:
            raise
        except OSError as exc:
            _fail(f"cannot read {path}: {exc}")

    def _on_timeout() -> None:
        bound = f" ({timeout_flag})" if timeout_flag else ""
        _fail(
            f"gave up reading {path} after {waited:g}s{bound} -- it is not "
            f"delivering data (a FIFO with no writer, or a device)",
            _TIMEOUT_EXIT,
        )

    result = _slurp_thread(_read_file, waited, on_timeout=_on_timeout)
    if len(result) > max_bytes:
        _fail(f"{path} is larger than the {max_bytes // 1024} KiB program file limit")
    return result


def _smuggled_bytes(text: str) -> UnicodeDecodeError | None:
    """Return the decode error ``surrogateescape`` hid in *text*, if any.

    Under UTF-8 mode (a ``C`` locale, as on CI) stdin decodes with
    ``surrogateescape``, so binary arrives as lone surrogates.  Encoding
    them back and decoding strictly gives the same message, exit code and
    byte offset strict mode already had.
    """
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        pass
    else:
        return None
    encoding = getattr(sys.stdin, "encoding", None) or "utf-8"
    try:
        text.encode(encoding, "surrogateescape").decode(encoding)
    except UnicodeDecodeError as exc:
        return exc
    except (UnicodeEncodeError, LookupError):
        # A surrogate outside the escape range, so not a byte this stream
        # smuggled in; leave it to the reader that asked for the text.
        return None
    return None


def _read_pipe_without_poll(
    stream: BufferedReader, fd: int, deadline: float | None
) -> bytes:
    """Drain an anonymous pipe where poll is unavailable, including Windows."""
    blocking = os.get_blocking(fd)
    data = bytearray()
    while True:
        remaining = _time_remaining(deadline)
        if blocking:
            os.set_blocking(fd, False)
        try:
            chunk: bytes | None = stream.read(_BLOCK)
        except BlockingIOError:
            chunk = None
        finally:
            if blocking:
                os.set_blocking(fd, True)
        if chunk is None:
            # Restore the caller's mode before waiting for more data.
            sleep(0.01 if remaining is None else min(0.01, remaining))
        elif not chunk:
            return bytes(data)
        else:
            data.extend(chunk)


def _read_buffered_stdin(stream: BufferedReader, deadline: float | None) -> bytes:
    """Drain buffered bytes without holding the stdin lock across a pipe wait."""
    raw = stream.raw
    if not isinstance(raw, FileIO):
        return read_snapshot(stream)
    fd = raw.fileno()
    mode = os.fstat(fd).st_mode
    if stat.S_ISREG(mode):
        return read_snapshot(stream)
    if not hasattr(select, "poll"):
        if stat.S_ISFIFO(mode):
            return _read_pipe_without_poll(stream, fd, deadline)
        return read_snapshot(raw)
    if not os.get_blocking(fd):
        return read_snapshot(stream)
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    data = bytearray()
    while True:
        remaining = _time_remaining(deadline)
        timeout = None if remaining is None else min(ceil(remaining * 1000), 2**31 - 1)
        if poller.poll(timeout):
            # read1 consumes buffered bytes or performs at most one ready read.
            chunk = stream.read1(_BLOCK)
            if not chunk:
                return bytes(data)
            data.extend(chunk)


def _read_stdin(
    timeout: float | None = None, hint: str = "", *, timeout_flag: str = ""
) -> str:
    """Return this command's stdin, or exit if it is not text or never comes.

    ``sys.stdin.read()`` blocks until EOF, so an open, unwritten pipe hung
    the command before ``--execution-timeout`` could apply.  The read runs on a
    daemon thread to bound blocking reads and announce a long wait.
    """
    # A missing descriptor or terminal supplies no piped input.
    stdin = sys.stdin
    if stdin is None or stdin.isatty():
        return ""
    deadline = None if timeout is None else monotonic() + timeout

    def _read_text() -> str:
        stream = cast("BinaryIO | None", getattr(stdin, "buffer", None))
        try:
            with stream_read_deadline(deadline):
                if isinstance(stream, BufferedReader):
                    return _read_buffered_stdin(stream, deadline).decode("utf-8")
                if stream is not None:
                    return read_snapshot(stream).decode("utf-8")
                return read_snapshot(stdin)
        except StreamReadTimeoutError:
            raise
        except UnicodeDecodeError as exc:
            _fail(f"cannot read stdin: not text ({_decode_note(exc)})")
        except OSError as exc:
            _fail(f"cannot read stdin: {exc}")

    def _on_timeout() -> None:
        bound = f" ({timeout_flag})" if timeout_flag else ""
        _fail(
            f"stdin did not reach EOF within {timeout:g}s{bound}{hint}",
            _TIMEOUT_EXIT,
        )

    result = _slurp_thread(
        _read_text, timeout, notice=_waiting_notice(hint), on_timeout=_on_timeout
    )
    if (hidden := _smuggled_bytes(result)) is not None:
        _fail(f"cannot read stdin: not text ({_decode_note(hidden)})")
    return result


class _StdoutError(Exception):
    """A write or flush failed at the output destination."""

    def __init__(self, error: OSError) -> None:
        """Retain the cause for the closed-pipe policy."""
        self.error = error
        super().__init__(str(error))


class _StdoutEncodingError(Exception):
    """Output text cannot be written as UTF-8."""


def _write_output(data: str | bytes, *, utf8: bool = True) -> None:
    """Write data to stdout and distinguish destination errors from faults."""
    stream = getattr(sys.stdout, "buffer", None)
    if (
        isinstance(data, str)
        and utf8
        and stream is not None
        and not sys.stdout.isatty()
    ):
        try:
            data = data.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _StdoutEncodingError(
                f"output contains a surrogate at character {exc.start} "
                "and cannot be encoded as UTF-8"
            ) from exc
    try:
        if isinstance(data, bytes):
            sys.stdout.buffer.write(data)
        else:
            try:
                sys.stdout.write(data)
            except UnicodeEncodeError:
                encoding = sys.stdout.encoding or "utf-8"
                sys.stdout.write(
                    data.encode(encoding, "backslashreplace").decode(encoding)
                )
    except OSError as exc:
        raise _StdoutError(exc) from exc


def _flush_stdout() -> None:
    """Flush buffered output while the CLI can report a destination error."""
    try:
        sys.stdout.flush()
    except OSError as exc:
        raise _StdoutError(exc) from exc


def _emit_partial(exc: EsolangError) -> None:
    """Write whatever the program printed before ``exc`` to stdout.

    A program printing ``Hi`` then underflowing gave empty stdout
    where ``debug`` showed ``output: 'Hi'``.  On stdout so a pipe sees the
    same prefix either way.
    """
    if not exc.partial_output:
        return
    try:
        _write_output(exc.partial_output)
    except _StdoutEncodingError as error:
        _note(f"note: omitted partial output. {error}")
        return
    # Terminal only, as on success: a pipe got "\x01\n" for "\x01", and a
    # --max-output 3 cap 4 bytes.
    if not exc.partial_output.endswith("\n") and sys.stdout.isatty():
        _write_output("\n")
    _flush_stdout()
