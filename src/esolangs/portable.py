"""Versioned JSON programs retaining dialect and template provenance."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict
from typing import Any

from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, resolve, template_char
from esolangs.runtime._program import Program
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.tagged import _Tagged, _Template

_FORMAT = "esolangs.program"


def dump_program(
    language: str, program: Program, *, settings: DialectSettings | None = None
) -> str:
    """Return version-1 JSON preserving source, choices, and template setters.

    Raster pixels are embedded as base64 PNG. Integer choices use hexadecimal
    strings, including values beyond Python's decimal conversion limit.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``settings`` is invalid for the language.
        ProgramNotFoundError: ``program`` is a Path that does not exist.
        ProgramError: ``program`` cannot be read (base of the above).
        MissingDependencyError: A raster needs ``esolangs[image]`` for PNG.
    """
    from esolangs import _read_source

    name = resolve(language)
    settings = effective_settings(name, program, settings)
    values = dialect_options(name, settings)
    source = _read_source(name, program)
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
    if isinstance(source, Raster):
        document.update(
            kind="png", source=base64.b64encode(source.to_png()).decode("ascii")
        )
    elif isinstance(source, CompressedText):
        document.update(
            kind="gzip",
            source=base64.b64encode(source.to_gzip()).decode("ascii"),
            limits=asdict(source.limits) if source.limits is not None else None,
        )
    elif isinstance(source, _Template):
        document.update(
            kind="template",
            source=str(source),
            char=source.char,
            setters=source.setters,
        )
    else:
        document.update(kind="text", source=str(source))
    return json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object, refusing a duplicate field."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = value
    return result


def _settings(value: Any, language: str) -> DialectSettings | None:
    """Restore saved dialect settings, validated for ``language``."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("settings must be an object or null")
    choices: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            if set(item) != {"integer"} or not isinstance(item["integer"], str):
                raise ValueError("integer settings need a hexadecimal string")
            literal = item["integer"]
            if not literal.startswith(("0x", "-0x")):
                raise ValueError("integer settings need a hexadecimal string")
            item = int(literal, 16)
        choices[key] = item
    settings = DialectSettings(**choices)
    dialect_options(language, settings)
    return settings


def _load_png(
    value: dict[str, Any], name: str, settings: DialectSettings | None
) -> Program:
    """Restore a ``png`` document's raster."""
    return Raster.from_png(base64.b64decode(value["source"], validate=True)).tagged(
        name, settings=settings
    )


def _load_gzip(
    value: dict[str, Any], name: str, settings: DialectSettings | None
) -> Program:
    """Restore a ``gzip`` document's compressed text."""
    limits = value.get("limits")
    if limits is not None:
        if not isinstance(limits, dict) or set(limits) != {
            "plain_chars",
            "generation_chars",
            "gzip_bytes",
        }:
            raise ValueError("invalid compressed text limits")
        limits = TextLimits(**limits)
    return CompressedText(
        base64.b64decode(value["source"], validate=True), limits=limits
    ).tagged(name, settings=settings)


def _load_text(
    value: dict[str, Any], name: str, settings: DialectSettings | None
) -> Program:
    """Restore a ``text`` document's source."""
    return _Tagged(value["source"], name, settings)


def _load_template(
    value: dict[str, Any], name: str, settings: DialectSettings | None
) -> Program:
    """Restore a ``template`` document's template and setters."""
    if not isinstance(value["char"], str) or len(value["char"]) != 1:
        raise ValueError("template char must be one character")
    if value["char"] != template_char(LANGUAGES[name].id):
        raise ValueError("template char does not match the language")
    pairs = value["setters"]
    if not isinstance(pairs, list) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(item, str) for item in pair)
        for pair in pairs
    ):
        raise ValueError("setters must be pairs of strings")
    return _Template(value["source"], name, value["char"], pairs, settings)


#: Source-kind dispatch for :func:`load_program`.
_LOADERS = {
    "png": _load_png,
    "gzip": _load_gzip,
    "text": _load_text,
    "template": _load_template,
}


def load_program(language: str, document: str) -> Program:
    """Restore version-1 JSON as tagged source for the requested language.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ArgumentError: ``document`` is not a string.
        ProgramError: ``document`` is not a valid version-1 program for
            ``language``, including invalid settings.
        MissingDependencyError: A PNG source needs ``esolangs[image]``.
    """
    from esolangs import _read_source

    name = resolve(language)
    if not isinstance(document, str):
        raise ArgumentError("document must be a JSON string")
    try:
        value = json.loads(document, object_pairs_hook=_object)
        if not isinstance(value, dict):
            raise ValueError("document must be an object")
        fields = {"format", "version", "language", "settings", "kind", "source"}
        kind = value.get("kind")
        if kind == "gzip" and "limits" in value:
            fields.add("limits")
        if kind == "template":
            fields |= {"char", "setters"}
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
        settings = _settings(value["settings"], name)
        if not isinstance(kind, str) or kind not in _LOADERS:
            raise ValueError("unknown source kind")
        source = _LOADERS[kind](value, name, settings)
        return _read_source(name, source)
    except (ValueError, TypeError) as error:
        raise ProgramError(f"invalid portable program: {error}") from error
