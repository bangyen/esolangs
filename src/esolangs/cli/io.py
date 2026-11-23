"""Reading a program and stdin under a bound, and writing the answer out.

Input can block forever on a FIFO or pipe. Deadlines and notices say why
nothing happened, and program files are read within a byte bound.
"""

from __future__ import annotations

import os
import select
import stat
import sys
import threading
from codecs import IncrementalEncoder, lookup
from collections.abc import Buffer, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext, suppress
from contextvars import ContextVar, copy_context
from dataclasses import replace
from encodings.utf_8 import IncrementalDecoder as UTF8Decoder
from encodings.utf_8_sig import IncrementalDecoder as UTF8SigDecoder
from errno import EAGAIN
from functools import partial
from gc import get_referents
from inspect import getattr_static
from io import (
    BufferedReader,
    FileIO,
    IncrementalNewlineDecoder,
    RawIOBase,
    TextIOWrapper,
    UnsupportedOperation,
)
from math import ceil
from time import monotonic, sleep
from typing import BinaryIO, NoReturn, TextIO, cast

from esolangs.artifacts import ProgramArtifact, TemplateArtifact
from esolangs.cli.hints import (
    _TIMEOUT_EXIT,
    _cli_error_text,
    _display_encoding,
    _exit_code,
    _timeout_text,
)
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionBudgetError,
    ProgramError,
    TemplateError,
)
from esolangs.operations.source import _check_program
from esolangs.registry import Catalog, get_catalog
from esolangs.runtime._files import (
    _BLOCK,
    StreamReadTimeoutError,
    _binary_chunk,
    _binary_snapshot,
    _SourceDirectory,
    _time_remaining,
    decode_utf8,
    explicit_path,
    read_snapshot,
    stream_read_deadline,
)
from esolangs.runtime._input import (
    _bind_input_reader,
    _unreadable_input,
    input_read_error,
    read_input,
)
from esolangs.runtime._program import Program
from esolangs.runtime._source import _FileSource, _open_program_path
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime._wait import wait_slice
from esolangs.runtime.source_hints import display_label, source_read_error
from esolangs.settings import (
    DialectSettings,
    _check_dialect_conflicts,
    _merge_settings,
    dialect_options,
)

#: How long a blocking stdin read waits before it says that it is waiting.
#: Shorter than the run notice: a read that has not finished is far more
#: likely to be a mistake than a program that is still going.
_WAITING_NOTICE_AFTER = 3.0


#: Cap source streams without a known file size, including endless devices.
_MAX_PROGRAM_BYTES = 1024 * 1024
#: A gzip-native runtime allows a larger source stream for its raw export.
_MAX_GZIP_NATIVE_PROGRAM_BYTES = 32 * _MAX_PROGRAM_BYTES


#: Fallback deadline for reading a program file.
_READ_DEADLINE = 10.0


#: How long an unbounded run goes before it says that it is unbounded.
#: A constant so a test can shorten it rather than wait.
_UNBOUNDED_NOTICE_AFTER = 10.0

# Keep tabs and newlines for layout. Escape the other C0 and C1 controls.
_DIAGNOSTIC_ESCAPES = {
    point: display_label(chr(point))
    for point in (*range(9), *range(11, 32), *range(127, 160))
}


class _DelayedNotice:
    """Print one line if the wrapped wait is still going after a while.

    The timer fires once and is cancelled when the wait finishes,
    whether it finished or raised.
    """

    def __init__(self, after: float, message: str) -> None:
        """Arm the notice to write ``message`` after ``after`` seconds."""
        self._timer = threading.Timer(
            after, _diagnostic, args=(message,), kwargs={"ready_only": True}
        )
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


def _read_program(
    path: str,
    timeout: float | None = None,
    *,
    language: str,
    timeout_flag: str = "",
    directory: _SourceDirectory | None = None,
    settings: DialectSettings | None = None,
    catalog: Catalog | None = None,
    _settings_validated: bool = False,
    portable: bool = False,
    bits: str | None = None,
) -> ProgramArtifact[Program]:
    """Read native source or a portable record under the acquisition deadline."""
    deadline = None if timeout is None else monotonic() + timeout
    catalog = get_catalog(catalog)
    gzip_native = catalog.languages[language].runtime.compressed_source
    label = "stdin" if path == "-" else display_label(path)
    max_bytes = _MAX_GZIP_NATIVE_PROGRAM_BYTES if gzip_native else _MAX_PROGRAM_BYTES
    if path == "-":
        data = _bounded_source_stdin(timeout, timeout_flag, deadline, max_bytes)
    else:
        data = _bounded_read(
            path,
            timeout,
            timeout_flag=timeout_flag,
            directory=directory,
            deadline=deadline,
            max_bytes=max_bytes,
        )

    def decode() -> ProgramArtifact[Program]:
        with nullcontext() if deadline is None else stream_read_deadline(deadline):
            if portable:
                return _load_portable_source(
                    language, label, data, settings, catalog, bits
                )
            return _check_program(
                language,
                _FileSource(label, data),
                normalize=True,
                settings=settings,
                catalog=catalog,
                _settings_validated=_settings_validated,
            )

    try:
        if deadline is None:
            return decode()
        remaining = deadline - monotonic()
        bound = f" ({timeout_flag})" if timeout_flag else ""

        def on_timeout() -> NoReturn:
            _fail(f"gave up decoding {label} after {timeout:g}s{bound}", _TIMEOUT_EXIT)

        if remaining <= 0:
            on_timeout()
        return _slurp_thread(decode, deadline, on_timeout=on_timeout)
    except ExecutionBudgetError as exc:
        _fail(_timeout_text(exc), _TIMEOUT_EXIT)
    except EsolangError as exc:
        _fail(exc)


def _load_portable_source(
    language: str,
    label: str,
    data: bytes,
    settings: DialectSettings | None,
    catalog: Catalog,
    bits: str | None,
) -> ProgramArtifact[Program]:
    """Restore runnable JSON and combine any explicit compatible choices."""
    from esolangs import from_json

    try:
        document = decode_utf8(data)
    except UnicodeDecodeError as error:
        raise source_read_error(label, error) from error
    artifact = from_json(language, document, catalog=catalog)
    if isinstance(artifact, TemplateArtifact):
        if bits is None:
            raise TemplateError(
                "unfilled portable template; pass --bits to esolangs run --artifact"
            )
        artifact = artifact.fill([int(bit) for bit in bits])
    elif bits is not None:
        raise ArgumentError("--bits requires an unfilled portable template")
    retained = artifact.settings
    if settings is not None and retained is not None:
        _check_dialect_conflicts(retained, settings)
    merged = _merge_settings(language, retained, settings, catalog=catalog)
    dialect_options(
        language,
        merged,
        catalog=catalog,
        validate_defaults=True,
        _sparse_validated=True,
    )
    return artifact if merged is retained else replace(artifact, settings=merged)


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    _diagnostic(f"{message}\n")


def _slurp_thread[SlurpT](
    work: Callable[[], SlurpT],
    deadline: float | None,
    *,
    stdin_hint: str | None = None,
    on_timeout: Callable[[], NoReturn],
) -> SlurpT:
    """Accept a reader's result or exception only before the deadline.

    An expired reader may still be running, so only the caller reports its
    outcome. Stdin notices run on the caller thread so shutdown cannot race
    a daemon holding the buffered stderr lock.
    """
    box: list[SlurpT | BaseException] = []

    def _slurp() -> None:
        try:
            box.append(work())
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=copy_context().run, args=(_slurp,), daemon=True)
    try:
        reader.start()
    except RuntimeError as exc:
        # SIGINT during CPython's startup condition release can raise
        # "release unlocked lock" while unwinding the original interrupt.
        if isinstance(exc.__context__, KeyboardInterrupt):
            raise exc.__context__ from None
        raise
    notice_at = None if stdin_hint is None else monotonic() + _WAITING_NOTICE_AFTER
    # Poll the join so Python can handle signals delivered to the reader.
    while reader.is_alive():
        now = monotonic()
        waited = wait_slice(deadline, now)
        if waited <= 0:
            break
        if notice_at is not None:
            if now >= notice_at:
                _diagnostic(
                    "still waiting for input on stdin after "
                    f"{_WAITING_NOTICE_AFTER:.0f}s; "
                    f"nothing has closed it{stdin_hint}\n",
                    ready_only=True,
                )
                notice_at = None
                continue
            waited = min(waited, notice_at - now)
        reader.join(waited)
    if reader.is_alive() or (deadline is not None and monotonic() >= deadline):
        on_timeout()
    # A finished thread always appended; a live one exited above.
    result = box[0]
    if deadline is not None and isinstance(result, StreamReadTimeoutError):
        on_timeout()
    if isinstance(result, BaseException):
        raise result
    return result


def _bounded_read(
    path: str,
    timeout: float | None,
    *,
    timeout_flag: str = "",
    directory: _SourceDirectory | None = None,
    deadline: float | None = None,
    max_bytes: int = _MAX_PROGRAM_BYTES,
) -> bytes:
    """Read up to the opening file size or the stream cap, under a deadline."""
    try:
        path = explicit_path(path).spelling
    except ArgumentError as error:
        _fail(error)
    label = display_label(path)
    waited = timeout if timeout is not None else _READ_DEADLINE
    if deadline is None:
        deadline = monotonic() + waited

    def _read_file() -> bytes:
        try:
            with (
                (
                    open(path, "rb")
                    if directory is None
                    else _open_program_path(directory.resolve(path), path)
                ) as handle,
                stream_read_deadline(deadline),
            ):
                _time_remaining(deadline)
                if isinstance(handle, BufferedReader):
                    fd = handle.fileno()
                    _time_remaining(deadline)
                    opened = os.fstat(fd)
                    # Pseudo-files can report a zero size and still yield data.
                    if stat.S_ISREG(opened.st_mode) and opened.st_size > 0:
                        _time_remaining(deadline)
                        size = max(0, opened.st_size - handle.tell())
                        return _binary_snapshot(
                            handle, None, size, deadline, handle.read1
                        )
                result = _binary_chunk(read_snapshot(handle, size=max_bytes + 1))
        except StreamReadTimeoutError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise source_read_error(label, exc) from exc
        if len(result) > max_bytes:
            raise ProgramError(
                f"{label} is larger than the {max_bytes // 1024} KiB program file limit"
            )
        return result

    def _on_timeout() -> NoReturn:
        bound = f" ({timeout_flag})" if timeout_flag else ""
        _fail(
            f"gave up reading {label} after {waited:g}s{bound} -- it is not "
            f"delivering data (a FIFO with no writer, or a device)",
            _TIMEOUT_EXIT,
        )

    try:
        return _slurp_thread(_read_file, deadline, on_timeout=_on_timeout)
    except ProgramError as exc:
        _fail(exc)


def _managed_stdin_text(text: str, stdin: TextIO) -> str:
    """Report raw bytes hidden by a managed text stream's surrogateescape."""
    if text.isascii():
        return text
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        pass
    else:
        return text
    encoding = getattr(stdin, "encoding", None) or "utf-8"
    # A surrogate outside the escape range can be explicit Python text.
    with suppress(UnicodeEncodeError, LookupError):
        text.encode(encoding, "surrogateescape").decode(encoding)
    return text


def _wait_for_pipe_data(deadline: float | None) -> None:
    remaining = _time_remaining(deadline)
    sleep(0.01 if remaining is None else min(0.01, remaining))


def _read_pipe_without_poll(
    stream: BufferedReader, fd: int, deadline: float | None, size: int | None
) -> bytes:
    """Drain an anonymous pipe where poll is unavailable, including Windows."""
    blocking = os.get_blocking(fd)
    data = bytearray()
    while size is None or len(data) < size:
        _time_remaining(deadline)
        width = _BLOCK if size is None else min(_BLOCK, size - len(data))
        if blocking:
            os.set_blocking(fd, False)
        try:
            chunk: bytes | None = stream.read(width)
        except BlockingIOError:
            chunk = None
        finally:
            if blocking:
                os.set_blocking(fd, True)
        if chunk is None:
            # Restore the caller's mode before waiting for more data.
            _wait_for_pipe_data(deadline)
            continue
        chunk = _binary_chunk(chunk)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _read_buffered_stdin(
    stream: BufferedReader, deadline: float | None, *, size: int | None = None
) -> bytes:
    """Drain buffered bytes without holding the stdin lock across a pipe wait."""
    _time_remaining(deadline)
    raw = stream.raw
    if not isinstance(raw, FileIO):
        return read_snapshot(stream, size=size)
    _time_remaining(deadline)
    fd = raw.fileno()
    _time_remaining(deadline)
    mode = os.fstat(fd).st_mode
    if stat.S_ISREG(mode):
        return read_snapshot(stream, size=size)
    if not hasattr(select, "poll"):
        if stat.S_ISFIFO(mode):
            return _read_pipe_without_poll(stream, fd, deadline, size)
        return read_snapshot(raw, size=size)
    if not os.get_blocking(fd):
        return read_snapshot(stream, size=size)
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    data = bytearray()
    while size is None or len(data) < size:
        remaining = _time_remaining(deadline)
        timeout = None if remaining is None else min(ceil(remaining * 1000), 2**31 - 1)
        if not poller.poll(timeout):
            continue
        _time_remaining(deadline)
        # read1 consumes buffered bytes or performs at most one ready read.
        width = _BLOCK if size is None else min(_BLOCK, size - len(data))
        try:
            chunk: bytes | None = stream.read1(width)
        except BlockingIOError:
            chunk = None
        if chunk is None:
            _wait_for_pipe_data(deadline)
            continue
        chunk = _binary_chunk(chunk)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _bounded_source_stdin(
    timeout: float | None, timeout_flag: str, deadline: float | None, max_bytes: int
) -> bytes:
    """Read native source bytes from stdin under the program stream bounds."""
    waited = _READ_DEADLINE if timeout is None else timeout
    if deadline is None:
        deadline = monotonic() + waited
    size = max_bytes + 1

    def read() -> bytes:
        stdin = sys.stdin
        if stdin is None:
            return b""
        with stream_read_deadline(deadline):
            _time_remaining(deadline)
            stream: BinaryIO | None = getattr(stdin, "buffer", None)
            if isinstance(stream, BufferedReader):
                return _read_buffered_stdin(stream, deadline, size=size)
            if stream is not None:
                return _binary_chunk(read_snapshot(stream, size=size))
            return read_snapshot(stdin, size=size).encode("utf-8")

    def on_timeout() -> NoReturn:
        bound = f" ({timeout_flag})" if timeout_flag else ""
        _fail(f"stdin did not reach EOF within {waited:g}s{bound}", _TIMEOUT_EXIT)

    try:
        source = _slurp_thread(read, deadline, on_timeout=on_timeout)
    except (OSError, TypeError, ValueError) as exc:
        _fail(source_read_error("stdin", exc))
    if len(source) > max_bytes:
        _fail(f"stdin is larger than the {max_bytes // 1024} KiB program stream limit")
    return source


@contextmanager
def _override_io_method(
    stream: object, name: str, replacement: Callable[..., object]
) -> Iterator[None]:
    """Restore the stream's own override, if any, when a borrowed method is done."""
    attributes = vars(stream)
    shadowed = name in attributes
    previous = attributes.get(name)
    attributes[name] = replacement
    try:
        yield
    finally:
        if shadowed:
            attributes[name] = previous
        else:
            del attributes[name]


def _read_stdin_bytes(stream: BinaryIO, deadline: float | None) -> bytes:
    value = (
        _read_buffered_stdin(stream, deadline)
        if isinstance(stream, BufferedReader)
        else read_snapshot(stream)
    )
    return _binary_chunk(value)


def _prefetched_utf8_parts(stdin: TextIOWrapper, data: bytes) -> tuple[int, bytes]:
    """Return bytes to feed the text decoder and any malformed pending prefix."""
    # TextIOWrapper exposes no decoder attribute. CPython's GC traversal
    # exposes it after any subclass members. getstate leaves text untouched.
    # Only feed bytes needed to finish a scalar through a lossy error handler.
    for decoder in reversed(get_referents(stdin)):
        if isinstance(
            decoder, (IncrementalNewlineDecoder, UTF8Decoder, UTF8SigDecoder)
        ):
            pending, flags = decoder.getstate()
            if not pending:
                return 0, b""
            width = 2 + (pending[0] >= 0xE0) + (pending[0] >= 0xF0)
            needed = width - len(pending)
            try:
                (pending + data[:needed]).decode("utf-8")
            except UnicodeDecodeError:
                # Drain the already decoded text before reporting the byte offset.
                decoder.setstate((b"", flags))
                return 0, pending
            return needed, b""
    split = 0
    while split < min(3, len(data)) and 0x80 <= data[split] < 0xC0:
        split += 1
    return split, b""


def _read_prefetched_stdin(stdin: TextIOWrapper, stream: BinaryIO, data: bytes) -> str:
    """Drain existing text state and preserve the still-unprocessed byte tail."""
    codec = lookup(stdin.encoding)
    if codec.name == "utf-8-sig":
        codec = lookup("utf-8")  # The active decoder has consumed the signature.
    split = len(data)
    pending = b""
    if codec.name == "utf-8":
        split, pending = _prefetched_utf8_parts(stdin, data)
    elif codec.name in {"ascii", "iso8859-1"}:
        split = 0  # A single-byte decoder cannot have a pending code point.
    if not pending and data[split : split + 1] == b"\n":
        split += 1  # The newline decoder may still hold the matching CR.
    with _override_io_method(stream, "read", lambda: data[:split]):
        text = TextIOWrapper.read(stdin)

    # An encoder with a starting state may insert bytes absent from the tail.
    make_encoder = cast(
        "Callable[[str], IncrementalEncoder] | None", codec.incrementalencoder
    )
    if make_encoder is None:
        return _managed_stdin_text(text, stdin)
    encoder = make_encoder("surrogateescape")
    if encoder.getstate():
        return _managed_stdin_text(text, stdin)
    try:
        restored = encoder.encode(text, final=True)
    except UnicodeEncodeError:
        return _managed_stdin_text(text + decode_utf8(pending + data[split:]), stdin)
    return decode_utf8(restored + pending + data[split:])


def _read_wrapped_stdin(
    stdin: TextIOWrapper, stream: BinaryIO, deadline: float | None
) -> str:
    try:
        # Setting the same error handler distinguishes a fresh wrapper from
        # one whose decoder may already hold characters or a split code unit.
        TextIOWrapper.reconfigure(stdin, errors=stdin.errors)
    except UnsupportedOperation:
        # Finish waiting outside the text wrapper, then let it decode the
        # suffix with its current state while no further I/O can block.
        data = _read_stdin_bytes(stream, deadline)
        return _read_prefetched_stdin(stdin, stream, data)
    return decode_utf8(_read_stdin_bytes(stream, deadline))


def _custom_text_reader(stdin: TextIOWrapper) -> bool:
    """Whether the caller supplies how a text wrapper reads."""
    return (
        getattr_static(type(stdin), "__getattribute__")
        is not TextIOWrapper.__getattribute__
        or getattr_static(stdin, "read", None) is not TextIOWrapper.read
    )


def _snapshot_stdin(stdin: TextIO, deadline: float | None) -> str:
    _time_remaining(deadline)
    with stream_read_deadline(deadline):
        if _has_backing_type(stdin, TextIOWrapper):
            if _custom_text_reader(stdin):
                # Bypassing this reader can lose text it already decoded.
                return _managed_stdin_text(read_input(stdin), stdin)
        else:
            checked = _bind_input_reader(stdin)
            _time_remaining(deadline)
            if checked is not None:
                return _managed_stdin_text(read_input(checked), stdin)
        stream = cast("BinaryIO | None", getattr(stdin, "buffer", None))
        _time_remaining(deadline)
        if stream is None:
            raise _unreadable_input(stdin)
        if _has_backing_type(stdin, TextIOWrapper) and hasattr(stream, "__dict__"):
            return _read_wrapped_stdin(stdin, stream, deadline)
        return decode_utf8(_read_stdin_bytes(stream, deadline))


def _is_terminal(stream: object) -> bool:
    """Treat missing or unavailable terminal probes as nonterminal streams."""
    try:
        isatty = getattr(stream, "isatty", None)
        return callable(isatty) and bool(isatty())
    except OSError:
        return False


def _probe_stdin(stream: object, deadline: float | None) -> bool | None:
    """Return the terminal state, or None for a closed stream."""
    _time_remaining(deadline)
    closed = getattr(stream, "closed", False)
    _time_remaining(deadline)
    if closed:
        return None
    terminal = _is_terminal(stream)
    _time_remaining(deadline)
    return terminal


def _read_stdin(
    timeout: float | None = None,
    hint: str = "",
    *,
    timeout_flag: str = "",
    terminal_prompt: str | None = None,
) -> str:
    """Return this command's stdin, or exit if it is not text or never comes.

    Piped reads run on a daemon thread to apply deadlines and announce
    long waits. A terminal prompt opts into interactive input.
    """
    stdin = sys.stdin
    if stdin is None:
        return ""
    deadline = None if timeout is None else monotonic() + timeout

    def _read_text() -> str:
        return _snapshot_stdin(stdin, deadline)

    def _on_timeout() -> NoReturn:
        bound = f" ({timeout_flag})" if timeout_flag else ""
        _fail(
            f"stdin did not reach EOF within {timeout:g}s{bound}{hint}",
            _TIMEOUT_EXIT,
        )

    def _read_probed(*, terminal: bool | None) -> str:
        if terminal is None or (terminal and terminal_prompt is None):
            return ""
        if terminal and terminal_prompt is not None:
            _note(terminal_prompt)
        return _read_text()

    # An interactive read has no deadline. Keeping it on the main thread
    # lets Ctrl-C interrupt it without leaving a reader holding stdin's lock.
    try:
        terminal = _probe_stdin(stdin, None) if deadline is None else None
        if deadline is None and terminal is not False:
            return _read_probed(terminal=terminal)
        # A managed adapter's terminal probes can block just like its read.
        read = (
            _read_text
            if deadline is None
            else lambda: _read_probed(terminal=_probe_stdin(stdin, deadline))
        )
        return _slurp_thread(read, deadline, stdin_hint=hint, on_timeout=_on_timeout)
    except UnicodeDecodeError as exc:
        _fail(input_read_error(exc))
    except ExecutionBudgetError as exc:
        _fail(_timeout_text(exc), _TIMEOUT_EXIT)
    except ArgumentError as exc:
        if deadline is not None and isinstance(exc.__cause__, StreamReadTimeoutError):
            _on_timeout()
        _fail(exc)
    except EsolangError as exc:
        _fail(exc, _exit_code(exc))
    except (OSError, TypeError, ValueError) as exc:
        _fail(input_read_error(exc))


class _StdoutError(Exception):
    """A write or flush failed at the output destination."""

    def __init__(self, error: OSError | ValueError) -> None:
        """Retain the cause for the closed-pipe policy."""
        self.error = error
        super().__init__(str(error))


class _StdoutEncodingError(Exception):
    """Output text cannot be written as UTF-8."""

    def __init__(self, error: UnicodeEncodeError, *, kept_prefix: bool = False) -> None:
        super().__init__(
            f"output contains a surrogate at character {error.start} "
            "and cannot be encoded as UTF-8"
        )
        self.kept_prefix = kept_prefix


def _write_all[DataT: (str, bytes, memoryview)](
    write: Callable[[DataT], int | None],
    data: DataT,
    *,
    before_write: Callable[[], None] | None = None,
) -> int:
    """Finish positive short writes and refuse a destination that stops accepting."""
    total = len(data)
    offset = 0
    while offset < total:
        if before_write is not None:
            before_write()
        written = write(data[offset:])
        if not written:
            raise BlockingIOError(
                EAGAIN, "write could not complete without blocking", offset
            )
        if written < 0 or written > total - offset:
            raise OSError("write returned an invalid count")
        offset += written
    return total


@contextmanager
def _complete_raw_writes(
    stream: TextIO, *, before_write: Callable[[], None] | None = None
) -> Iterator[None]:
    """Check unbuffered writes without changing the stream's text encoder."""
    raw = getattr(stream, "buffer", None)
    if not isinstance(raw, RawIOBase):
        yield
        return
    write = raw.write

    def complete(data: Buffer) -> int:
        return _write_all(write, memoryview(data).cast("B"), before_write=before_write)

    # TextIOWrapper discards the raw write count. Guard the existing stream
    # rather than replacing the wrapper and losing its encoder state.
    with _override_io_method(raw, "write", complete):
        yield


def _complete_stdout_writes() -> AbstractContextManager[None]:
    return _complete_raw_writes(sys.stdout)


_READY_ONLY: ContextVar[bool] = ContextVar("diagnostic_ready_only", default=False)


class _DiagnosticUnavailableError(Exception):
    """An optional diagnostic would wait on a busy destination."""


def _abandon_output(stream: TextIO | None) -> None:
    """Keep Python's shutdown flush from retrying the failed destination."""
    if stream is None:
        return
    with suppress(AttributeError, OSError, ValueError), open(os.devnull, "wb") as sink:
        os.dup2(sink.fileno(), stream.fileno())


def _output_ready(stream: TextIO) -> bool:
    """Check whether an optional notice can write without waiting on a pipe."""
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return True  # Caller-provided streams such as StringIO have no descriptor.
    try:
        if hasattr(select, "poll"):
            poller = select.poll()
            poller.register(fd, select.POLLOUT)
            return bool(poller.poll(0))
        # On platforms without poll, pipe readiness cannot be checked here.
        return not stat.S_ISFIFO(os.fstat(fd).st_mode)
    except (OSError, ValueError):
        return False


def _check_diagnostic_ready(stream: TextIO) -> None:
    if _READY_ONLY.get() and not _output_ready(stream):
        raise _DiagnosticUnavailableError


def _complete_stderr_writes() -> AbstractContextManager[None]:
    stream = sys.stderr
    if _output_unavailable(stream):
        return nullcontext()
    return _complete_raw_writes(
        stream, before_write=partial(_check_diagnostic_ready, stream)
    )


def _diagnostic(message: str, *, ready_only: bool = False) -> None:
    """Write to stderr without changing the command's outcome if it fails."""
    stream = sys.stderr
    if stream is None:
        return
    check_ready = partial(_check_diagnostic_ready, stream)

    def write(data: str) -> int:
        try:
            return stream.write(data)
        except UnicodeEncodeError:
            # A caller-supplied text adapter may lack reconfigure().
            escaped = data.encode("ascii", "backslashreplace").decode("ascii")
            _write_all(stream.write, escaped, before_write=check_ready)
            return len(data)

    token = _READY_ONLY.set(ready_only)
    try:
        _write_all(
            write, message.translate(_DIAGNOSTIC_ESCAPES), before_write=check_ready
        )
        check_ready()
        stream.flush()
    except KeyboardInterrupt:
        # An interrupted notice must leave stderr available to report SIGINT.
        if not ready_only:
            _abandon_output(stream)
        raise
    except OSError:
        _abandon_output(stream)
    except (_DiagnosticUnavailableError, ValueError):
        pass
    finally:
        _READY_ONLY.reset(token)


def _fail(message: str | BaseException, code: int = 2) -> NoReturn:
    if isinstance(message, BaseException):
        message = _cli_error_text(message)
    _diagnostic(message + "\n")
    sys.exit(code)


def _output_unavailable(stream: TextIO | None) -> bool:
    """Check closure without asking a detached wrapper for its closed flag."""
    if stream is None:
        return True
    if _has_backing_type(stream, TextIOWrapper):
        try:
            if getattr_static(TextIOWrapper, "buffer").__get__(stream) is None:
                return True
        except ValueError:
            return True
    return bool(getattr(stream, "closed", False))


@contextmanager
def _stdout_destination() -> Iterator[TextIO]:
    """Classify failures at the output destination."""
    stream = sys.stdout
    try:
        if _output_unavailable(stream):
            raise OSError("stdout is closed")
        yield stream
    except KeyboardInterrupt:
        _abandon_output(stream)
        raise
    except OSError as exc:
        raise _StdoutError(exc) from exc
    except ValueError as exc:
        if not _output_unavailable(stream):
            raise
        raise _StdoutError(exc) from exc


def _stdout_is_terminal() -> bool:
    """Check stdout under the same closure policy as writes and flushing."""
    with _stdout_destination() as stdout:
        return _is_terminal(stdout)


def _write_text(stream: TextIO, data: str) -> int:
    """Write one text segment, escaping characters outside the stream's encoding."""
    try:
        return stream.write(data)
    except UnicodeEncodeError:
        encoding = _display_encoding(stream)
        _write_all(
            stream.write, data.encode(encoding, "backslashreplace").decode(encoding)
        )
        return len(data)


def _write_output(
    data: str | bytes, *, utf8: bool = True, keep_encodable_prefix: bool = False
) -> None:
    """Write data to stdout and distinguish destination errors from faults."""
    with _stdout_destination() as stdout:
        stream = getattr(stdout, "buffer", None)
        if (
            isinstance(data, str)
            and utf8
            and stream is not None
            and not _is_terminal(stdout)
        ):
            try:
                data = data.encode("utf-8")
            except UnicodeEncodeError as exc:
                kept_prefix = keep_encodable_prefix and exc.start > 0
                if kept_prefix:
                    _write_all(stream.write, exc.object[: exc.start].encode("utf-8"))
                raise _StdoutEncodingError(exc, kept_prefix=kept_prefix) from exc
        if isinstance(data, bytes):
            if stream is None:
                raise OSError("binary output requires a binary stdout stream")
            _write_all(stream.write, data)
        else:
            _write_all(partial(_write_text, stdout), data)


def _flush_stdout() -> None:
    """Flush buffered output while the CLI can report a destination error."""
    with _stdout_destination() as stdout:
        stdout.flush()


def _emit_partial(output: str) -> None:
    """Write the current invocation's output before reporting its failure.

    A program printing ``Hi`` then underflowing gave empty stdout
    where ``debug`` showed ``output: 'Hi'``.  On stdout so a pipe sees the
    same prefix either way.
    """
    if not output:
        return
    try:
        _write_output(output, keep_encodable_prefix=True)
    except _StdoutEncodingError as error:
        if error.kept_prefix:
            _flush_stdout()
        omitted = (
            "the rest of partial output" if error.kept_prefix else "partial output"
        )
        _note(f"note: omitted {omitted}. {error}")
        return
    # Terminal only, as on success: a pipe got "\x01\n" for "\x01", and a
    # --max-output 3 cap 4 bytes.
    if not output.endswith("\n") and _stdout_is_terminal():
        _write_output("\n")
    _flush_stdout()
