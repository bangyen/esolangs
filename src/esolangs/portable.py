"""Native source files and versioned JSON programs."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, replace
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import ArgumentError, ProgramError, TemplateError
from esolangs.raster import Raster, png
from esolangs.registry import template_char
from esolangs.registry._catalog import Catalog
from esolangs.runtime._json import unique_object
from esolangs.runtime._source import ProgramSource
from esolangs.runtime.source_hints import with_hint
from esolangs.settings import (
    DialectSettings,
    _settings_for,
    dialect_options,
    effective_settings,
)

_FORMAT = "esolangs.program"


def save_program(
    language: str,
    program: ProgramSource,
    path: str | PathLike[str],
    *,
    gzip: bool = False,
    normalize: bool = False,
    catalog: Catalog | None = None,
) -> None:
    """Write a program as a native source file.

    Text retains its UTF-8 bytes and line endings, compressed source stays gzip,
    and rasters are PNG. ``gzip=True`` compresses ordinary text exports too.
    Compression is explicit; a ``.gz`` suffix alone does not enable it.
    ``normalize=True`` appends a language-permitted native file terminator to text,
    including gzip exports.
    An existing file is replaced after encoding and
    writing succeed. Use :func:`dump_program` for a portable document that
    preserves dialect settings and template setters.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``gzip`` or ``normalize`` is not a Boolean flag, or
            ``path`` is not a str or PathLike.
        TemplateError: ``program`` is an unfilled template.
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: The record belongs to another language, or the source
            cannot be read or encoded or the file cannot be written.
        MissingDependencyError: A raster needs ``esolangs[image]`` for PNG.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if type(gzip) is not bool:
        raise ArgumentError("gzip must be a boolean")
    if type(normalize) is not bool:
        raise ArgumentError("normalize must be a boolean")
    if not isinstance(path, (str, PathLike)):
        raise ArgumentError(
            f"path must be a str or PathLike, got {type(path).__name__}"
        )
    from esolangs.operations.source import check_origin, read_artifact

    # The language decides the file terminator and PNG metadata; without it,
    # normalize appended "\n" even where a trailing newline is code.
    origin = catalog.resolve(language)
    try:
        record = (
            program
            if isinstance(program, (ProgramArtifact, TemplateArtifact))
            else None
        )
        if record is not None:
            check_origin(origin, record.language, catalog=catalog)
            if isinstance(record, TemplateArtifact):
                # A native file cannot carry bindings: it reloaded as plain
                # source and ran with its placeholders unfilled.
                raise with_hint(
                    TemplateError(
                        "a template's native file would run with its "
                        "placeholders unfilled"
                    ),
                    "fill it with instantiate() first, or keep the bindings "
                    "with dump_program()",
                )
            program = record.source
        elif not isinstance(program, (str, Raster, CompressedText)):
            # Bytes, paths and streams load as run() loads them.
            record = read_artifact(origin, program, catalog=catalog)
            program = record.source
        if isinstance(program, CompressedText):
            source = program.to_gzip()
        elif isinstance(program, Raster):
            if gzip:
                raise ProgramError("gzip export requires text; rasters use PNG")
            source = png.write_source(
                program.rows,
                origin,
                record.settings if record is not None else None,
                record.scale if isinstance(record, ProgramArtifact) else None,
            )
        elif isinstance(program, str):
            ending = (
                "\n"
                if normalize and catalog.languages[origin].runtime.file_newline
                else ""
            )
            source = (
                CompressedText.from_chunks((program, ending)).to_gzip()
                if gzip
                else (program + ending).encode("utf-8")
            )
        else:
            raise ProgramError("expected text, compressed source, or a raster")
        target = Path(path)
        if target.is_dir():
            # The staged rename's error named the temporary file instead.
            raise IsADirectoryError("it is a directory")
        with TemporaryDirectory(dir=target.parent) as temporary:
            staged = Path(temporary) / "source"
            staged.write_bytes(source)
            staged.replace(target)
    except (ProgramError, TemplateError):
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ProgramError(f"cannot save program to {path!s}: {exc}") from exc


def dump_program(
    language: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None = None,
    catalog: Catalog | None = None,
) -> str:
    """Return version-1 JSON preserving source, choices, and Boolean bindings.

    Raster pixels are embedded as base64 PNG. Integer choices use hexadecimal
    strings, including values beyond Python's decimal conversion limit.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``settings`` is invalid for the language.
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: ``program`` cannot be read (base of the above).
        MissingDependencyError: A raster needs ``esolangs[image]`` for PNG.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.operations.source import read_artifact

    name = catalog.resolve(language)
    settings = effective_settings(name, program, settings, catalog=catalog)
    values = dialect_options(name, settings, catalog=catalog)
    acquired = read_artifact(name, program, catalog=catalog)
    artifact = (
        program
        if isinstance(program, (ProgramArtifact, TemplateArtifact))
        else acquired
    )
    settings = effective_settings(name, artifact, settings, catalog=catalog)
    values = dialect_options(name, settings, catalog=catalog)
    encoded = (
        None
        if settings is None
        else {
            key: {"integer": hex(value)} if type(value) is int else value
            for key, value in values.items()
        }
    )
    document: dict[str, Any] = {
        "format": _FORMAT,
        "version": 1,
        "language": name,
        "settings": encoded,
    }
    if isinstance(artifact, ProgramArtifact) and artifact.input_arity is not None:
        document["input_arity"] = artifact.input_arity
    body = artifact.source
    if isinstance(artifact, TemplateArtifact):
        document.update(
            kind="template",
            source=artifact.source,
            char=artifact.bindings.char,
            setters=artifact.bindings.setters,
            spans=artifact.spans,
        )
    elif isinstance(body, Raster):
        document.update(
            kind="png",
            source=base64.b64encode(
                png.write_source(body.rows, name, settings, artifact.scale)
            ).decode("ascii"),
        )
    elif isinstance(body, CompressedText):
        document.update(
            kind="gzip",
            source=base64.b64encode(body.to_gzip()).decode("ascii"),
            limits=asdict(body.limits) if body.limits is not None else None,
        )
    else:
        document.update(kind="text", source=str(body))
    try:
        # The check ``load_program`` makes: a lone surrogate dumped as a
        # ``\ud800`` escape, which it then refused.
        json.dumps(document, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProgramError(f"program is not valid UTF-8 text: {error}") from error
    return json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def _settings(
    value: Any, language: str, *, catalog: Catalog | None = None
) -> DialectSettings | None:
    """Restore saved dialect settings, validated for ``language``."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    settings = decode_settings(value, language, catalog=catalog)
    if settings is not None:
        dialect_options(language, settings, catalog=catalog)
    return settings


def decode_settings(
    value: Any, language: str | None, *, catalog: Catalog | None = None
) -> DialectSettings | None:
    """Restore saved dialect settings; shared with PNG metadata."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("settings must be an object or null")
    choices: dict[str, Any] = {}
    for key, saved in value.items():
        item = saved
        if isinstance(item, dict):
            if set(item) != {"integer"} or not isinstance(item["integer"], str):
                raise ValueError("integer settings need a hexadecimal string")
            literal = item["integer"]
            if not literal.startswith(("0x", "-0x")):
                raise ValueError("integer settings need a hexadecimal string")
            item = int(literal, 16)
        choices[key] = item
    if language is None:
        raise ValueError("settings need a language to apply to")
    return _settings_for(language, choices, catalog=catalog)


def _load_png(
    value: dict[str, Any],
    name: str,
    settings: DialectSettings | None,
    *,
    catalog: Catalog | None = None,
) -> ProgramArtifact[Raster]:
    """Restore a ``png`` document's raster."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.operations.source import read_png_artifact

    data = base64.b64decode(value["source"], validate=True)
    record = read_png_artifact(name, data, catalog=catalog)
    metadata = png.read_metadata(data)
    if metadata is not None and record.settings != settings:
        raise ValueError("conflicting PNG and document settings")
    return ProgramArtifact(record.source, name, settings, record.scale)


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
        settings,
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
    return ProgramArtifact(value["source"], name, settings)


def _load_template(
    value: dict[str, Any],
    name: str,
    settings: DialectSettings | None,
    *,
    catalog: Catalog | None = None,
) -> TemplateArtifact:
    """Restore a ``template`` document's template and setters."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if not isinstance(value["char"], str) or len(value["char"]) != 1:
        raise ValueError("template char must be one character")
    if value["char"] != template_char(catalog.languages[name].id, catalog=catalog):
        raise ValueError("template char does not match the language")
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
        TemplateBindings(value["char"], tuple(pairs)),
        settings,
        spans=spans,
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


#: Source-kind dispatch for :func:`load_program`.
_LOADERS: dict[str, _Loader] = {
    "png": _load_png,
    "gzip": _load_gzip,
    "text": _load_text,
    "template": _load_template,
}


def load_program(
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
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    from esolangs.operations.source import _read_source

    name = catalog.resolve(language)
    if not isinstance(document, str):
        raise ArgumentError("document must be a JSON string")
    try:
        value = json.loads(document, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError("document must be an object")
        fields = {"format", "version", "language", "settings", "kind", "source"}
        kind = value.get("kind")
        if kind == "gzip":
            fields.add("limits")
        if kind == "template":
            fields |= {"char", "setters", "spans"}
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
        if value["language"] != name:
            raise ValueError(f"program language must be {name}")
        if not isinstance(value["source"], str):
            raise ValueError("source must be a string")
        # Strict UTF-8 everywhere, as a program file is read: a JSON
        # "\ud800" escape in the source or a setter loaded a lone surrogate.
        json.dumps(value, ensure_ascii=False).encode("utf-8")
        settings = _settings(value["settings"], name, catalog=catalog)
        if not isinstance(kind, str) or kind not in _LOADERS:
            raise ValueError("unknown source kind")
        artifact = _LOADERS[kind](value, name, settings, catalog=catalog)
        if isinstance(artifact, ProgramArtifact) and "input_arity" in value:
            arity = value["input_arity"]
            if type(arity) is not int or arity < 1:
                raise ValueError("input_arity must be a positive integer")
            artifact = replace(artifact, input_arity=arity)
        _read_source(name, artifact, catalog=catalog)
        return artifact
    except (ValueError, TypeError) as error:
        raise ProgramError(f"invalid portable program: {error}") from error
