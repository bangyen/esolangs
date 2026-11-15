"""Acquire runnable source and validate language ownership."""

from os import PathLike
from typing import Any

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import (
    MissingDependencyError,
    ProgramError,
    TemplateError,
)
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._files import explicit_path
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._program import Program
from esolangs.runtime._source import (
    ProgramSource,
    _FileSource,
    _read_container,
    source_for,
)
from esolangs.runtime._validate import check_flag, check_scale
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
    if not isinstance(origin, str):
        raise ProgramError("source language must be a string")
    canonical = resolve_origin(origin, catalog=catalog)
    if canonical != language:
        raise ProgramError(
            f"this program was generated for {canonical or origin}, not {language}; "
            f"read as {language} source it may well run, and answer nonsense"
        )


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
    _, retained, scale = read_png_metadata(name, data, catalog=catalog)
    merged = _merge_settings(name, retained, settings, catalog=catalog)
    return ProgramArtifact(Raster.from_png(data), name, settings=merged, scale=scale)


def read_png_metadata(
    name: str, data: bytes, *, catalog: Catalog
) -> tuple[dict[str, Any], DialectSettings | None, int | None]:
    """Validate native source claims without opening the image."""
    from esolangs.portable import decode_settings

    if catalog.languages[name].runtime.source_kind is not SourceKind.RASTER:
        raise ProgramError(f"{name} requires text source, but the program is a PNG")
    try:
        metadata = png.read_metadata(data)
        if metadata is None:
            return {}, None, None
        origin = metadata.get("language")
        if origin is not None and not isinstance(origin, str):
            raise ValueError("PNG language must be a string")
        check_origin(name, origin, catalog=catalog)
        settings = decode_settings(metadata.get("settings"), origin, catalog=catalog)
        scale = metadata.get("scale")
        return metadata, settings, None if scale is None else check_scale(scale)
    except (ProgramError, MissingDependencyError):
        raise
    except Exception as error:
        failure = ProgramError(f"not a readable PNG: {error}")
        for note in getattr(error, "__notes__", ()):
            failure.add_note(note)
        raise failure from error


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

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings = effective_settings(name, program, settings, catalog=catalog)
    if isinstance(program, (ProgramArtifact, TemplateArtifact)):
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
        return read_png_artifact(name, value, settings=settings, catalog=catalog)
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
) -> ProgramArtifact[Program]:
    """Acquire a runnable record without consuming stdin or parsing commands."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    record = read_artifact(
        name, program, settings=settings, catalog=catalog, normalize=normalize
    )
    assert isinstance(record, ProgramArtifact)
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
    if isinstance(source, ProgramArtifact):
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
    language's native file newline policy.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: Settings or the path argument are invalid.
        ProgramNotFoundError: The source file does not exist.
        ProgramError: Source cannot be decoded or belongs to another language.
        MissingDependencyError: PNG loading needs the image extra.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    check_flag(normalize, "normalize")
    dialect_options(name, settings, catalog=catalog)
    artifact = read_artifact(
        name,
        explicit_path(path),
        settings=settings,
        catalog=catalog,
        normalize=normalize,
    )
    assert isinstance(artifact, ProgramArtifact)
    return artifact
