"""Unambiguous objects for JSON metadata and worker protocols."""

from typing import Any


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build an object, refusing repeated fields at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {key}")
        result[key] = value
    return result
