"""Acquire runnable source and validate language ownership."""

from os import PathLike
from typing import Any

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import (
    EsolangError,
    MissingDependencyError,
    ProgramError,
    TemplateError,
)
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._program import Program
from esolangs.runtime._source import (
    ProgramSource,
    _FileSource,
    _read_container,
    _SourcePath,
    anchor_program_source,
    check_raster_gzip,
    source_for,
)
from esolangs.runtime._validate import _has_backing_type, check_flag, check_scale
from esolangs.runtime.source_hints import program_error_context, source_read_error
from esolangs.settings import (
    DialectSettings,
    _merge_settings,
    dialect_options,
    effective_settings,
)


def check_origin(
    language: str, origin: object, *, catalog: "Catalog | None" = None
) -> None:
    """Reject foreign provenance before reading a payload."""
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)
    if origin is None:
        return
    if not _has_backing_type(origin, str):
        raise ProgramError("source language must be a string")
    canonical = resolve_origin(origin, catalog=catalog)
    if canonical != language:
        raise ProgramError(
            f"this program was generated for {canonical or origin}, not {language}; "
            f"read as {language} source it may well run, and answer nonsense"
        )


def positive_metadata_field(value: dict[str, Any], key: str) -> int | None:
    """Read optional positive integer metadata, refusing an explicit null."""
    if key not in value:
        return None
    field = value[key]
    if type(field) is not int or field < 1:
        raise ValueError(f"{key} must be a positive integer")
    return field


def read_png_artifact(
    language: str,
    data: bytes,
    *,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
) -> ProgramArtifact[Raster]:
    """Decode native metadata into its owning artifact, leaving pixels untagged."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    _, retained, scale, arity = read_png_metadata(name, data, catalog=catalog)
    merged = _merge_settings(name, retained, settings, catalog=catalog)
    return ProgramArtifact(
        Raster.from_png(data), name, settings=merged, scale=scale, input_arity=arity
    )


@_track_acquisition_failures()
def read_png_metadata(
    name: str, data: bytes, *, catalog: Catalog
) -> tuple[dict[str, Any], DialectSettings | None, int | None, int | None]:
    """Validate native source claims without opening the image."""
    from esolangs.portable import decode_settings

    if catalog.languages[name].runtime.source_kind is not SourceKind.RASTER:
        raise ProgramError(f"{name} requires text source, but the program is a PNG")
    check_raster_gzip(name, data)
    try:
        metadata = png.read_metadata(data)
        if metadata is None:
            return {}, None, None, None
        origin = metadata.get("language")
        if origin is not None and not isinstance(origin, str):
            raise ValueError("PNG language must be a string")
        check_origin(name, origin, catalog=catalog)
        settings = decode_settings(
            metadata.get("settings"), None if origin is None else name, catalog=catalog
        )
        scale = metadata.get("scale")
        scale = None if scale is None else check_scale(scale)
        arity = positive_metadata_field(metadata, "input_arity")
        return metadata, settings, scale, arity
    except (ProgramError, MissingDependencyError):
        raise
    except Exception as error:
        if _is_acquisition_failure(error):
            raise
        raise program_error_context(f"not a readable PNG: {error}", error) from error


def read_artifact(
    language: str,
    program: ProgramSource | _FileSource,
    *,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
    normalize: bool = False,
    preserve_compression: bool = False,
) -> Artifact:
    """Acquire source once, merging explicit choices with the retained settings."""
    from esolangs.registry._catalog import get_catalog

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings = effective_settings(name, program, settings, catalog=catalog)
    if _has_backing_type(program, ProgramArtifact) or _has_backing_type(
        program, TemplateArtifact
    ):
        check_origin(name, program.language, catalog=catalog)
        source = source_for(
            name,
            program.source,
            catalog=catalog,
            preserve_compression=preserve_compression,
        )
        if (
            source is program.source
            and program.language == name
            and settings is program.settings
        ):
            return program
        if isinstance(program, TemplateArtifact):
            if not isinstance(source, str):
                raise TemplateError("template source must be text")
            return TemplateArtifact(
                source,
                name,
                program.bindings,
                settings=settings,
                spans=program.spans,
            )
        return ProgramArtifact(
            source,
            name,
            settings=settings,
            scale=program.scale,
            input_arity=program.input_arity,
        )
    value, path = _read_container(program)
    if isinstance(value, bytes) and (
        value.startswith(b"\x89PNG\r\n\x1a\n")
        or catalog.languages[name].runtime.source_kind is SourceKind.RASTER
    ):
        with _track_acquisition_failures():
            try:
                return read_png_artifact(
                    name, value, settings=settings, catalog=catalog
                )
            except ProgramError as error:
                if (
                    path is None
                    or type(error) is not ProgramError
                    or _is_acquisition_failure(error)
                ):
                    raise
                raise program_error_context(
                    f"cannot read {path}: {error}", error
                ) from error
    # Re-wrap file bytes so a decoding error names the file, not its bytes.
    named = (
        _FileSource(path, value)
        if path is not None and isinstance(value, bytes)
        else value
    )
    source = source_for(
        name,
        named,
        catalog=catalog,
        native=path is not None and normalize,
        preserve_compression=preserve_compression,
    )
    return ProgramArtifact(source, name, settings=settings)


def _check_program(
    language: str,
    program: ProgramSource | _FileSource,
    stdin: InputSource = "",
    *,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
    normalize: bool = False,
    preserve_compression: bool = False,
) -> ProgramArtifact[Program]:
    """Acquire a runnable record without consuming stdin or parsing commands."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if _has_backing_type(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    record = read_artifact(
        name,
        program,
        settings=settings,
        catalog=catalog,
        normalize=normalize,
        preserve_compression=preserve_compression,
    )
    assert isinstance(record, ProgramArtifact)
    # Check the combined choices only after native metadata could add an override.
    dialect_options(name, record.settings, catalog=catalog, validate_defaults=True)
    check_input(stdin)
    return record


def from_source(
    language: str,
    source: Program,
    *,
    settings: DialectSettings | None = None,
    catalog: "Catalog | None" = None,
) -> ProgramArtifact[Program]:
    """Declare runnable source, including text that resembles a filename.

    Parsing happens on execution. Use ``from_file`` to read native source.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        TemplateError: Source is an unfilled template.
        ProgramError: Source has an unsupported type or does not match the
            language's source kind.
        ArgumentError: Dialect settings are invalid for this language.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if _has_backing_type(source, ProgramArtifact):
        raise ProgramError(
            f"from_source takes source, not a {source.language} artifact; "
            "pass its .source"
        )
    retained = effective_settings(name, source, settings, catalog=catalog)
    artifact = ProgramArtifact(source, name, settings=retained)
    source_for(name, artifact.source, catalog=catalog, preserve_compression=True)
    return artifact


def from_file(
    language: str,
    path: "str | PathLike[str]",
    *,
    settings: DialectSettings | None = None,
    normalize: bool = False,
    catalog: "Catalog | None" = None,
) -> ProgramArtifact[Program]:
    """Read lossless source with retained metadata.

    Gzip and PNG are detected by content. ``normalize=True`` applies the
    language's native file newline policy. Imports without newline
    processing retain the original gzip bytes. PNG can retain the
    input arity and canonical owner.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: Settings or the path argument are invalid.
        ProgramNotFoundError: The source file does not exist.
        ProgramError: Source cannot be decoded or belongs to another language.
        MissingDependencyError: PNG loading needs the image extra.
    """
    from esolangs.registry._catalog import get_catalog

    captured = _SourcePath.capture(path)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    check_flag(normalize, "normalize")
    dialect_options(name, settings, catalog=catalog)
    try:
        source = captured.bind()
    except EsolangError:
        raise
    except OSError as error:
        raise source_read_error("the program", error) from error
    artifact = read_artifact(
        name,
        source,
        settings=settings,
        catalog=catalog,
        normalize=normalize,
        preserve_compression=True,
    )
    assert isinstance(artifact, ProgramArtifact)
    return artifact
