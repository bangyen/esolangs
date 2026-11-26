"""Strict JSON records and shared object validation."""

import json
import re
from typing import Any, NoReturn

from esolangs.runtime.memory import _hit_digit_cap, format_integer, parse_integer
from esolangs.runtime.source_hints import display_label

_SURROGATES = re.compile(r"[\ud800-\udfff]")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build an object, refusing repeated fields at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field: {display_label(key)}")
        result[key] = value
    return result


def _reject_json_constant(token: str) -> NoReturn:
    """Refuse Python's nonstandard JSON numeric constants."""
    raise ValueError(f"invalid JSON constant {token}")


def record_loads(document: str) -> Any:
    """Read strict records with unique object keys and arbitrary integers."""
    return json.loads(
        str.__str__(document),
        object_pairs_hook=unique_object,
        parse_int=parse_integer,
        parse_constant=_reject_json_constant,
    )


def check_record_utf8(value: Any) -> None:
    """Check text in a decoded JSON record without re-encoding its numbers."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and _SURROGATES.search(item):
            item.encode("utf-8")
        elif isinstance(item, dict):
            pending.extend(item)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def canonical_integer(value: Any) -> int:
    """Decode exactly the hexadecimal spelling emitted by worker encoders."""
    if not isinstance(value, str) or not value.startswith(("0x", "-0x")):
        raise ValueError("invalid worker integer")
    decoded = int(value, 16)
    if hex(decoded) != value:
        raise ValueError("noncanonical worker integer")
    return decoded


def _record_key(key: object, *, ensure_ascii: bool) -> str:
    """Spell a JSON object key with the normal encoder's scalar coercions."""
    if isinstance(key, str):
        text = key
    elif isinstance(key, int) and not isinstance(key, bool):
        text = format_integer(key)
    elif key is None or isinstance(key, (bool, float)):
        text = json.dumps(key, allow_nan=False)
    else:
        raise TypeError(
            f"keys must be str, int, float, bool or None, not {type(key).__name__}"
        )
    return json.dumps(text, ensure_ascii=ensure_ascii)


def record_dumps(
    value: Any, *, ensure_ascii: bool = True, sort_keys: bool = False
) -> str:
    """Keep persisted record integers as JSON numbers, including large ones."""
    try:
        return json.dumps(
            value,
            ensure_ascii=ensure_ascii,
            sort_keys=sort_keys,
            allow_nan=False,
            separators=(",", ":"),
        )
    except ValueError as error:
        if not _hit_digit_cap(error):
            raise

    active: set[int] = set()

    def encode(item: Any) -> str:
        if type(item) is not bool and issubclass(type(item), int):
            return format_integer(int.__int__(item))
        if not isinstance(item, (dict, list, tuple)):
            return json.dumps(item, ensure_ascii=ensure_ascii, allow_nan=False)
        identity = id(item)
        if identity in active:
            raise ValueError("Circular reference detected")
        active.add(identity)
        try:
            if isinstance(item, dict):
                keys = sorted(item) if sort_keys else item
                return (
                    "{"
                    + ",".join(
                        _record_key(key, ensure_ascii=ensure_ascii)
                        + ":"
                        + encode(item[key])
                        for key in keys
                    )
                    + "}"
                )
            return "[" + ",".join(map(encode, item)) + "]"
        finally:
            active.remove(identity)

    return encode(value)
