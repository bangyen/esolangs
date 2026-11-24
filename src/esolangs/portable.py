"""Native source files and versioned JSON programs."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterable, Iterator
from contextlib import ExitStack
from dataclasses import asdict, replace
from os import PathLike
from typing import Any, Protocol, cast

from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import (
    CompressedText,
    TextLimits,
    _check_plain,
    _normalize_limits,
)
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    GeneratorCapError,
    ProgramError,
    TemplateError,
)
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._files import decode_utf8, destination_path, reserve_staged
from esolangs.runtime._json import check_record_utf8, record_dumps, record_loads
from esolangs.runtime._source import (
    ProgramSource,
    _raster_gzip_error,
    anchor_program_source,
    native_file_terminator,
    source_for,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import (
    display_label,
    program_error_context,
    with_hint,
)
from esolangs.settings import (
    DialectSettings,
    _settings_record,
    dialect_options,
    effective_settings,
)

_FORMAT = "esolangs.program"


def _portable_record_owner(data: bytes) -> str | None:
    """Read the envelope's language before resolving it or loading its source."""
    if _FORMAT.encode("ascii") not in data and b"\\u" not in data:
        return None
    try:
        value = record_loads(decode_utf8(data))
    except (ValueError, RecursionError):
        return None
    if (
        isinstance(value, dict)
        and value.get("format") == _FORMAT
        and type(value.get("version")) is int
        and value.get("kind") in ("text", "png", "gzip", "template")
        and isinstance(value.get("source"), str)
        and "settings" in value
        and isinstance(owner := value.get("language"), str)
    ):
        return owner
    return None


class _ArtifactLanguageMismatchError(ValueError):
    def __init__(self, requested: str, owner: str) -> None:
        super().__init__(
            f"program language must be {display_label(requested)}"
            f"; artifact records {display_label(owner)}"
        )
        self.owner = owner


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
    Use :func:`to_json` to retain text artifacts' settings
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
    from esolangs.operations.source import read_artifact

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


def to_json(
    language: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None = None,
    catalog: Catalog | None = None,
) -> str:
    """Return version-1 JSON preserving source, choices, and Boolean bindings.

    Raster pixels are embedded as base64 PNG. Integer choices use hexadecimal
    strings, including values beyond Python's decimal conversion limit.
    If the PNG metadata exceeds its native limit, the document carries the
    settings and any explicit scale alongside an untagged image.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``settings`` is invalid for the language.
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: ``program`` cannot be read or a supplied setting
            conflicts with a retained one.
        MissingDependencyError: A raster needs ``esolangs[image]`` for PNG.
    """
    from esolangs.registry._catalog import get_catalog

    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    from esolangs.operations.source import read_artifact

    name = catalog.resolve(language)
    artifact = read_artifact(
        name, program, settings=settings, catalog=catalog, preserve_compression=True
    )
    settings = artifact.settings
    encoded = (
        None
        if settings is None
        else {
            key: {"integer": hex(value)} if type(value) is int else value
            for key, value in DialectSettings.options(settings).items()
        }
    )
    document: dict[str, Any] = {
        "format": _FORMAT,
        "version": 1,
        "language": name,
        "settings": encoded,
    }
    if not _has_backing_type(artifact, ProgramArtifact):
        _require_template_capability(name, catalog=catalog)
        template = cast("TemplateArtifact", artifact)
        document.update(
            kind="template",
            source=template.source,
            char=template.bindings.char,
            setters=template.bindings.setters,
            spans=template.spans,
        )
        if template.generation_width is not None:
            document["generation_width"] = template.generation_width
    else:
        if artifact.input_arity is not None:
            document["input_arity"] = artifact.input_arity
        body = artifact.source
        if _has_backing_type(body, Raster):
            image = png.write_rgb(body.rows)
            try:
                image = png.attach_source_metadata(
                    image, name, settings, artifact.scale
                )
            except png.SourceMetadataSizeError:
                if artifact.scale is not None:
                    document["scale"] = artifact.scale
            document.update(
                kind="png",
                source=base64.b64encode(image).decode("ascii"),
            )
        elif _has_backing_type(body, CompressedText):
            limits = _normalize_limits(body.limits)
            document.update(
                kind="gzip",
                source=base64.b64encode(body.to_gzip()).decode("ascii"),
                limits=asdict(limits) if limits is not None else None,
            )
        else:
            document.update(kind="text", source=str(body))
    try:
        check_record_utf8(document)
    except UnicodeEncodeError as error:
        raise ProgramError(f"program is not valid UTF-8 text: {error}") from error
    return record_dumps(document, sort_keys=True)


def _decode_settings(
    value: Any,
    language: str | None,
    *,
    catalog: Catalog,
    checked_settings: DialectSettings | None = None,
) -> DialectSettings | None:
    """Restore saved choices against a schema without calling its dialect."""
    if value is None:
        return None
    choices = _decode_settings_choices(value)
    if language is None:
        raise ValueError("settings need a language to apply to")
    if (
        checked_settings is not None
        and checked_settings._schema.language == language  # noqa: SLF001
        and all(type(item) in (int, str) for item in choices.values())
        and choices == DialectSettings.options(checked_settings)
    ):
        return checked_settings
    return _settings_record(catalog.resolve(language), choices, catalog=catalog)


def _decode_settings_choices(value: Any) -> dict[str, Any]:
    """Decode settings payloads without binding or invoking a dialect."""
    if not isinstance(value, dict):
        raise ValueError("settings must be an object or null")
    choices: dict[str, Any] = {}
    for key, saved in value.items():
        if type(saved) is int:
            raise ValueError("integer settings need a hexadecimal string")
        item = saved
        if isinstance(item, dict):
            if set(item) != {"integer"} or not isinstance(item["integer"], str):
                raise ValueError("integer settings need a hexadecimal string")
            literal = item["integer"]
            if not literal.startswith(("0x", "-0x")):
                raise ValueError("integer settings need a hexadecimal string")
            item = int(literal, 16)
        choices[key] = item
    return choices


def _load_png(
    value: dict[str, Any],
    name: str,
    *,
    catalog: Catalog,
) -> ProgramArtifact[Raster]:
    """Restore a ``png`` document's raster."""
    from esolangs.operations.source import positive_metadata_field, read_png_source

    arity = positive_metadata_field(value, "input_arity")
    scale = positive_metadata_field(value, "scale")
    data = base64.b64decode(value["source"], validate=True)
    scan, (png_settings, png_scale, png_arity) = read_png_source(
        name, data, catalog=catalog
    )
    settings = _decode_settings(value["settings"], name, catalog=catalog)
    # Native writers use null for settings and scale they do not supply.
    if png_settings is not None and png_settings != settings:
        raise ValueError("conflicting PNG and document settings")
    if scale is None:
        scale = png_scale
    elif png_scale is not None and png_scale != scale:
        raise ValueError("conflicting PNG and document scale")
    if arity is None:
        arity = png_arity
    elif png_arity is not None and png_arity != arity:
        raise ValueError("conflicting PNG and document input_arity")
    dialect_options(name, settings, catalog=catalog)
    return ProgramArtifact(
        Raster._from_png(scan),  # noqa: SLF001 - reuse the validated chunk scan
        name,
        settings=settings,
        scale=scale,
        input_arity=arity,
    )


def _load_gzip(
    value: dict[str, Any],
    name: str,
    settings: DialectSettings | None,
    *,
    catalog: Catalog | None = None,
) -> ProgramArtifact[CompressedText]:
    """Restore a ``gzip`` document's compressed text."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if catalog.languages[name].runtime.source_kind is SourceKind.RASTER:
        raise _raster_gzip_error(name)
    limits = value["limits"]
    if limits is not None:
        if not isinstance(limits, dict) or set(limits) != {
            "plain_chars",
            "generation_chars",
            "gzip_bytes",
        }:
            raise ValueError("invalid compressed text limits")
        limits = TextLimits(**limits)
    return ProgramArtifact(
        CompressedText(base64.b64decode(value["source"], validate=True), limits=limits),
        name,
        settings=settings,
    )


def _load_text(
    value: dict[str, Any],
    name: str,
    settings: DialectSettings | None,
    *,
    catalog: Catalog | None = None,
) -> ProgramArtifact[str]:
    """Restore a ``text`` document's source."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return ProgramArtifact(value["source"], name, settings=settings)


def _require_template_capability(name: str, *, catalog: Catalog) -> None:
    """Accept explicit markers where the selected language embeds its inputs."""
    if not catalog.languages[name].parameterized:
        raise ProgramError(f"{display_label(name)} does not support input templates")


def _load_template(
    value: dict[str, Any],
    name: str,
    settings: DialectSettings | None,
    *,
    catalog: Catalog | None = None,
) -> TemplateArtifact:
    """Restore a ``template`` document's template and setters."""
    from esolangs.operations.source import positive_metadata_field
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if not isinstance(value["char"], str) or len(value["char"]) != 1:
        raise ValueError("template char must be one character")
    _require_template_capability(name, catalog=catalog)
    width = positive_metadata_field(value, "generation_width")
    pairs = value["setters"]
    if not isinstance(pairs, list) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(item, str) for item in pair)
        for pair in pairs
    ):
        raise ValueError("setters must be pairs of strings")
    raw = value["spans"]
    if not isinstance(raw, list) or any(
        not isinstance(span, list)
        or len(span) != 2
        or any(type(offset) is not int for offset in span)
        for span in raw
    ):
        raise ValueError("template spans must be pairs of offsets")
    spans = tuple((start, end) for start, end in raw)
    return TemplateArtifact(
        value["source"],
        name,
        TemplateBindings(char=value["char"], setters=tuple(pairs)),
        settings=settings,
        spans=spans,
        generation_width=width,
    )


class _Loader(Protocol):
    def __call__(
        self,
        value: dict[str, Any],
        name: str,
        settings: DialectSettings | None,
        *,
        catalog: Catalog | None = None,
    ) -> Artifact: ...


#: Source-kind dispatch for :func:`from_json`.
_LOADERS: dict[str, _Loader] = {
    "gzip": _load_gzip,
    "text": _load_text,
    "template": _load_template,
}


@_track_acquisition_failures()
def from_json(
    language: str, document: str, *, catalog: Catalog | None = None
) -> Artifact:
    """Restore version-1 JSON as an explicit program or template record.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``document`` is not a string.
        ProgramError: ``document`` is not a valid version-1 program for
            ``language``, including invalid settings.
        MissingDependencyError: A PNG source needs ``esolangs[image]``.
    """
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)
    from esolangs.operations.source import positive_metadata_field

    name = catalog.resolve(language)
    if not _has_backing_type(document, str):
        raise ArgumentError("document must be a JSON string")
    try:
        value = record_loads(document)
        if not isinstance(value, dict):
            raise ValueError("document must be an object")
        fields = {"format", "version", "language", "settings", "kind", "source"}
        kind = value.get("kind")
        if kind == "gzip":
            fields.add("limits")
        if kind == "png" and "scale" in value:
            fields.add("scale")
        if kind == "template":
            fields |= {"char", "setters", "spans"}
            if "generation_width" in value:
                fields.add("generation_width")
        elif "input_arity" in value:
            fields.add("input_arity")
        if set(value) != fields:
            raise ValueError("unexpected or missing fields")
        if (
            value["format"] != _FORMAT
            or type(value["version"]) is not int
            or value["version"] != 1
        ):
            raise ValueError("unsupported program format or version")
        origin = value["language"]
        owner = (
            resolve_origin(origin, catalog=catalog) if isinstance(origin, str) else None
        )
        if owner is None:
            raise ValueError(f"program language must be {display_label(name)}")
        if owner != name:
            raise _ArtifactLanguageMismatchError(name, owner)
        if not isinstance(value["source"], str):
            raise ValueError("source must be a string")
        # Strict UTF-8 everywhere, as a program file is read: a JSON
        # "\ud800" escape in the source or a setter loaded a lone surrogate.
        check_record_utf8(value)
        if kind == "png":
            artifact: Artifact = _load_png(value, name, catalog=catalog)
        else:
            if not isinstance(kind, str) or kind not in _LOADERS:
                raise ValueError("unknown source kind")
            arity = positive_metadata_field(value, "input_arity")
            settings = _decode_settings(value["settings"], name, catalog=catalog)
            artifact = _LOADERS[kind](value, name, settings, catalog=catalog)
            if isinstance(artifact, ProgramArtifact) and arity is not None:
                artifact = replace(artifact, input_arity=arity)
        source_for(name, artifact.source, catalog=catalog, preserve_compression=True)
        if kind != "png":
            dialect_options(name, artifact.settings, catalog=catalog)
        return artifact
    except (ValueError, TypeError, RecursionError) as error:
        if _is_acquisition_failure(error):
            raise
        # A path or native source here is the usual mistake (dogfood, 2.0.0).
        hint = (
            "; from_json reads to_json JSON text, not a path; "
            "load a native file with Language(name).from_file(path)"
            if isinstance(error, json.JSONDecodeError)
            else ""
        )
        raise program_error_context(
            f"invalid portable program: {error}{hint}", error
        ) from error
