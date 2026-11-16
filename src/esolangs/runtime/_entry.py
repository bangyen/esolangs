"""The shared ``python <file>`` entry point behind every interpreter.

Each interpreter keeps a two-line ``__main__`` block so a standalone
``python <file>`` runs it.  Its body moved here from 63 copies in nine
variants, which coverage's ``exclude_lines`` measured in none of them.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from esolangs.runtime._files import explicit_path
from esolangs.runtime._source import (
    compressed_text_source,
    native_text_source,
    text_source,
)
from esolangs.runtime.io import IO, _RedirectedIO

if TYPE_CHECKING:
    from os import PathLike

    from esolangs.raster import Raster

#: How ``run`` wants the source: the whole string, the lines with newlines
#: (``readlines()``), or without (``splitlines()``).  A grid language handed
#: kept newlines reads a column too many, so these are not interchangeable.
SourceShape = Literal["text", "keep", "strip"]
# These loaders accept exact path spellings without needing a pathlib.Path.
_TEXT_LOADERS = (text_source, native_text_source, compressed_text_source)


def _standard_io() -> IO:
    """Keep TTY input interactive and borrow redirected text without a snapshot."""
    stream = sys.stdin
    with suppress(OSError, ValueError):
        isatty = getattr(stream, "isatty", None)
        if callable(isatty) and isatty():
            return IO()
    return _RedirectedIO(stream)


def script_main(
    run: Callable[[Any, IO], int | None],
    *,
    shape: SourceShape = "text",
    loader: Callable[[Path], Any] | None = None,
) -> None:
    """Run the program file named by ``sys.argv[1]``, if one was given.

    A missing argument is a no-op; a non-``None`` return becomes the exit
    status (the language's halt).  Read as UTF-8, not the locale encoding.
    Default text decoding accepts gzip and retains universal-newline behavior,
    including the final newline. Explicit loaders own their decoding policy.
    """
    if len(sys.argv) < 2:
        return
    spelling = sys.argv[1]
    if loader is None:
        source: Any = text_source(explicit_path(spelling))
        source = source.replace("\r\n", "\n").replace("\r", "\n")
    elif any(loader is read for read in _TEXT_LOADERS):
        reader = cast("Callable[[PathLike[str]], Any]", loader)
        source = reader(explicit_path(spelling))
    else:
        source = loader(Path(spelling))
    if shape == "keep":
        source = source.splitlines(keepends=True)
    elif shape == "strip":
        source = source.splitlines()
    code = run(source, _standard_io())
    if code is not None:
        sys.exit(code)


class _RasterRunner(Protocol):
    def __call__(
        self, program: Raster, io: IO, /, *, scale: int | None
    ) -> int | None: ...


def raster_script_main(language: str, run: _RasterRunner) -> None:
    """Run a standalone PNG with its retained scale and interactive I/O."""
    if len(sys.argv) < 2:
        return
    from esolangs.operations.source import from_file
    from esolangs.raster import Raster

    artifact = from_file(language, sys.argv[1])
    assert isinstance(artifact.source, Raster)
    code = run(artifact.source, _standard_io(), scale=artifact.scale)
    if code is not None:
        sys.exit(code)
