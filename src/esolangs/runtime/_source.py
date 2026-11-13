"""Source containers, decoded at the interpreter boundary."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText
from esolangs.exceptions import ArgumentError, ProgramError, ProgramNotFoundError
from esolangs.raster import Raster
from esolangs.runtime._definition import SourceLoader
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_scale
from esolangs.runtime.source_hints import syntax_error, with_hint

if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


type ProgramSource = Program | Artifact | bytes | os.PathLike[str] | IO[str] | IO[bytes]


@dataclass(frozen=True, slots=True)
class _FileSource:
    """A bounded file snapshot retaining its filename for errors."""

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
        if isinstance(source, (ProgramArtifact, TemplateArtifact)):
            source = source.source
        if isinstance(source, _FileSource):
            return source.read(), True
        if isinstance(source, os.PathLike):
            return Path(source).read_bytes(), True
        if isinstance(source, (str, bytes, Raster, CompressedText)):
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


def _label(source: object) -> str:
    """Name a source in errors: its path, never its (possibly huge) bytes."""
    if isinstance(source, (os.PathLike, _FileSource)):
        return str(source)
    return "the program"


def text_source(
    source: ProgramSource | _FileSource, *, label: str | None = None
) -> str:
    """Decode UTF-8 source without changing line endings or terminators."""
    label = _label(source) if label is None else label
    value, _path = _read_container(source)
    if isinstance(value, bytes) and value.startswith(b"\x1f\x8b"):
        value = CompressedText(value)
    if isinstance(value, CompressedText):
        value = str(value)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise syntax_error(
                f"cannot read {label}: not text (invalid UTF-8 at byte {exc.start})",
                "save the text program as UTF-8 before running it",
                error_type=ProgramError,
            ) from exc
    if not isinstance(value, str):
        raise syntax_error(
            f"program must be a string of source or a Path, got {type(value).__name__}",
            "pass text source or UTF-8 bytes; use pathlib.Path for a text filename",
            error_type=ProgramError,
        )
    return value


def native_text_source(source: ProgramSource | _FileSource) -> str:
    """Normalize native text line endings and remove one file terminator."""
    return (
        text_source(source).replace("\r\n", "\n").replace("\r", "\n").removesuffix("\n")
    )


def compressed_text_source(source: ProgramSource | _FileSource) -> str | CompressedText:
    """Keep gzip source compressed; accept ordinary text containers too."""
    value, _path = _read_container(source)
    if isinstance(value, CompressedText):
        return value
    if isinstance(value, bytes) and value.startswith(b"\x1f\x8b"):
        return CompressedText(value)
    return text_source(value, label=_label(source))


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


_SOURCE_LOADERS: dict[
    SourceLoader, Callable[[ProgramSource | _FileSource], Program]
] = {
    SourceLoader.TEXT: text_source,
    SourceLoader.VERBATIM: text_source,
    SourceLoader.COMPRESSED: compressed_text_source,
    SourceLoader.RASTER: raster_source,
}


def source_for(
    language: str,
    source: ProgramSource | _FileSource,
    *,
    catalog: Catalog | None = None,
    native: bool = False,
) -> Program:
    """Decode containers using declared policy without importing an interpreter."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    loader = catalog.languages[catalog.resolve(language)].runtime.source_loader
    if native and loader is SourceLoader.TEXT:
        return native_text_source(source)
    return _SOURCE_LOADERS[loader](source)


def effective_scale(
    language: str, program: object, scale: int | None, *, catalog: Catalog | None = None
) -> int | None:
    """Prefer an explicit scale, then the program artifact's metadata."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if (
        scale is None
        and isinstance(program, ProgramArtifact)
        and catalog.resolve(program.language) == catalog.resolve(language)
    ):
        return program.scale
    return scale


def check_scale_for(
    language: str, scale: int | None, *, catalog: Catalog | None = None
) -> None:
    """Validate scale using the interpreter's declared capability."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if scale is None:
        return

    check_scale(scale)
    if not catalog.languages[
        catalog.resolve(language)
    ].runtime.capabilities.supports_scale:
        raise with_hint(
            ArgumentError("scale is only supported for raster interpreters"),
            ("omit scale for text languages; apply it only to raster source"),
        )
