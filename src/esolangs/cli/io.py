"""Reading a program and stdin under a bound, and writing the answer out.

Both can block forever (a fifo, a pipe nobody writes to), so every read
carries a size and a deadline, and two notices say why nothing happened.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager

from esolangs import _read_source, load_program
from esolangs.cli.args import _check_count, _errors, _fail
from esolangs.cli.hints import _TIMEOUT_EXIT, _decode_note
from esolangs.exceptions import EsolangError, ProgramError
from esolangs.registry import resolve
from esolangs.runtime._program import Program
from esolangs.runtime._source import _FileSource
from esolangs.settings import DialectSettings, dialect_options, effective_settings

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


def _read_program(
    path: str,
    timeout: float | None = None,
    *,
    language: str,
    portable: bool = False,
    settings: DialectSettings | None = None,
    content: bytes | None = None,
) -> Program:
    """Read bounded source or portable JSON; validate overrides before stdin."""
    if content is None:
        content = _bounded_read(path, timeout)
    try:
        if portable:
            program = load_program(language, _portable_text(content))
            dialect_options(language, effective_settings(language, program, settings))
            return program
        return _read_source(language, _FileSource(path, content))
    except EsolangError as exc:
        _fail(exc)
        raise  # pragma: no cover - _fail exits


def _portable_text(content: bytes) -> str:
    """Decode a portable document, which must be UTF-8."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProgramError("portable program must be UTF-8 JSON") from exc


def _portable_language(path: str, timeout: float | None = None) -> tuple[str, bytes]:
    """Return the language and acquired bytes of a portable document."""
    content = _bounded_read(path, timeout)
    try:
        value = json.loads(_portable_text(content))
    except ValueError as exc:
        raise ProgramError(f"invalid portable program: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("language"), str):
        raise ProgramError("invalid portable program: language must be a string")
    return resolve(value["language"]), content


def _resolve_target(
    command: str, rest: list[str], timeout: float | None, *, portable: bool
) -> tuple[str, str, bytes | None]:
    """Split positionals into ``(language, path, content)``.

    With ``--portable`` and a single positional, that positional is a
    document carrying its own language; otherwise the positionals are
    the language and the program path.
    """
    if portable and len(rest) == 1:
        path = rest[0]
        with _errors():
            language, content = _portable_language(path, timeout)
    else:
        _check_count(command, rest, 2)
        language, path = rest[0], rest[1]
        content = None
    return language, path, content


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    sys.stderr.write(f"{message}\n")


def _termination_notice(name: str, bounds: str) -> None:
    """Warn that a termination-mode language answers 1 by not halting.

    ``bounds`` names how this command can bound the run, e.g.
    ``"--timeout SECONDS"`` or ``"--timeout SECONDS or --steps N"``.
    """
    _note(
        f"{name}: this language answers 1 by not terminating, so a "
        f"program with that answer will run until you stop it; pass "
        f"{bounds} to bound it"
    )


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
            f"gave up reading {path} after {waited:.0f}s -- it is not "
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
    if sys.stdin.isatty():
        return ""

    def _read_text() -> str:
        try:
            return sys.stdin.read()
        except UnicodeDecodeError as exc:
            _fail(f"cannot read stdin: not text ({_decode_note(exc)})")

    def _on_timeout() -> None:
        _fail(
            f"no input arrived on stdin within {timeout:.0f}s, and nothing "
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

    A program can legitimately print a lone surrogate (a print command emits
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

    A program printing ``Hi`` then underflowing gave empty stdout
    where ``debug`` showed ``output: 'Hi'``.  On stdout so a pipe sees the
    same prefix either way.
    """
    if not exc.partial_output:
        return
    _write_output(exc.partial_output)
    if not exc.partial_output.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
