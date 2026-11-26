"""Stage and replace native program files."""

import os
import stat
from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack, contextmanager, suppress
from errno import ENOTDIR
from pathlib import Path
from secrets import token_hex
from tempfile import TemporaryDirectory
from typing import BinaryIO

from esolangs.runtime._files import _ExplicitPath


def _destination_mode(target: str, *, directory: int | None = None) -> int | None:
    """Read the destination entry's mode, refusing directories."""
    # A missing entry can be created. Other lookup errors must surface before
    # reading a source stream, even when isdir() would simply return False.
    try:
        mode = os.lstat(target, dir_fd=directory).st_mode
    except FileNotFoundError:
        return None
    followed = mode
    if stat.S_ISLNK(mode):
        with suppress(OSError):
            followed = os.stat(target, dir_fd=directory).st_mode
    if stat.S_ISDIR(followed):
        raise IsADirectoryError("it is a directory")
    return mode


# Search-only opens preserve the ability to export into a write/search directory
# even when the caller cannot list it. Other platforms use pathname staging.
_DIRECTORY_SEARCH = getattr(os, "O_PATH", getattr(os, "O_SEARCH", None))
_ANCHORED_STAGING = (
    _DIRECTORY_SEARCH is not None
    and {os.open, os.mkdir, os.unlink, os.rmdir, os.lstat, os.stat, os.chmod, os.rename}
    <= os.supports_dir_fd
)


def _unlink_staged(directory: int) -> None:
    with suppress(FileNotFoundError):
        os.unlink("source", dir_fd=directory)


def _stage_in_directory(
    parent: str, filename: str, cleanup: ExitStack
) -> tuple[BinaryIO, Callable[[], None]]:
    """Hold the destination directory even if a source callback renames it."""
    assert _DIRECTORY_SEARCH is not None
    flags = _DIRECTORY_SEARCH | os.O_DIRECTORY
    directory = os.open(parent, flags)
    cleanup.callback(os.close, directory)
    _destination_mode(filename or ".", directory=directory)
    while True:
        temporary = f"tmp-{token_hex(8)}"
        try:
            os.mkdir(temporary, mode=0o700, dir_fd=directory)
        except FileExistsError:
            continue
        break
    cleanup.callback(os.rmdir, temporary, dir_fd=directory)
    stage = os.open(temporary, flags | os.O_NOFOLLOW, dir_fd=directory)
    cleanup.callback(os.close, stage)
    cleanup.callback(_unlink_staged, stage)

    def open_source(path: str, flags: int) -> int:
        return os.open(path, flags, mode=0o666, dir_fd=stage)

    stream = cleanup.enter_context(open("source", "xb", opener=open_source))  # noqa: SIM115

    def replace_source() -> None:
        mode = _destination_mode(filename, directory=directory)
        if mode is not None and stat.S_ISREG(mode):
            os.chmod("source", mode & 0o777, dir_fd=stage)
        os.replace("source", filename, src_dir_fd=stage, dst_dir_fd=directory)

    return stream, replace_source


def _stage_at_path(
    parent: str, filename: str, cleanup: ExitStack
) -> tuple[BinaryIO, Callable[[], None]]:
    """Stage beside a resolved destination on platforms without directory fds."""
    # Resolve only the parent: trailing separators and final link entries matter.
    parent = os.path.realpath(parent, strict=True)
    destination = os.path.join(parent, filename)
    _destination_mode(destination)
    temporary = cleanup.enter_context(TemporaryDirectory(dir=parent))
    staged = Path(temporary) / "source"
    stream = cleanup.enter_context(staged.open("wb"))

    def replace_source() -> None:
        mode = _destination_mode(destination)
        if os.name == "posix" and mode is not None and stat.S_ISREG(mode):
            staged.chmod(mode & 0o777)
        os.replace(staged, destination)

    return stream, replace_source


@contextmanager
def reserve_staged(
    target: _ExplicitPath,
) -> Iterator[Callable[[Iterable[bytes]], None]]:
    """Reserve an open staging file and yield its write-and-replace operation."""
    if "\0" in target.spelling:
        raise ValueError("embedded null character in path")
    destination = target.destination()
    parent, filename = os.path.split(destination)
    try:
        parent_mode = os.stat(parent).st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError("its directory does not exist") from error
    if not stat.S_ISDIR(parent_mode):
        raise NotADirectoryError(ENOTDIR, os.strerror(ENOTDIR), parent)
    with ExitStack() as cleanup:
        try:
            prepare = _stage_in_directory if _ANCHORED_STAGING else _stage_at_path
            stream, replace_source = prepare(parent, filename, cleanup)

            def publish(chunks: Iterable[bytes]) -> None:
                stream.writelines(chunks)
                stream.close()
                # Use current access bits after a potentially slow acquisition/write.
                replace_source()
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
