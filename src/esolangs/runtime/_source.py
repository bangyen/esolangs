"""Source containers, decoded at the interpreter boundary."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ProgramError,
    ProgramNotFoundError,
)
from esolangs.raster import Raster
from esolangs.runtime._definition import SourceLoader
from esolangs.runtime._files import explicit_path, read_snapshot
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_scale
from esolangs.runtime.source_hints import program_error_context, syntax_error, with_hint

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
) -> tuple[Program | bytes, str | None]:
    """Return the underlying data and the filename if it came from a file."""
    label = "the program"
    reading_stream = False
    try:
        if isinstance(source, (ProgramArtifact, TemplateArtifact)):
            source = source.source
        if isinstance(source, _FileSource):
            return source.read(), source.path
        if isinstance(source, os.PathLike):
            path = explicit_path(source)
            label = str(path)
            with open(path, "rb") as file:
                return read_snapshot(file), label
        if isinstance(source, (Raster, CompressedText)):
            return source, None
        value = source
        if not isinstance(source, (str, bytes)):
            label = "the program stream"
            reading_stream = True
            reader = getattr(source, "read", None)
            if callable(reader):
                value = read_snapshot(source, reader=reader)
        if isinstance(value, str):
            return str.__str__(value), None
        if isinstance(value, bytes):
            return bytes.__bytes__(value), None
    except (OSError, TypeError, ValueError) as exc:
        if reading_stream and isinstance(exc, EsolangError):
            raise
        if isinstance(exc, FileNotFoundError):
            raise syntax_error(
                f"cannot read {label}: {exc}",
                "check that the source path exists and names the intended program file",
                error_type=ProgramNotFoundError,
            ) from exc
        raise syntax_error(
            f"cannot read {label}: {exc}",
            "check that the program file or stream is readable",
            error_type=ProgramError,
        ) from exc
    raise syntax_error(
        "program must be a string of source, bytes, a Raster, a Path, "
        f"or a readable stream, got {type(source).__name__}",
        "pass source text or bytes; use pathlib.Path for a program filename",
        error_type=ProgramError,
    )


def _read_gzip(data: bytes, label: str | None) -> CompressedText:
    """Validate compressed source with its optional native filename."""
    try:
        return CompressedText(data)
    except ProgramError as error:
        if label is None:
            raise
        raise program_error_context(f"cannot read {label}: {error}", error) from error


def text_source(
    source: ProgramSource | _FileSource, *, label: str | None = None
) -> str:
    """Decode UTF-8 source without changing line endings or terminators."""
    value, path = _read_container(source)
    if label is None:
        label = path
    if isinstance(value, bytes) and value.startswith(b"\x1f\x8b"):
        value = _read_gzip(value, label)
    if isinstance(value, CompressedText):
        # Construction already enforced the generation budget. plain_chars
        # limits raw export; loading an interpreter's source is not export.
        value = "".join(value.chunks())
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise syntax_error(
                f"cannot read {label or 'the program'}: not text "
                f"(invalid UTF-8 at byte {exc.start})",
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


def native_file_terminator(text: str) -> str:
    """Append a terminator without merging it into a final source CR."""
    return "\r\n" if text.endswith("\r") else "\n"


def _native_chunks(chunks: Iterable[str]) -> Iterator[str]:
    """Normalize line endings across chunks and drop one final terminator."""
    pending = ""
    for chunk in chunks:
        text = pending + chunk
        split = -2 if text.endswith("\r\n") else -1
        pending = text[split:]
        yield text[:split].replace("\r\n", "\n").replace("\r", "\n")
    yield pending.replace("\r\n", "\n").replace("\r", "\n").removesuffix("\n")


def _native_compressed_source(
    source: ProgramSource | _FileSource,
) -> str | CompressedText:
    """Normalize a gzip-native language without expanding it into one string."""
    value = compressed_text_source(source)
    if isinstance(value, CompressedText):
        return CompressedText.from_chunks(
            _native_chunks(value.chunks()), limits=value.limits
        )
    return native_text_source(value)


def compressed_text_source(source: ProgramSource | _FileSource) -> str | CompressedText:
    """Keep gzip source compressed; accept ordinary text containers too."""
    value, path = _read_container(source)
    if isinstance(value, CompressedText):
        return value
    if isinstance(value, bytes) and value.startswith(b"\x1f\x8b"):
        return _read_gzip(value, path)
    return text_source(value, label=path)


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
    preserve_compression: bool = False,
) -> Program:
    """Decode containers using declared policy without importing an interpreter."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    loader = catalog.languages[catalog.resolve(language)].runtime.source_loader
    if native and loader is SourceLoader.TEXT:
        return native_text_source(source)
    if native and loader is SourceLoader.COMPRESSED:
        return _native_compressed_source(source)
    if preserve_compression and loader is not SourceLoader.RASTER:
        return compressed_text_source(source)
    return _SOURCE_LOADERS[loader](source)


def effective_scale(
    language: str, program: object, scale: int | None, *, catalog: Catalog | None = None
) -> int | None:
    """Prefer an explicit scale, then the program artifact's metadata."""
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)
    if (
        scale is None
        and isinstance(program, ProgramArtifact)
        and resolve_origin(program.language, catalog=catalog)
        == catalog.resolve(language)
    ):
        return program.scale
    return None if scale is None else check_scale(scale)


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
