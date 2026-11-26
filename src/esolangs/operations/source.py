"""Public constructors for owned program source."""

from os import PathLike

from esolangs.artifacts import ProgramArtifact, bind_catalog
from esolangs.exceptions import EsolangError, ProgramError
from esolangs.registry._catalog import Catalog
from esolangs.runtime._artifact_source import read_source_artifact
from esolangs.runtime._program import Program
from esolangs.runtime._source import _SourcePath, source_for
from esolangs.runtime._validate import _has_backing_type, check_flag
from esolangs.runtime.source_hints import source_read_error
from esolangs.settings import DialectSettings, dialect_options, effective_settings


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
    return bind_catalog(artifact, catalog)


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
    language's native file newline policy. Imports retain the original
    gzip bytes when the source text is unchanged. PNG can retain the
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
    artifact = read_source_artifact(
        name,
        source,
        settings=settings,
        catalog=catalog,
        normalize=normalize,
        preserve_compression=True,
    )
    return bind_catalog(artifact, catalog)
