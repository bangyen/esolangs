"""Reading a program and stdin under a bound, and writing the answer out.

Both can block forever (a fifo, a pipe nobody writes to), so every read
carries a size and a deadline, and two notices say why nothing happened.
"""

from __future__ import annotations

import sys
import threading
from contextlib import AbstractContextManager, nullcontext

from esolangs.cli_args import (
    _fail,
)
from esolangs.cli_hints import (
    _TIMEOUT_EXIT,
    _decode_note,
)
from esolangs.exceptions import EsolangError
from esolangs.raster import Raster

#: A program file that starts with the PNG signature is an image-language
#: program, decoded to a :class:`~esolangs.raster.Raster` rather than text.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _null_context() -> AbstractContextManager[None]:
    """Return a do-nothing ``with`` target, for an already-bounded run."""
    return nullcontext()


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


class _UnboundedNotice:
    """Print one line if an unbounded run is still going after a while.

    ``run`` and ``debug`` take no bound by default, but several languages
    loop forever by design; one reader killed a silent spin after eight
    CPU-minutes.  A timer fires once, names the flag, and is cancelled
    when the run finishes.
    """

    def __init__(self, command: str) -> None:
        """Arm the notice for ``command``, which names the flag to pass."""
        self._timer = threading.Timer(
            _UNBOUNDED_NOTICE_AFTER, self._say, args=(command,)
        )
        self._timer.daemon = True

    @staticmethod
    def _say(command: str) -> None:
        """Write the one line, from the timer thread."""
        sys.stderr.write(
            f"still running after {_UNBOUNDED_NOTICE_AFTER:.0f}s with no bound; "
            f"several of these languages loop forever by design -- "
            f"`esolangs {command} --timeout SECONDS` stops one\n"
        )

    def __enter__(self) -> _UnboundedNotice:
        """Start the timer."""
        self._timer.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        """Cancel it, whether the run finished or raised."""
        self._timer.cancel()


def _read_program(path: str, timeout: float | None = None) -> str | Raster:
    """Return the program in ``path``, or exit with a usage error.

    A raster language's program is a PNG, so the bytes are read and, when
    they carry the PNG signature, decoded here; otherwise they are UTF-8
    text.  One trailing newline is the text file's: CV(N)(C), Grapheme and
    NoComment reject one, and ``esolangs generate ... > prog.txt`` writes it.
    """
    # The *open* is on the thread as well as the read.  Opening a FIFO
    # blocks until a writer appears, so bounding only the read left the
    # command hanging one line earlier -- which is what a reader saw when
    # ``--timeout 2`` did not stop ``run`` on an unfed pipe.
    program = _bounded_read(path, timeout)
    return program.removesuffix("\n") if isinstance(program, str) else program


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    sys.stderr.write(f"{message}\n")


def _bounded_read(path: str, timeout: float | None) -> str | Raster:
    """Open and read ``path``, with a size cap and a deadline.

    Only the blocking open+read runs on the daemon thread: ``open`` on a
    FIFO waits for a writer, and ``/dev/zero`` reached 3.9 GB ignoring
    ``--timeout`` and SIGINT inside one C call.  Decoding (UTF-8, or a PNG
    for a raster program) runs here on the caller's thread, so its cost is
    not charged to the deadline: a Line PNG decoded for longer than a short
    ``--timeout`` and was misreported as a FIFO that never delivered, though
    the file was a regular one.  The cap is two orders above the largest
    generated program.
    """
    box: list[bytes | BaseException] = []

    def _slurp() -> None:
        try:
            with open(path, "rb") as handle:
                box.append(handle.read(_MAX_PROGRAM_BYTES + 1))
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=_slurp, daemon=True)
    reader.start()
    waited = timeout if timeout is not None else _READ_DEADLINE
    reader.join(waited)
    if reader.is_alive():
        _fail(
            f"gave up reading {path} after {waited:.0f}s -- it is not "
            f"delivering data (a FIFO with no writer, or a device)",
            _TIMEOUT_EXIT,
        )
    result = box[0] if box else b""
    if isinstance(result, OSError):
        _fail(f"cannot read {path}: {result}")
    if isinstance(result, BaseException):
        raise result
    if result.startswith(_PNG_MAGIC):
        # A raster program; decoding it here means ``run`` and ``debug``
        # accept the same PNG ``generate`` wrote, rather than reading its
        # bytes as text and refusing "not text".
        try:
            return Raster.from_png(result)
        except EsolangError as exc:
            _fail(str(exc))
    try:
        text = result.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Its own clause: ``UnicodeDecodeError`` is a ``ValueError``, not an
        # ``OSError``, so pointing ``run`` at a PNG used to dump a raw
        # traceback where every other unreadable file gets one clean line.
        _fail(f"cannot read {path}: not text ({_decode_note(exc)})")
    if len(text) > _MAX_PROGRAM_BYTES:
        _fail(
            f"{path} is larger than the {_MAX_PROGRAM_BYTES // 1024} KiB this "
            f"reads; the largest program this package generates is far under "
            f"it, so this is almost certainly not a program"
        )
    return text


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
    if sys.stdin.isatty():
        return ""
    box: list[str | BaseException] = []

    def _slurp() -> None:
        try:
            box.append(sys.stdin.read())
        except BaseException as exc:
            box.append(exc)

    reader = threading.Thread(target=_slurp, daemon=True)
    reader.start()
    with _WaitingNotice(hint):
        reader.join(timeout)
    if reader.is_alive():
        _fail(
            f"no input arrived on stdin within {timeout:.0f}s, and nothing "
            f"closed it{hint}",
            _TIMEOUT_EXIT,
        )
    result = box[0] if box else ""
    if isinstance(result, UnicodeDecodeError):
        _fail(f"cannot read stdin: not text ({_decode_note(result)})")
    if isinstance(result, BaseException):
        raise result
    hidden = _smuggled_bytes(result)
    if hidden is not None:
        _fail(f"cannot read stdin: not text ({_decode_note(hidden)})")
    return result


class _WaitingNotice:
    """Say, once, that this command is waiting for input that is not coming."""

    def __init__(self, hint: str = "") -> None:
        """Arm the notice, mentioning ``hint`` if there is one."""
        self._timer = threading.Timer(_WAITING_NOTICE_AFTER, self._say, args=(hint,))
        self._timer.daemon = True

    @staticmethod
    def _say(hint: str) -> None:
        """Write the one line, from the timer thread."""
        sys.stderr.write(
            f"still waiting for input on stdin after "
            f"{_WAITING_NOTICE_AFTER:.0f}s; nothing has closed it{hint}\n"
        )

    def __enter__(self) -> _WaitingNotice:
        """Start the timer."""
        self._timer.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        """Cancel it."""
        self._timer.cancel()


def _write_output(text: str) -> None:
    """Write program output to stdout, whatever bytes it turned out to be.

    A program can legitimately print a lone surrogate (Sophie's `,` prints
    the accumulator as a character with no bound), on which
    ``sys.stdout.write`` raised a nineteen-line traceback.  Written through
    the byte stream with ``surrogatepass`` when the text stream refuses,
    keeping ``run --help``'s verbatim promise; a stream with no ``buffer``
    falls back to an escaped form.
    """
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        stream = getattr(sys.stdout, "buffer", None)
        if stream is None:
            sys.stdout.write(text.encode("utf-8", "backslashreplace").decode("utf-8"))
            return
        sys.stdout.flush()
        stream.write(text.encode(sys.stdout.encoding or "utf-8", "surrogatepass"))
        stream.flush()


def _emit_partial(exc: EsolangError) -> None:
    """Write whatever the program printed before ``exc`` to stdout.

    A Modulous program printing ``Hi`` then underflowing gave empty stdout
    where ``debug`` showed ``output: 'Hi'``.  On stdout so a pipe sees the
    same prefix either way.
    """
    if not exc.partial_output:
        return
    _write_output(exc.partial_output)
    if not exc.partial_output.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
