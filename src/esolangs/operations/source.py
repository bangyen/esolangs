"""Acquire runnable source and validate language ownership."""

from esolangs.artifacts import Artifact, ProgramArtifact, TemplateArtifact
from esolangs.exceptions import MissingDependencyError, ProgramError, TemplateError
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._input import InputSource, check_input
from esolangs.runtime._program import Program
from esolangs.runtime._source import (
    ProgramSource,
    _FileSource,
    _read_container,
    source_for,
)
from esolangs.runtime._validate import check_scale
from esolangs.settings import dialect_options


def check_origin(
    language: str, origin: object, *, catalog: "Catalog | None" = None
) -> None:
    """Reject known foreign provenance before reading a payload."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if origin is None:
        return
    if not isinstance(origin, str):
        raise ProgramError("source language must be a string")
    canonical = catalog.resolve(origin)
    if canonical != language:
        raise ProgramError(
            f"this program was generated for {canonical}, so running it as "
            f"{language} would read it as {language} source -- which may well run, "
            "and answer nonsense"
        )


def read_png_artifact(
    language: str, data: bytes, *, catalog: "Catalog | None" = None
) -> ProgramArtifact[Raster]:
    """Decode native metadata into its owning artifact, leaving pixels untagged."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.portable import decode_settings

    name = catalog.resolve(language)
    try:
        metadata = png.read_metadata(data)
        settings = None
        scale = None
        if metadata is not None:
            origin = metadata.get("language")
            if origin is not None and not isinstance(origin, str):
                raise ValueError("PNG language must be a string")
            check_origin(name, origin, catalog=catalog)
            settings = decode_settings(
                metadata.get("settings"), origin, catalog=catalog
            )
            scale = metadata.get("scale")
            if scale is not None:
                check_scale(scale)
        raster = Raster.from_png(data)
        return ProgramArtifact(raster, name, settings, scale)
    except (ProgramError, MissingDependencyError):
        raise
    except Exception as error:
        raise ProgramError(f"not a readable PNG: {error}") from error


def read_artifact(
    language: str,
    program: ProgramSource | _FileSource,
    *,
    catalog: "Catalog | None" = None,
    normalize: bool = False,
) -> Artifact:
    """Acquire source once, retaining native metadata only in an explicit record."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, (ProgramArtifact, TemplateArtifact)):
        check_origin(name, program.language, catalog=catalog)
        dialect_options(name, program.settings, catalog=catalog)
        source = source_for(name, program.source, catalog=catalog)
        if source is program.source and program.language == name:
            return program
        if isinstance(program, TemplateArtifact):
            if not isinstance(source, str):
                raise TemplateError("template source must be text")
            return TemplateArtifact(source, name, program.bindings, program.settings)
        return ProgramArtifact(
            source, name, program.settings, program.scale, program.input_arity
        )
    value, file = _read_container(program)
    if isinstance(value, bytes) and value.startswith(b"\x89PNG\r\n\x1a\n"):
        record = read_png_artifact(name, value, catalog=catalog)
        # Source-kind checking still belongs to the selected language's loader.
        source = source_for(name, record.source, catalog=catalog)
        return ProgramArtifact(source, name, record.settings, record.scale)
    # Re-wrap file bytes so a decoding error names the file, not its bytes.
    named = (
        _FileSource(str(program), value) if file and isinstance(value, bytes) else value
    )
    source = source_for(name, named, catalog=catalog, native=file and normalize)
    return ProgramArtifact(source, name)


def _read_source(
    language: str,
    program: ProgramSource | _FileSource,
    *,
    catalog: "Catalog | None" = None,
) -> Program:
    """Project source for callers that explicitly need only the payload."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return read_artifact(language, program, catalog=catalog).source


def _check_program(
    language: str,
    program: ProgramSource | _FileSource,
    stdin: InputSource = "",
    *,
    catalog: "Catalog | None" = None,
    normalize: bool = False,
) -> ProgramArtifact[Program]:
    """Acquire a runnable record without consuming stdin or parsing commands."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if isinstance(program, TemplateArtifact):
        raise TemplateError("fill the template before execution")
    record = read_artifact(name, program, catalog=catalog, normalize=normalize)
    assert isinstance(record, ProgramArtifact)
    check_input(stdin)
    return record
