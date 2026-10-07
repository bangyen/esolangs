"""Source containers, decoded at the interpreter boundary."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from esolangs._input import InputSource as InputSource
from esolangs._input import check_input as check_input
from esolangs._input import read_input as read_input
from esolangs._program import Program
from esolangs.exceptions import ArgumentError, ProgramError, ProgramNotFoundError
from esolangs.interpreters.source_hints import syntax_error, with_hint
from esolangs.raster import Raster

type ProgramSource = Program | bytes | os.PathLike[str] | IO[str] | IO[bytes]


@dataclass(frozen=True, slots=True)
class _FileSource:
    """A bounded file snapshot retaining file newline semantics."""

    path: str
    content: bytes

    def read(self) -> bytes:
        return self.content

    def __str__(self) -> str:
        return self.path


def _read_container(
    source: ProgramSource | _FileSource,
) -> tuple[Program | bytes, bool]:
    try:
        if isinstance(source, _FileSource):
            return source.read(), True
        if isinstance(source, os.PathLike):
            return Path(source).read_bytes(), True
        if isinstance(source, (str, bytes, Raster)):
            return source, False
        if callable(getattr(source, "read", None)):
            value = source.read()
            if isinstance(value, (str, bytes)):
                return value, False
    except FileNotFoundError as exc:
        raise syntax_error(
            f"cannot read {source!s}: {exc}",
            "check that the source path exists and names the intended program file",
            error_type=ProgramNotFoundError,
        ) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise syntax_error(
            f"cannot read {source!s}: {exc}",
            "check that the program file or stream is readable",
            error_type=ProgramError,
        ) from exc
    raise syntax_error(
        "program must be a string of source, bytes, a Raster, a Path, "
        f"or a readable stream, got {type(source).__name__}",
        "pass source text or bytes; use pathlib.Path for a program filename",
        error_type=ProgramError,
    )


def text_source(source: ProgramSource | _FileSource) -> str:
    """Load UTF-8 source; only Paths lose one trailing newline."""
    value, path = _read_container(source)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise syntax_error(
                f"cannot read {source!s}: not text (invalid UTF-8 at byte {exc.start})",
                "save the text program as UTF-8 before running it",
                error_type=ProgramError,
            ) from exc
    if not isinstance(value, str):
        raise syntax_error(
            f"program must be a string of source or a Path, got {type(value).__name__}",
            "pass text source or UTF-8 bytes; use pathlib.Path for a text filename",
            error_type=ProgramError,
        )
    return (
        value.replace("\r\n", "\n").replace("\r", "\n").removesuffix("\n")
        if path
        else value
    )


def raster_source(source: ProgramSource | _FileSource) -> Raster:
    """Load a Raster or lossless PNG bytes from any supported container."""
    value, _path = _read_container(source)
    if isinstance(value, bytes):
        return Raster.from_png(value)
    if not isinstance(value, Raster):
        raise syntax_error(
            f"program must be a Raster or a Path, got {type(value).__name__}",
            "pass a Raster or PNG bytes; use pathlib.Path for a PNG filename",
            error_type=ProgramError,
        )
    return value


def check_scale_for(language: str, scale: int | None) -> None:
    """Validate scale using the interpreter's declared capability."""
    if scale is None:
        return
    from esolangs._execution import interpreter_module
    from esolangs._validate import check_scale
    from esolangs.registry import resolve

    check_scale(scale)
    module = interpreter_module(resolve(language))
    if not getattr(module, "supports_scale", False):
        raise with_hint(
            ArgumentError("scale is only supported for raster interpreters"),
            ("omit scale for text languages; apply it only to raster source"),
        )
