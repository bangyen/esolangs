"""Source containers, decoded at the interpreter boundary."""

from __future__ import annotations

import os
from pathlib import Path

from esolangs._input import InputSource as InputSource
from esolangs._input import Reader
from esolangs._input import check_input as check_input
from esolangs._input import read_input as read_input
from esolangs.exceptions import ArgumentError, ProgramError, ProgramNotFoundError
from esolangs.raster import Raster

type ProgramSource = str | bytes | Raster | os.PathLike[str] | Reader


def _read_container(source: ProgramSource) -> tuple[str | bytes | Raster, bool]:
    try:
        if isinstance(source, os.PathLike):
            return Path(source).read_bytes(), True
        if isinstance(source, (str, bytes, Raster)):
            return source, False
        if callable(getattr(source, "read", None)):
            value = source.read()
            if isinstance(value, (str, bytes)):
                return value, False
    except FileNotFoundError as exc:
        raise ProgramNotFoundError(f"cannot read {source!s}: {exc}") from exc
    except (OSError, TypeError, ValueError) as exc:
        raise ProgramError(f"cannot read {source!s}: {exc}") from exc
    raise ProgramError(
        "program must be a string of source, bytes, a Raster, a Path, "
        f"or a readable stream, got {type(source).__name__}"
    )


def text_source(source: ProgramSource) -> str:
    """Load UTF-8 source; only Paths lose one trailing newline."""
    value, path = _read_container(source)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProgramError(
                f"cannot read {source!s}: not text (invalid UTF-8 at byte {exc.start})"
            ) from exc
    if not isinstance(value, str):
        raise ProgramError(
            f"program must be a string of source or a Path, got {type(value).__name__}"
        )
    return (
        value.replace("\r\n", "\n").replace("\r", "\n").removesuffix("\n")
        if path
        else value
    )


def raster_source(source: ProgramSource) -> Raster:
    """Load a Raster or lossless PNG bytes from any supported container."""
    value, _path = _read_container(source)
    if isinstance(value, bytes):
        return Raster.from_png(value)
    if not isinstance(value, Raster):
        raise ProgramError(
            f"program must be a Raster or a Path, got {type(value).__name__}"
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
        raise ArgumentError("scale is only supported for raster interpreters")
