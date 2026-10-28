"""Reading a program and stdin under a bound, and writing the answer out.

Both can block forever (a fifo, a pipe nobody writes to), so every read
carries a size and a deadline, and two notices say why nothing happened.
"""

from __future__ import annotations

import codecs
import sys
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager

from esolangs import _read_source
from esolangs.cli.args import _fail
from esolangs.cli.hints import _TIMEOUT_EXIT, _decode_note
from esolangs.exceptions import EsolangError
from esolangs.runtime._program import Program
from esolangs.runtime._source import _FileSource

#: How long a blocking stdin read waits before it says that it is waiting.
#: Shorter than the run notice: a read that has not finished is far more
#: likely to be a mistake than a program that is still going.
_WAITING_NOTICE_AFTER = 3.0


#: The most a program file may hold.  Two orders of magnitude above the
#: largest program any generator here produces.
_MAX_PROGRAM_BYTES = 1024 * 1024


#: How long to wait for a program file that is not delivering, when no
#: ``--timeout`` was given to bound it instead.
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
        self._timer = threading.Timer(after, sys.stderr.write, args=(message,))
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
        f"`esolangs {command} --timeout SECONDS` stops one\n",
    )


def _waiting_notice(hint: str = "") -> _DelayedNotice:
    """Notice for stdin still not delivering after a while."""
    return _DelayedNotice(
        _WAITING_NOTICE_AFTER,
        f"still waiting for input on stdin after {_WAITING_NOTICE_AFTER:.0f}s; "
        f"nothing has closed it{hint}\n",
    )


def _read_program(path: str, timeout: float | None = None, *, language: str) -> Program:
    """Read bounded source, refusing a non-text or oversized file."""
    try:
        return _read_source(language, _FileSource(path, _bounded_read(path, timeout)))
    except EsolangError as exc:
        _fail(exc)
        raise  # pragma: no cover - _fail exits


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    sys.stderr.write(f"{message}\n")


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

    reader = threading.Thread(target=_slurp, daemon=True)
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
    if isinstance(result, BaseException):
        raise result
    return result


def _bounded_read(path: str, timeout: float | None) -> bytes:
    """Open and read ``path``, with a size cap and a deadline.

    Only acquisition runs on the daemon thread; interpreter decoding follows
    on the caller's thread. The cap applies before any decoding.
    """
    waited = timeout if timeout is not None else _READ_DEADLINE

    def _read_file() -> bytes:
        try:
            with open(path, "rb") as handle:
                return handle.read(_MAX_PROGRAM_BYTES + 1)
        except OSError as exc:
            _fail(f"cannot read {path}: {exc}")

    def _on_timeout() -> None:
        _fail(
            f"gave up reading {path} after {waited:g}s -- it is not "
            f"delivering data (a FIFO with no writer, or a device)",
            _TIMEOUT_EXIT,
        )

    result = _slurp_thread(_read_file, waited, on_timeout=_on_timeout)
    if len(result) > _MAX_PROGRAM_BYTES:
        _fail(
            f"{path} is larger than the {_MAX_PROGRAM_BYTES // 1024} KiB this "
            f"reads; the largest program this package generates is far under "
            f"it, so this is almost certainly not a program"
        )
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


def _read_stdin(timeout: float | None = None, hint: str = "") -> str:
    """Return this command's stdin, or exit if it is not text or never comes.

    ``sys.stdin.read()`` blocks until EOF, so an open, unwritten pipe hung
    the command before ``--timeout`` could apply.  The read runs on a
    daemon thread bounded by ``--timeout``, announced if still waiting; a
    thread rather than :func:`select.select` because tests supply an
    object with no ``fileno``.
    """
    # None: fd 0 was closed at startup (``<&-``), an internal error, exit 70.
    if sys.stdin is None or sys.stdin.isatty():
        return ""

    def _read_text() -> str:
        try:
            return sys.stdin.read()
        except UnicodeDecodeError as exc:
            _fail(f"cannot read stdin: not text ({_decode_note(exc)})")

    def _on_timeout() -> None:
        _fail(
            f"no input arrived on stdin within {timeout:g}s, and nothing "
            f"closed it{hint}",
            _TIMEOUT_EXIT,
        )

    result = _slurp_thread(
        _read_text, timeout, notice=_waiting_notice(hint), on_timeout=_on_timeout
    )
    hidden = _smuggled_bytes(result)
    if hidden is not None:
        _fail(f"cannot read stdin: not text ({_decode_note(hidden)})")
    return result


def _write_output(text: str) -> None:
    """Write program output to stdout, whatever bytes it turned out to be.

    A program can print a lone surrogate (a print command emits the
    accumulator as an unbounded character), which made ``sys.stdout.write``
    raise a nineteen-line traceback.  When the text stream refuses, write
    through the byte stream with ``surrogatepass``, keeping ``run --help``'s
    verbatim promise; a stream with no ``buffer`` gets an escaped form.  A
    stream that cannot encode a character at all (an ASCII locale) gets it
    backslash-escaped, since ``surrogatepass`` raised again there (exit 70).
    """
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        # A text-only stream (an in-process StringIO) takes any str verbatim.
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:
            sys.stdout.write(text.encode("utf-8", "backslashreplace").decode("utf-8"))
        return
    encoding = sys.stdout.encoding or "utf-8"
    try:
        text.encode(encoding)  # Strict: ``main`` made the stream itself lenient.
    except UnicodeEncodeError:
        utf8 = codecs.lookup(encoding).name == "utf-8"
        sys.stdout.flush()
        stream.write(
            text.encode(encoding, "surrogatepass" if utf8 else "backslashreplace")
        )
        stream.flush()
        return
    sys.stdout.write(text)


def _emit_partial(exc: EsolangError) -> None:
    """Write whatever the program printed before ``exc`` to stdout.

    A program printing ``Hi`` then underflowing gave empty stdout
    where ``debug`` showed ``output: 'Hi'``.  On stdout so a pipe sees the
    same prefix either way.
    """
    if not exc.partial_output:
        return
    _write_output(exc.partial_output)
    # Terminal only, as on success: a pipe got "\x01\n" for "\x01", and a
    # --max-output 3 cap 4 bytes.
    if not exc.partial_output.endswith("\n") and sys.stdout.isatty():
        sys.stdout.write("\n")
    sys.stdout.flush()
