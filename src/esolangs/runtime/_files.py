"""Path arguments and staged publication of native program bytes."""

from collections.abc import Iterable
from os import PathLike, fspath
from pathlib import Path
from tempfile import TemporaryDirectory

from esolangs.exceptions import ArgumentError


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
