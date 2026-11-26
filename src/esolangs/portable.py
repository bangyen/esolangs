"""Versioned JSON programs."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, replace
from typing import Any, Protocol, cast

from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
    bind_catalog,
)
from esolangs.compressed import (
    CompressedText,
    TextLimits,
    _normalize_limits,
)
from esolangs.exceptions import (
    ArgumentError,
    ProgramError,
)
from esolangs.operations.export import to_file as to_file
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.raster import Raster, png
from esolangs.registry._catalog import Catalog
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._json import check_record_utf8, record_dumps, record_loads
from esolangs.runtime._source import (
    ProgramSource,
    _raster_gzip_error,
    anchor_program_source,
    source_for,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import (
    display_label,
    program_error_context,
)
from esolangs.settings import (
    DialectSettings,
    _decode_settings,
    dialect_options,
)

_FORMAT = "esolangs.program"


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
    from esolangs.runtime._artifact_source import read_artifact

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
        if template.generation_balance is not None:
            document["generation_balance"] = template.generation_balance
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
        # The check ``from_json`` makes: a lone surrogate dumped as a
        # ``\ud800`` escape, which it then refused.
        record_dumps(document, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProgramError(f"program is not valid UTF-8 text: {error}") from error
    return record_dumps(document, sort_keys=True)


def _load_png(
    value: dict[str, Any],
    name: str,
    *,
    catalog: Catalog,
) -> ProgramArtifact[Raster]:
    """Restore a ``png`` document's raster."""
    from esolangs.runtime._artifact_source import (
        positive_metadata_field,
        read_png_metadata,
    )

    arity = positive_metadata_field(value, "input_arity")
    scale = positive_metadata_field(value, "scale")
    data = base64.b64decode(value["source"], validate=True)
    png_settings, png_scale, png_arity = read_png_metadata(name, data, catalog=catalog)
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
        Raster.from_png(data), name, settings=settings, scale=scale, input_arity=arity
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
    from esolangs.registry._catalog import get_catalog
    from esolangs.runtime._artifact_source import positive_metadata_field

    catalog = get_catalog(catalog)
    if not isinstance(value["char"], str) or len(value["char"]) != 1:
        raise ValueError("template char must be one character")
    _require_template_capability(name, catalog=catalog)
    width = positive_metadata_field(value, "generation_width")
    if "generation_balance" in value and type(value["generation_balance"]) is not bool:
        raise ValueError("generation_balance must be boolean")
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
        generation_balance=value.get("generation_balance"),
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
    from esolangs.runtime._artifact_source import positive_metadata_field

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
            if "generation_balance" in value:
                fields.add("generation_balance")
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
        owner = value["language"]
        if not isinstance(owner, str) or resolve_origin(owner, catalog=catalog) != name:
            raise ValueError(f"program language must be {display_label(name)}")
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
        return bind_catalog(artifact, catalog)
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
