"""Source containers, decoded at the interpreter boundary."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, cast

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText, _freeze_compressed
from esolangs.exceptions import ArgumentError, EsolangError, ProgramError
from esolangs.outcomes import (
    _is_acquisition_failure,
    _remember_acquisition_failure,
    _track_acquisition_failures,
)
from esolangs.raster import Raster
from esolangs.raster.png import _SIGNATURE as _PNG_SIGNATURE
from esolangs.runtime._definition import SourceLoader
from esolangs.runtime._files import (
    _path_directory,
    _SourceDirectory,
    decode_utf8,
    explicit_path,
    read_snapshot,
)
from esolangs.runtime._program import Program
from esolangs.runtime._validate import _has_backing_type, check_scale
from esolangs.runtime.source_hints import (
    display_label,
    program_error_context,
    source_read_error,
    syntax_error,
    with_hint,
)

if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


type ProgramSource = Program | Artifact | bytes | os.PathLike[str] | IO[str] | IO[bytes]

_GZIP_SIGNATURE = b"\x1f\x8b"


@dataclass(frozen=True, slots=True)
class _FileSource:
    """A bounded file snapshot retaining its filename for errors."""

    path: str
    content: bytes

    def read(self) -> bytes:
        return self.content

    def __str__(self) -> str:
        return self.path


@dataclass(frozen=True, slots=True)
class _SourcePath:
    """Keep the caller's directory without binding their path provider yet."""

    argument: str | os.PathLike[str]
    directory: _SourceDirectory | None

    @classmethod
    def capture(cls, path: str | os.PathLike[str]) -> _SourcePath:
        if _has_backing_type(path, cls):
            return path
        return cls(path, _path_directory(path))

    def bind(self) -> _SourcePath:
        """Validate the explicit file argument at the public loader's boundary."""
        return _SourcePath(explicit_path(self.argument), self.directory)

    def resolve(self, spelling: str) -> str:
        return spelling if self.directory is None else self.directory.resolve(spelling)

    def __fspath__(self) -> str:
        return self.resolve(explicit_path(self.argument).spelling)


def anchor_program_source[T](source: T) -> T | _SourcePath:
    """Capture the base of path operands once, leaving other inputs untouched."""
    if issubclass(type(source), os.PathLike) and not _has_backing_type(
        source, _SourcePath
    ):
        return _SourcePath.capture(cast("os.PathLike[str]", source))
    return source


def _open_program_path(filename: str, label: str) -> IO[bytes]:
    try:
        return open(filename, "rb")
    except OSError as error:
        if (
            filename != label
            and type(error).__module__ == "builtins"
            and error.filename == filename
        ):
            # The OS names the anchored spelling. Report the caller's operand.
            error.filename = label
        raise


@_track_acquisition_failures()
def _read_container(
    source: ProgramSource | _FileSource,
) -> tuple[Program | bytes, str | None]:
    """Return the underlying data and the filename if it came from a file."""
    label = "the program"
    reading_stream = False
    try:
        if _has_backing_type(source, ProgramArtifact) or _has_backing_type(
            source, TemplateArtifact
        ):
            source = source.source
        if _has_backing_type(source, _FileSource):
            return source.read(), source.path
        if issubclass(type(source), os.PathLike):
            located = source if _has_backing_type(source, _SourcePath) else None
            argument = (
                cast("os.PathLike[str]", source)
                if located is None
                else located.argument
            )
            try:
                label = explicit_path(argument).spelling
            except ArgumentError as error:
                # Binding the operand can fail before any filesystem access.
                _remember_acquisition_failure(error)
                raise
            filename = label if located is None else located.resolve(label)
            with _open_program_path(filename, label) as file:
                return read_snapshot(file), label
        if _has_backing_type(source, Raster) or _has_backing_type(
            source, CompressedText
        ):
            return source, None
        value = source
        if not issubclass(type(source), (str, bytes)):
            label = "the program stream"
            reading_stream = True
            reader = getattr(source, "read", None)
            if callable(reader):
                value = read_snapshot(
                    cast("IO[str] | IO[bytes]", source), reader=reader
                )
        if _has_backing_type(value, str):
            return str.__str__(value), None
        if _has_backing_type(value, bytes):
            return bytes.__bytes__(value), None
    except (OSError, TypeError, ValueError) as exc:
        if _is_acquisition_failure(exc):
            raise
        if reading_stream and isinstance(exc, EsolangError):
            _remember_acquisition_failure(exc)
            raise
        raise source_read_error(label, exc) from exc
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
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
        raise program_error_context(
            f"cannot read {display_label(label)}: {error}", error
        ) from error


def check_raster_gzip(language: str, source: object) -> None:
    """Report gzip text presented to a raster language before decoding it."""
    if _has_backing_type(source, CompressedText) or (
        _has_backing_type(source, bytes) and bytes.startswith(source, _GZIP_SIGNATURE)
    ):
        raise _raster_gzip_error(language)


def _raster_gzip_error(language: str) -> ProgramError:
    return with_hint(
        ProgramError(
            f"{display_label(language)} requires raster source, "
            "but the program is gzip text"
        ),
        "use a PNG program or select the language that reads this gzip source",
    )


def _text_raster_error(language: str, actual: str) -> ProgramError:
    return with_hint(
        ProgramError(
            f"{display_label(language)} requires text source, "
            f"but the program is {actual}"
        ),
        "use text source or select the language that reads the raster",
    )


def text_source(
    source: ProgramSource | _FileSource, *, label: str | None = None
) -> str:
    """Decode UTF-8 source without changing line endings or terminators."""
    value, path = _read_container(source)
    if label is None:
        label = path
    if _has_backing_type(value, bytes) and value.startswith(_GZIP_SIGNATURE):
        value = _read_gzip(value, label)
    if _has_backing_type(value, CompressedText):
        # Construction already enforced the generation budget. plain_chars
        # limits raw export; loading an interpreter's source is not export.
        value = "".join(_freeze_compressed(value).chunks())
    if _has_backing_type(value, bytes):
        if value.startswith(_PNG_SIGNATURE):
            raise syntax_error(
                f"cannot read {display_label(label or 'the program')}: "
                "text source is required, but the program is a PNG",
                "use text source or select the language that reads the PNG",
                error_type=ProgramError,
            )
        try:
            value = decode_utf8(value)
        except UnicodeDecodeError as exc:
            raise syntax_error(
                f"cannot read {display_label(label or 'the program')}: not text "
                f"(invalid UTF-8 at byte {exc.start})",
                "save the text program as UTF-8 before running it",
                error_type=ProgramError,
            ) from exc
    if not _has_backing_type(value, str):
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
    *,
    recompress: bool = True,
) -> str | CompressedText:
    """Preserve unchanged gzip and normalize changed text for the source policy."""
    value = compressed_text_source(source)
    if _has_backing_type(value, CompressedText):
        # A measured final LF already requires a rewrite. Otherwise preserve
        # the native archive unless a carriage return needs translation.
        if value._last_character() != "\n" and not value._has_carriage_return:  # noqa: SLF001
            return value
        chunks = _native_chunks(value.chunks())
        if recompress:
            return CompressedText.from_chunks(chunks, limits=value.limits)
        return "".join(chunks)
    return native_text_source(value)


def compressed_text_source(source: ProgramSource | _FileSource) -> str | CompressedText:
    """Keep gzip source compressed; accept ordinary text containers too."""
    value, path = _read_container(source)
    if _has_backing_type(value, CompressedText):
        return _freeze_compressed(value)
    if _has_backing_type(value, bytes) and value.startswith(_GZIP_SIGNATURE):
        return _read_gzip(value, path)
    return text_source(value, label=path)


def raster_source(source: ProgramSource | _FileSource) -> Raster:
    """Load a Raster or lossless PNG bytes from any supported container."""
    value, _path = _read_container(source)
    if _has_backing_type(value, bytes):
        return Raster.from_png(value)
    if not _has_backing_type(value, Raster):
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

    name = catalog.resolve(language)
    loader = catalog.languages[name].runtime.source_loader
    if loader is SourceLoader.RASTER:
        check_raster_gzip(name, source)
    elif _has_backing_type(source, Raster):
        raise _text_raster_error(name, "a Raster")
    if native and loader is SourceLoader.TEXT:
        if preserve_compression:
            return _native_compressed_source(source, recompress=False)
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
        and _has_backing_type(program, ProgramArtifact)
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
