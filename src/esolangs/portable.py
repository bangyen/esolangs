"""Versioned JSON programs retaining dialect and template provenance."""

from __future__ import annotations

import base64
import json
from typing import Any

from esolangs._program import Program
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, resolve, template_char
from esolangs.settings import DialectSettings, dialect_options, effective_settings
from esolangs.tagged import _Tagged, _Template

_FORMAT = "esolangs.program"


def dump_program(
    language: str, program: Program, *, settings: DialectSettings | None = None
) -> str:
    """Return version-1 JSON preserving source, choices, and template setters.

    Raster pixels are embedded as base64 PNG. Integer choices use hexadecimal
    strings, including values beyond Python's decimal conversion limit.
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
        "kind": "png" if isinstance(source, Raster) else "text",
        "source": (
            base64.b64encode(source.to_png()).decode("ascii")
            if isinstance(source, Raster)
            else str(source)
        ),
    }
    if isinstance(source, _Template):
        document.update(kind="template", char=source.char, setters=source.setters)
    return json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = value
    return result


def _settings(value: Any, language: str) -> DialectSettings | None:
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


def load_program(language: str, document: str) -> Program:
    """Restore version-1 JSON as tagged source for the requested language."""
    from esolangs import _read_source

    name = resolve(language)
    if not isinstance(document, str):
        raise ArgumentError("document must be a JSON string")
    try:
        value = json.loads(document, object_pairs_hook=_object)
        if not isinstance(value, dict):
            raise ValueError("document must be an object")
        fields = {"format", "version", "language", "settings", "kind", "source"}
        if value.get("kind") == "template":
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
        settings = _settings(value["settings"], name)
        source: Program
        if value["kind"] == "png":
            source = Raster.from_png(
                base64.b64decode(value["source"], validate=True)
            ).tagged(name, settings)
        elif value["kind"] == "text":
            source = _Tagged(value["source"], name, settings)
        elif value["kind"] == "template":
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
            source = _Template(value["source"], name, value["char"], pairs, settings)
        else:
            raise ValueError("unknown source kind")
        return _read_source(name, source)
    except (ValueError, TypeError) as error:
        raise ProgramError(f"invalid portable program: {error}") from error
