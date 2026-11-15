"""Read source snapshots and publish native program bytes."""

import os
import select
import stat
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from io import BufferedReader, BufferedRWPair, FileIO, IOBase
from math import ceil
from os import PathLike, fspath
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import IO, cast, overload

from esolangs.exceptions import ArgumentError

_STREAM_DEADLINE: ContextVar[float | None] = ContextVar("stream_deadline", default=None)
_BLOCK = 65_536
_WOULD_BLOCK = "stream would block; supply the complete contents"


class StreamReadTimeoutError(TimeoutError):
    """A raw snapshot ran past the invocation's acquisition deadline."""


@contextmanager
def stream_read_deadline(deadline: float | None) -> Iterator[None]:
    """Bound a cooperating stream by an invocation's acquisition deadline."""
    token = _STREAM_DEADLINE.set(deadline)
    try:
        yield
    finally:
        _STREAM_DEADLINE.reset(token)


def _nonblocking_fd(stream: IOBase) -> int | None:
    """Find descriptors that may report temporary absence as EOF."""
    try:
        fd = stream.fileno()
        if not os.get_blocking(fd) and not stat.S_ISREG(os.fstat(fd).st_mode):
            return fd
    except (AttributeError, OSError, TypeError, ValueError):
        # In-memory streams, closed descriptors and unsupported platforms
        # use the original read path, which reports its own failures.
        pass
    return None


def _time_remaining(deadline: float | None) -> float | None:
    """Refuse to start a read after an invocation's deadline."""
    if deadline is None:
        return None
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise StreamReadTimeoutError(
            "stream did not finish before the acquisition deadline"
        )
    return remaining


def _binary_snapshot(
    stream: FileIO | BufferedReader | BufferedRWPair,
    fd: int | None,
    size: int | None,
    deadline: float | None,
    reader: Callable[..., str | bytes | None] | None,
) -> bytes:
    """Read binary chunks through true EOF or a byte cap."""
    read = (
        stream.read if reader is None else cast("Callable[[int], bytes | None]", reader)
    )
    poller = None
    if fd is not None:
        poller = select.poll()
        poller.register(fd, select.POLLIN)
    data = bytearray()
    while size is None or len(data) < size:
        remaining = _time_remaining(deadline)
        chunk = read(_BLOCK if size is None else min(_BLOCK, size - len(data)))
        if chunk is None:
            if poller is None:
                raise BlockingIOError(_WOULD_BLOCK)
            # poll's millisecond timeout is a C int independently of Python's clock.
            poller.poll(
                None if remaining is None else min(ceil(remaining * 1000), 2**31 - 1)
            )
        elif not chunk:
            break
        else:
            data.extend(chunk)
    return bytes(data)


@overload
def read_snapshot(
    stream: IO[str],
    *,
    size: int | None = None,
    reader: Callable[..., str | None] | None = None,
) -> str: ...


@overload
def read_snapshot(
    stream: IO[bytes],
    *,
    size: int | None = None,
    reader: Callable[..., bytes | None] | None = None,
) -> bytes: ...


def read_snapshot(
    stream: IO[str] | IO[bytes],
    *,
    size: int | None = None,
    reader: Callable[..., str | bytes | None] | None = None,
) -> str | bytes:
    """Read from the current position, reusing an already-bound reader if given."""
    fd = _nonblocking_fd(stream) if isinstance(stream, IOBase) else None
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    if isinstance(stream, BufferedRWPair):
        # The reader's fd is private. Sized reads distinguish None from EOF,
        # while an unbounded read can return a prefix before the writer closes.
        return _binary_snapshot(stream, None, size, deadline, reader)
    if fd is not None:
        if hasattr(select, "poll") and (
            isinstance(stream, FileIO)
            or (isinstance(stream, BufferedReader) and isinstance(stream.raw, FileIO))
        ):
            return _binary_snapshot(stream, fd, size, deadline, reader)
        raise BlockingIOError(
            "cannot detect EOF on this nonblocking stream; "
            "pass a blocking stream or supply the complete contents"
        )
    read = stream.read if reader is None else reader
    value = read() if size is None else read(size)
    if value is None:
        raise BlockingIOError(_WOULD_BLOCK)
    return value


def explicit_path(path: str | PathLike[str]) -> Path:
    """Validate a path argument before opening or reading a file."""
    try:
        spelling = fspath(path)
    except (TypeError, ValueError) as error:
        raise ArgumentError("path must be a str or PathLike returning str") from error
    if not isinstance(spelling, str):
        raise ArgumentError("path must be a str or PathLike returning str")
    spelling = str.__str__(spelling)
    if not spelling:
        raise ArgumentError("path must not be empty")
    return Path(spelling)


def write_staged(target: Path, chunks: Iterable[bytes]) -> None:
    """Replace the directory entry only after all source bytes are written."""
    # The staged write's errors should name the destination, not a temporary file.
    if target.is_dir():
        raise IsADirectoryError("it is a directory")
    if not target.parent.is_dir():
        raise FileNotFoundError("its directory does not exist")
    with TemporaryDirectory(dir=target.parent) as temporary:
        staged = Path(temporary) / "source"
        with staged.open("wb") as stream:
            stream.writelines(chunks)
        staged.replace(target)
