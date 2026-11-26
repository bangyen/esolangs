"""Encode and read requests for an isolated interpreter."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any, TextIO, cast

from esolangs.compressed import CompressedText
from esolangs.raster import Raster
from esolangs.registry._catalog import Catalog
from esolangs.runtime._json import _WorkerBase64, canonical_integer, worker_loads
from esolangs.runtime._program import Program
from esolangs.runtime._raster_wire import _raster_transport
from esolangs.settings import DialectSettings, dialect_options

_REQUEST_FIELDS = frozenset(
    {
        "language",
        "program",
        "raster",
        "compressed",
        "stdin",
        "settings",
        "integer_settings",
        "seed",
        "integer_seed",
        "scale",
        "max_memory",
        "max_output",
        "integer_max_output",
        "max_steps",
        "integer_max_steps",
        "termination",
        "report_prepared",
    }
)


def _source_transport(
    source: Program, *, chunked: bool, stopped: Callable[[], bool] | None
) -> dict[str, Any]:
    """Encode all source containers for the JSON worker protocol."""
    if isinstance(source, CompressedText):
        compressed = source.to_gzip()
        return {
            "program": _WorkerBase64(compressed)
            if chunked
            else base64.b64encode(compressed).decode("ascii"),
            "raster": False,
            "compressed": True,
        }
    return {
        "program": _raster_transport(source, stopped)
        if isinstance(source, Raster)
        else source,
        "raster": isinstance(source, Raster),
        "compressed": False,
    }


def encode_request(
    name: str,
    source: Program,
    stdin: str,
    *,
    settings: DialectSettings | None = None,
    seed: int | None = None,
    scale: int | None = None,
    max_memory: int | None = None,
    max_output: int | None = None,
    max_steps: int | None = None,
    termination: bool = False,
    report_prepared: bool = False,
    catalog: Catalog | None = None,
    _settings_validated: bool = False,
    chunked: bool = False,
    stopped: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Encode one complete worker request, including unavailable options."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    choices = (
        DialectSettings.options(settings)
        if _settings_validated and settings is not None
        else dialect_options(name, settings, catalog=catalog)
    )
    return {
        "language": name,
        **_source_transport(source, chunked=chunked, stopped=stopped),
        "stdin": stdin,
        "settings": {
            key: hex(value) if type(value) is int else value
            for key, value in choices.items()
        },
        "integer_settings": [
            key for key, value in choices.items() if type(value) is int
        ],
        # Decimal JSON rendering rejects valid 4301-digit integers.
        "seed": hex(seed) if seed is not None else None,
        "integer_seed": seed is not None,
        "scale": hex(scale) if scale is not None else None,
        "max_memory": max_memory,
        "max_output": hex(max_output) if max_output is not None else None,
        "integer_max_output": max_output is not None,
        "max_steps": hex(max_steps) if max_steps is not None else None,
        "integer_max_steps": max_steps is not None,
        "termination": termination,
        "report_prepared": report_prepared,
    }


def read_request(stream: TextIO) -> dict[str, Any]:
    """Decode the canonical request; omitted options are protocol errors."""
    request = worker_loads(stream.read())
    if not isinstance(request, dict) or set(request) != _REQUEST_FIELDS:
        raise ValueError("invalid worker request fields")
    flags = (
        "raster",
        "compressed",
        "termination",
        "integer_seed",
        "integer_max_output",
        "integer_max_steps",
    )
    if (
        any(type(request[key]) is not bool for key in flags)
        or (request["raster"] and request["compressed"])
        or any(not isinstance(request[key], str) for key in ("language", "stdin"))
        or not isinstance(request["settings"], dict)
        or not isinstance(request["integer_settings"], list)
    ):
        raise ValueError("invalid worker request values")
    integer_settings = request["integer_settings"]
    if (
        any(not isinstance(key, str) for key in integer_settings)
        or len(set(integer_settings)) != len(integer_settings)
        or set(integer_settings) - request["settings"].keys()
    ):
        raise ValueError("invalid worker integer settings")
    for key, value in request["settings"].items():
        if not isinstance(value, str):
            raise ValueError("invalid worker setting")
        if key in integer_settings:
            canonical_integer(value)
    for key in ("seed", "max_output", "max_steps"):
        value = request[key]
        if request[f"integer_{key}"]:
            decoded = canonical_integer(value)
            if key != "seed" and decoded < 0:
                raise ValueError("invalid worker limit")
            if key != "seed":
                request[key] = decoded
        elif value is not None:
            raise ValueError("untagged worker integer")
    if request["scale"] is not None:
        scale = canonical_integer(request["scale"])
        if scale < 1:
            raise ValueError("invalid worker scale")
        request["scale"] = scale
    memory = request["max_memory"]
    if memory is not None and (type(memory) is not int or memory < 1):
        raise ValueError("invalid worker size")
    if type(request["report_prepared"]) is not bool:
        raise ValueError("invalid worker preparation flag")
    if request["raster"]:
        _check_raster_request(request["program"])
    elif not isinstance(request["program"], str):
        raise ValueError("invalid worker source")
    return cast("dict[str, Any]", request)


def _check_raster_request(runs: Any) -> None:
    """Refuse malformed runs before expansion can drop counts or channels."""
    if not isinstance(runs, list):
        raise ValueError("invalid worker raster")
    for run in runs:
        if (
            not isinstance(run, list)
            or len(run) != 2
            or type(run[0]) is not int
            or run[0] < 1
            or not isinstance(run[1], list)
        ):
            raise ValueError("invalid worker raster row")
        for pixel in run[1]:
            if (
                not isinstance(pixel, list)
                or len(pixel) != 2
                or type(pixel[0]) is not int
                or pixel[0] < 1
                or not isinstance(pixel[1], list)
                or len(pixel[1]) != 3
                or any(type(c) is not int or not 0 <= c <= 255 for c in pixel[1])
            ):
                raise ValueError("invalid worker raster pixel")
