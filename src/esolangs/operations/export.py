"""Encode and publish native program files."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack
from os import PathLike
from typing import cast

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.compressed import CompressedText, TextLimits, _check_plain
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    GeneratorCapError,
    ProgramError,
    TemplateError,
)
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._files import destination_path
from esolangs.runtime._publish import reserve_staged
from esolangs.runtime._source import (
    ProgramSource,
    anchor_program_source,
    native_file_terminator,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import display_label, with_hint
from esolangs.settings import DialectSettings, effective_settings


def _terminated_text(
    chunks: Iterable[str], *, plain_limits: TextLimits | None = None
) -> Iterator[str]:
    """Append one native separator and count it against the plain export cap."""
    tail = ""
    size = 0
    for chunk in chunks:
        if chunk:
            tail = chunk[-1]
            size += len(chunk)
        yield chunk
    ending = native_file_terminator(tail)
    if plain_limits is not None:
        _check_plain(plain_limits, size + len(ending))
    yield ending


def _native_file_bytes(
    record: Artifact, *, gzip: bool, terminate: bool
) -> Iterable[bytes]:
    """Encode a native file, retaining gzip bytes when no conversion is needed."""
    if not _has_backing_type(record, ProgramArtifact):
        raise with_hint(
            TemplateError(
                "a template's native file would run with its placeholders unfilled"
            ),
            "fill it with instantiate() first, or keep the bindings with to_json()",
        )
    body = record.source
    if _has_backing_type(body, Raster):
        if gzip:
            raise ProgramError("gzip export requires text; rasters use PNG")
        return (
            png.write_source(
                body.rows,
                record.language,
                record.settings,
                record.scale,
                input_arity=record.input_arity,
            ),
        )
    limits = None
    chunks: Iterable[str]
    if _has_backing_type(body, CompressedText):
        if gzip and not terminate:
            return (body.to_gzip(),)
        limits = body.limits
        chunks = body.chunks() if gzip else body.plain_chunks()
        if terminate and not gzip and limits is not None:
            _check_plain(limits, len(body) + 1)
    else:
        chunks = (cast("str", body),)
    if terminate:
        chunks = _terminated_text(chunks, plain_limits=None if gzip else limits)
    if gzip:
        return (CompressedText.from_chunks(chunks, limits=limits).to_gzip(),)
    return (chunk.encode("utf-8") for chunk in chunks)


def to_file(
    language: str,
    program: ProgramSource,
    path: str | PathLike[str],
    *,
    settings: DialectSettings | None = None,
    gzip: bool = False,
    normalize: bool = False,
    catalog: Catalog | None = None,
) -> None:
    """Write a program as a native source file.

    Text retains its UTF-8 bytes and line endings, and rasters are PNG.
    ``gzip=True`` writes gzip. ``gzip=False`` writes plain text.
    Compression is explicit; a ``.gz`` suffix alone does not enable it.
    ``normalize=True`` appends one native file terminator where permitted,
    including gzip exports. Native import normalizes line endings to LF and
    removes the added terminator.
    An existing file is replaced after encoding and writing succeed.
    ``settings`` can add choices to an artifact's retained settings.
    PNG metadata records the result and any input arity.
    Use :func:`esolangs.to_json` to retain text artifacts' settings
    and input arity or to preserve templates with their setters.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``gzip`` or ``normalize`` is not a Boolean flag,
            ``path`` is not a str or PathLike, or is empty, or ``settings``
            is invalid for the language.
        TemplateError: ``program`` is an unfilled template.
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: The record belongs to another language, a supplied
            setting conflicts with a retained one, the source cannot be read
            or encoded, or the file cannot be written.
        GeneratorCapError: Plain text exceeds its raw-export budget, or
            adding a native terminator exceeds its generation or gzip budget.
        MissingDependencyError: A raster needs ``esolangs[image]`` for PNG.
    """
    from esolangs.registry._catalog import get_catalog

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    if type(gzip) is not bool:
        raise ArgumentError("gzip must be a boolean")
    if type(normalize) is not bool:
        raise ArgumentError("normalize must be a boolean")
    try:
        target = destination_path(path)
    except EsolangError:
        raise
    except OSError as error:
        raise ProgramError(f"cannot save program: {error}") from error
    from esolangs.runtime._artifact_source import read_artifact

    # The language decides the file terminator and PNG metadata; without it,
    # normalize appended "\n" even where a trailing newline is code.
    origin = catalog.resolve(language)
    runtime = catalog.languages[origin].runtime
    with ExitStack() as reservation:
        # Paths can open a FIFO, and a reader can consume bytes irreversibly.
        kind = type(program)
        consumes_source = issubclass(kind, PathLike) or not issubclass(
            kind,
            (str, bytes, Raster, CompressedText, ProgramArtifact, TemplateArtifact),
        )
        if consumes_source and gzip and runtime.source_kind is SourceKind.RASTER:
            effective_settings(origin, program, settings, catalog=catalog)
            raise ProgramError("gzip export requires text; rasters use PNG")
        publish: Callable[[Iterable[bytes]], None] | None = None
        unavailable: OSError | ValueError | None = None
        try:
            publish = reservation.enter_context(reserve_staged(target))
        except (OSError, ValueError) as error:
            if consumes_source:
                effective_settings(origin, program, settings, catalog=catalog)
                raise ProgramError(
                    f"cannot save program to {display_label(target.spelling)}: {error}"
                ) from error
            # A materialized source's immediate validation failures still win.
            unavailable = error
        record = read_artifact(
            origin,
            program,
            settings=settings,
            catalog=catalog,
            preserve_compression=True,
        )
        try:
            chunks = _native_file_bytes(
                record, gzip=gzip, terminate=normalize and runtime.file_newline
            )
            if unavailable is not None:
                raise unavailable
            assert publish is not None
            publish(chunks)
        except (GeneratorCapError, ProgramError, TemplateError):
            raise
        except (OSError, TypeError, ValueError) as error:
            raise ProgramError(
                f"cannot save program to {display_label(target.spelling)}: {error}"
            ) from error
