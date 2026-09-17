"""Reading a program and stdin under a bound, and writing the answer out.

A program file and stdin are both untrusted and both can block forever -- a
fifo, a terabyte of source, a pipe nobody writes to -- so every read here
carries a size and a deadline, and the two notices tell a waiting user why
nothing has happened yet.
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

    ``run`` and ``debug`` take no bound by default, which is right -- most
    of these programs halt, and imposing a budget nobody chose would be
    worse.  But several languages loop forever *by design*, and the
    unbounded path on one of those is an indefinite spin with no output and
    nothing on screen to suggest a cause; one reader killed it after eight
    CPU-minutes.

    So the default is unchanged and the silence is not: a timer fires once,
    names the flag, and is cancelled the moment the run finishes.  Nothing
    is printed for the ordinary case of a program that halts promptly.
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


def _read_program(path: str, timeout: float | None = None) -> str:
    """Return the program in ``path``, or exit with a usage error.

    The trailing newline is the *file's*, not the program's, and three
    interpreters (CV(N)(C), Grapheme, NoComment) reject one as an unknown
    command.  Since ``esolangs generate ... > prog.txt`` writes that newline,
    keeping it meant this tool produced programs its own ``run`` refused,
    and the three committed examples could not be run at all.
    """
    # The *open* is on the thread as well as the read.  Opening a FIFO
    # blocks until a writer appears, so bounding only the read left the
    # command hanging one line earlier -- which is what a reader saw when
    # ``--timeout 2`` did not stop ``run`` on an unfed pipe.
    return _bounded_read(path, timeout).rstrip("\n")


def _note(message: str) -> None:
    """Write one advisory line to stderr, without Python's warning framing."""
    sys.stderr.write(f"{message}\n")


def _bounded_read(path: str, timeout: float | None) -> str:
    """Open and read ``path``, with a size cap and a deadline.

    Both halves on a daemon thread, because both can block forever and
    neither can be interrupted from Python: ``open`` on a FIFO waits for a
    writer, and a read of a character device never ends -- ``/dev/zero``
    reached 3.9 GB of resident memory, ignored ``--timeout``, and ignored
    SIGINT, because the interpreter sat inside one C-level call throughout.

    The size cap is two orders of magnitude above the largest program any
    generator here produces.  The deadline is the caller's ``--timeout``
    when there is one, so the bound they asked for covers the whole
    command rather than only the part after the file is in memory.
    """
    box: list[str | BaseException] = []

    def _slurp() -> None:
        try:
            with open(path) as handle:
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
    result = box[0] if box else ""
    if isinstance(result, OSError):
        _fail(f"cannot read {path}: {result}")
    if isinstance(result, UnicodeDecodeError):
        # Its own clause: ``UnicodeDecodeError`` is a ``ValueError``, not an
        # ``OSError``, so pointing ``run`` at a PNG used to dump a raw
        # traceback where every other unreadable file gets one clean line.
        _fail(f"cannot read {path}: not text ({_decode_note(result)})")
    if isinstance(result, BaseException):
        raise result
    if len(result) > _MAX_PROGRAM_BYTES:
        _fail(
            f"{path} is larger than the {_MAX_PROGRAM_BYTES // 1024} KiB this "
            f"reads; the largest program this package generates is far under "
            f"it, so this is almost certainly not a program"
        )
    return result


def _smuggled_bytes(text: str) -> UnicodeDecodeError | None:
    """Return the decode error ``surrogateescape`` hid in *text*, if any.

    ``sys.stdin`` decodes strictly only some of the time.  Under UTF-8
    mode -- which Python enables by itself when the locale is ``C``, as it
    is on a bare CI runner -- the standard streams decode with
    ``surrogateescape`` instead, so a binary stdin never raises: its bytes
    arrive as lone surrogates and flow on into a reader, which then
    complains about a U+DC80 rather than refusing the input.

    This adds no refusal.  It gives UTF-8 mode the behaviour strict mode
    already had at the call below -- same message, same exit code, same
    byte offset -- by encoding the escapes back to the bytes they stand
    for and decoding those strictly, which raises what the stream did not.

    Lone surrogates are the only characters UTF-8 cannot encode, so that
    failure is the test for whether the round trip is worth making.
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

    Shared by the commands that read it.  Each called ``sys.stdin.read()``
    directly and each therefore had the same hole: a program's binary output
    piped into ``read-answer`` crashed with a traceback rather than being
    refused.

    **The read is bounded and announced.**  ``sys.stdin.read()`` blocks
    until end-of-file, so a pipe that is open and never written -- which is
    what a terminal looks like, and what a parent process that forgot to
    close stdin gives you -- hung this command forever with nothing on
    screen.  ``--timeout`` did not help, because it bounds *execution* and
    this happens before any program runs.

    So: the read happens on a daemon thread, ``--timeout`` bounds it as
    well, and an unbounded read that is still waiting says so.  A thread
    rather than :func:`select.select` because stdin here is not always a
    real file -- the tests supply an object with no ``fileno`` -- and this
    works for anything with a ``read``.
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
    """Say, once, that this command is waiting for input that is not coming.

    The same shape as :class:`_UnboundedNotice` and for the same reason: the
    default is unchanged and the silence is not.
    """

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

    A program's output is whatever the program produced, and not all of it
    is encodable text.  WII2D's ``~`` prints the accumulator as a character
    with no bound, so a program can legitimately produce a lone surrogate
    -- and ``sys.stdout.write`` on one of those raises
    ``UnicodeEncodeError`` from inside the CLI, which reached the user as a
    nineteen-line traceback.  That is the one thing this CLI is built not
    to do.

    Written through the byte stream with ``surrogatepass`` when the text
    stream refuses, which keeps the promise ``run --help`` makes -- output
    goes out verbatim, so it can be compared or piped byte for byte -- for
    output that has no valid UTF-8 spelling.  A stream with no ``buffer``
    (a captured one, mainly) falls back to an escaped form, which is not
    byte-exact and is better than an exception.
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

    A run that failed used to emit nothing at all -- a Modulous program
    printing ``Hi`` and then popping an empty stack gave an empty stdout,
    an empty stderr and exit 1, while ``debug`` on the same file showed
    ``output: 'Hi'``.  The bytes before the failure are most of the
    diagnosis when the program is one you are still writing.

    On stdout, where the successful run puts them, so a pipe sees the same
    prefix either way and the error stays on stderr.
    """
    if not exc.partial_output:
        return
    _write_output(exc.partial_output)
    if not exc.partial_output.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
