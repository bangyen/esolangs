"""Read source snapshots and publish native program bytes."""

import os
import select
import stat
from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
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


@overload
def read_snapshot(
    stream: IO[str] | IO[bytes],
    *,
    size: int | None = None,
    reader: Callable[..., str | bytes | None],
) -> str | bytes: ...


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


@dataclass(frozen=True, slots=True)
class _ExplicitPath:
    """A file argument whose OS spelling still includes its final component."""

    spelling: str

    def __fspath__(self) -> str:
        return self.spelling

    def __str__(self) -> str:
        return self.spelling


def explicit_path(path: str | PathLike[str]) -> _ExplicitPath:
    """Validate a path argument before opening or reading a file."""
    if isinstance(path, _ExplicitPath):
        return path
    try:
        spelling = fspath(path)
    except (TypeError, ValueError) as error:
        raise ArgumentError("path must be a str or PathLike returning str") from error
    if not isinstance(spelling, str):
        raise ArgumentError("path must be a str or PathLike returning str")
    spelling = str.__str__(spelling)
    if not spelling:
        raise ArgumentError("path must not be empty")
    return _ExplicitPath(spelling)


def _anchored_spelling(path: str) -> str:
    """Freeze the current directory without normalizing the target spelling."""
    drive, tail = os.path.splitdrive(path)
    if os.path.isabs(path) and (os.name != "nt" or drive):
        return path
    # Windows has both rooted paths on the current drive and drive-local CWDs.
    base = os.path.abspath(f"{drive}.") if drive else os.getcwd()
    return os.path.join(base, tail)


def _destination_mode(target: str) -> int | None:
    """Read the destination entry's mode, refusing directories."""
    # A missing entry can be created. Other lookup errors must surface before
    # reading a source stream, even when isdir() would simply return False.
    try:
        mode = os.lstat(target).st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISDIR(mode) or (stat.S_ISLNK(mode) and os.path.isdir(target)):
        raise IsADirectoryError("it is a directory")
    return mode


@contextmanager
def reserve_staged(
    target: _ExplicitPath,
) -> Iterator[Callable[[Iterable[bytes]], None]]:
    """Reserve an open staging file and yield its write-and-replace operation."""
    if "\0" in target.spelling:
        raise ValueError("embedded null character in path")
    destination = _anchored_spelling(target.spelling)
    parent = os.path.dirname(destination)
    if not os.path.isdir(parent):
        raise FileNotFoundError("its directory does not exist")
    _destination_mode(destination)
    if os.name == "posix" and ".." in parent.split(os.sep):
        # tempfile normalizes its result. Resolve symlinks before their '..'.
        parent = os.path.realpath(parent, strict=True)
    with ExitStack() as cleanup:
        try:
            temporary = cleanup.enter_context(TemporaryDirectory(dir=parent))
            staged = Path(temporary) / "source"
            stream = cleanup.enter_context(staged.open("wb"))

            def publish(chunks: Iterable[bytes]) -> None:
                stream.writelines(chunks)
                stream.close()
                # Use current access bits after a potentially slow acquisition/write.
                mode = _destination_mode(destination)
                if os.name == "posix" and mode is not None and stat.S_ISREG(mode):
                    staged.chmod(mode & 0o777)
                staged.replace(destination)
                cleanup.close()

            yield publish
        except BaseException as error:
            try:
                cleanup.close()
            except OSError as cleanup_error:
                error.add_note(f"could not clean staging for {target}: {cleanup_error}")
            raise


def write_staged(target: _ExplicitPath, chunks: Iterable[bytes]) -> None:
    """Replace the directory entry only after all source bytes are written."""
    with reserve_staged(target) as publish:
        publish(chunks)
