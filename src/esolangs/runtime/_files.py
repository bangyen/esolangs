"""Read source snapshots and publish native program bytes."""

import os
import select
import stat
from codecs import utf_8_decode
from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from errno import ENOTDIR
from io import BufferedReader, BufferedRWPair, FileIO, IOBase
from math import ceil
from os import PathLike, fspath
from pathlib import Path, PosixPath, WindowsPath
from string import ascii_uppercase
from tempfile import TemporaryDirectory
from time import monotonic
from typing import IO, cast, overload

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.outcomes import _remember_acquisition_failure
from esolangs.runtime._validate import _has_backing_type

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
    except EsolangError:
        raise
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


def decode_utf8(data: bytes) -> str:
    """Decode UTF-8, checking the acquisition deadline between bounded chunks."""
    deadline = _STREAM_DEADLINE.get()
    if deadline is None:
        return bytes.decode(data, "utf-8")
    parts: list[str] = []
    size = bytes.__len__(data)
    offset = 0
    while offset < size:
        _time_remaining(deadline)
        end = min(offset + _BLOCK, size)
        block = bytes.__getitem__(data, slice(offset, end))
        try:
            text, consumed = utf_8_decode(block, "strict", end == size)
        except UnicodeDecodeError as error:
            _time_remaining(deadline)
            error.object = bytes.__bytes__(data)
            error.start += offset
            error.end += offset
            error.args = (
                error.encoding,
                error.object,
                error.start,
                error.end,
                error.reason,
            )
            raise
        parts.append(text)
        # A nonfinal decode can leave an incomplete code point for the next block.
        offset += consumed
    _time_remaining(deadline)
    text = "".join(parts)
    _time_remaining(deadline)
    return text


def _binary_chunk(value: object) -> bytes:
    """Use the stored bytes before testing for EOF or accumulating input."""
    if not _has_backing_type(value, bytes):
        raise TypeError("binary stream read must return bytes")
    return bytes.__bytes__(value)


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
            continue
        block = _binary_chunk(chunk)
        if not block:
            break
        data.extend(block)
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
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    fd = _nonblocking_fd(stream) if _has_backing_type(stream, IOBase) else None
    _time_remaining(deadline)
    if _has_backing_type(stream, BufferedRWPair):
        # The reader's fd is private. Sized reads distinguish None from EOF,
        # while an unbounded read can return a prefix before the writer closes.
        return _binary_snapshot(stream, None, size, deadline, reader)
    if fd is not None:
        if hasattr(select, "poll") and (
            _has_backing_type(stream, FileIO)
            or (
                _has_backing_type(stream, BufferedReader)
                and _has_backing_type(stream.raw, FileIO)
            )
        ):
            return _binary_snapshot(stream, fd, size, deadline, reader)
        raise BlockingIOError(
            "cannot detect EOF on this nonblocking stream; "
            "pass a blocking stream or supply the complete contents"
        )
    if reader is None:
        reader = stream.read
        _time_remaining(deadline)
    value = reader() if size is None else reader(size)
    if value is None:
        raise BlockingIOError(_WOULD_BLOCK)
    return value


@dataclass(frozen=True, slots=True)
class _ExplicitPath:
    """A file argument whose OS spelling still includes its final component."""

    spelling: str
    _destination: str | OSError | None = None

    def __fspath__(self) -> str:
        return self.spelling

    def __str__(self) -> str:
        return self.spelling

    def anchor_destination(
        self, directory: "_SourceDirectory | None"
    ) -> "_ExplicitPath":
        """Freeze the destination spelling, leaving errors to staging."""
        if self._destination is not None:
            return self
        try:
            return _ExplicitPath(
                self.spelling, _anchored_spelling(self.spelling, directory)
            )
        except OSError as error:
            return _ExplicitPath(self.spelling, error)

    def destination(self) -> str:
        """Return the target spelling for staging and replacement."""
        if isinstance(self._destination, OSError):
            raise self._destination
        if self._destination is not None:
            return self._destination
        return _anchored_spelling(self.spelling)


def explicit_path(path: str | PathLike[str]) -> _ExplicitPath:
    """Validate a path argument before opening or reading a file."""
    if _has_backing_type(path, _ExplicitPath):
        return path
    try:
        spelling = fspath(path)
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
    except (TypeError, ValueError) as error:
        raise ArgumentError("path must be a str or PathLike returning str") from error
    if not _has_backing_type(spelling, str):
        raise ArgumentError("path must be a str or PathLike returning str")
    spelling = str.__str__(spelling)
    if not spelling:
        raise ArgumentError("path must not be empty")
    return _ExplicitPath(spelling)


class _SourceDirectory:
    """Capture the lexical bases a late path provider may select."""

    def __init__(self, spelling: str | None) -> None:
        self.current = self._capture()
        self.drives: dict[str, str | OSError] = {}
        if os.name != "nt":
            return
        if spelling is None:
            # A managed provider may return a drive-relative operand later.
            drives = tuple(f"{letter}:" for letter in ascii_uppercase)
        else:
            drive = os.path.splitdrive(spelling)[0]
            drives = (drive.upper(),) if drive else ()
        active = (
            os.path.splitdrive(self.current)[0].upper()
            if isinstance(self.current, str)
            else None
        )
        self.drives.update(
            (drive, self.current if drive == active else self._capture(drive))
            for drive in drives
        )

    @staticmethod
    def _capture(drive: str = "") -> str | OSError:
        try:
            return _working_directory(drive)
        except OSError as error:
            return error

    def resolve(self, spelling: str) -> str:
        return _anchored_spelling(spelling, self)

    def base(self, drive: str) -> str:
        result = self.drives.get(drive.upper()) if drive else self.current
        if isinstance(result, OSError):
            raise result
        return _working_directory(drive) if result is None else result


def _working_directory(drive: str) -> str:
    return os.path.abspath(f"{drive}.") if drive else os.getcwd()


def _absolute_spelling(path: str, drive: str) -> bool:
    return os.path.isabs(path) and (os.name != "nt" or bool(drive))


def _source_directory(spelling: str | None) -> _SourceDirectory | None:
    if spelling is not None and _absolute_spelling(
        spelling, os.path.splitdrive(spelling)[0]
    ):
        return None
    return _SourceDirectory(spelling)


def _path_directory(path: str | PathLike[str]) -> _SourceDirectory | None:
    """Capture path bases without calling an arbitrary path provider."""
    spelling = None
    if _has_backing_type(path, _ExplicitPath):
        spelling = path.spelling
    elif _has_backing_type(path, str):
        spelling = str.__str__(path)
    elif type(path) in (PosixPath, WindowsPath):
        spelling = str(path)
    return _source_directory(spelling)


def destination_path(path: str | PathLike[str]) -> _ExplicitPath:
    """Bind a destination relative to the caller's directory."""
    directory = _path_directory(path)
    return explicit_path(path).anchor_destination(directory)


def _anchored_spelling(path: str, directory: _SourceDirectory | None = None) -> str:
    """Freeze the current directory without normalizing the target spelling."""
    drive, tail = os.path.splitdrive(path)
    if _absolute_spelling(path, drive):
        return path
    # Windows has both rooted paths on the current drive and drive-local CWDs.
    base = _working_directory(drive) if directory is None else directory.base(drive)
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
    destination = target.destination()
    parent = os.path.dirname(destination)
    try:
        parent_mode = os.stat(parent).st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError("its directory does not exist") from error
    if not stat.S_ISDIR(parent_mode):
        raise NotADirectoryError(ENOTDIR, os.strerror(ENOTDIR), parent)
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
