"""Unambiguous objects for JSON metadata and worker protocols."""

import json
import re
from typing import Any


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build an object, refusing repeated fields at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = value
    return result


def canonical_integer(value: Any) -> int:
    """Decode exactly the hexadecimal spelling emitted by worker encoders."""
    if not isinstance(value, str) or not value.startswith(("0x", "-0x")):
        raise ValueError("invalid worker integer")
    decoded = int(value, 16)
    if hex(decoded) != value:
        raise ValueError("noncanonical worker integer")
    return decoded


_SURROGATES = re.compile(r"[\ud800-\udfff]")


def _worker_values(value: Any) -> Any:
    if isinstance(value, str) and _SURROGATES.search(value):
        return {"$python_text": value.encode("utf-8", "surrogatepass").hex()}
    if isinstance(value, dict):
        values = {key: _worker_values(item) for key, item in value.items()}
        if len(values) == 1 and next(iter(values)) in {
            "$python_text",
            "$python_object",
        }:
            return {"$python_object": list(map(list, values.items()))}
        return values
    if isinstance(value, (list, tuple)):
        return [_worker_values(item) for item in value]
    return value


def worker_dumps(value: Any) -> str:
    """Preserve Python text code points that JSON otherwise combines."""
    return json.dumps(_worker_values(value))


def worker_object(pairs: list[tuple[str, Any]]) -> Any:
    """Decode canonical worker text tags after rejecting repeated fields."""
    result = unique_object(pairs)
    if set(result) == {"$python_object"}:
        entries = result["$python_object"]
        if (
            not isinstance(entries, list)
            or len(entries) != 1
            or not isinstance(entries[0], list)
            or len(entries[0]) != 2
            or entries[0][0] not in ("$python_text", "$python_object")
        ):
            raise ValueError("invalid worker object")
        return dict(entries)
    if set(result) != {"$python_text"}:
        return result
    payload = result["$python_text"]
    if not isinstance(payload, str):
        raise ValueError("invalid worker text")
    raw = bytes.fromhex(payload)
    text = raw.decode("utf-8", "surrogatepass")
    if raw.hex() != payload or not _SURROGATES.search(text):
        raise ValueError("noncanonical worker text")
    return text
