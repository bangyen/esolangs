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
    pending: list[tuple[str, Any]] = [("value", value)]
    values: list[Any] = []
    active: set[int] = set()
    while pending:
        operation, item = pending.pop()
        if operation != "value":
            identity, keys, count = item
            children = values[-count:] if count else []
            if count:
                del values[-count:]
            active.remove(identity)
            if operation == "object":
                result = dict(zip(keys, children, strict=True))
                if len(result) == 1 and next(iter(result)) in {
                    "$python_text",
                    "$python_object",
                }:
                    values.append({"$python_object": list(map(list, result.items()))})
                else:
                    values.append(result)
            else:
                values.append(children)
        elif isinstance(item, str) and _SURROGATES.search(item):
            values.append({"$python_text": item.encode("utf-8", "surrogatepass").hex()})
        elif isinstance(item, (dict, list, tuple)):
            identity = id(item)
            if identity in active:
                raise ValueError("Circular reference detected")
            active.add(identity)
            if isinstance(item, dict):
                pairs = [(key, child) for key, child in item.items()]
                keys = [key for key, _child in pairs]
                children = [child for _key, child in pairs]
                operation = "object"
            else:
                keys = []
                # list(item) adds a __len__ call absent from the old traversal.
                children = [child for child in item]  # noqa: C416
                operation = "array"
            pending.append((operation, (identity, keys, len(children))))
            pending.extend(("value", child) for child in reversed(children))
        else:
            values.append(item)
    return values[0]


def _worker_key(key: Any) -> str:
    if isinstance(key, str):
        return json.dumps(key)
    if key is None or isinstance(key, (int, float)):
        return json.dumps(json.dumps(key))
    raise TypeError(
        f"keys must be str, int, float, bool or None, not {type(key).__name__}"
    )


def worker_dumps(value: Any) -> str:
    """Preserve Python code points without recursive container encoding."""
    pending: list[tuple[str, Any]] = [("value", _worker_values(value))]
    output: list[str] = []
    while pending:
        operation, item = pending.pop()
        if operation == "text":
            output.append(item)
        elif isinstance(item, dict):
            pairs = list(item.items())
            output.append("{")
            pending.append(("text", "}"))
            for index in range(len(pairs) - 1, -1, -1):
                if index < len(pairs) - 1:
                    pending.append(("text", ", "))
                key, child = pairs[index]
                pending.append(("value", child))
                pending.append(("text", ": "))
                pending.append(("text", _worker_key(key)))
        elif isinstance(item, list):
            output.append("[")
            pending.append(("text", "]"))
            for index in range(len(item) - 1, -1, -1):
                if index < len(item) - 1:
                    pending.append(("text", ", "))
                pending.append(("value", item[index]))
        else:
            output.append(json.dumps(item))
    return "".join(output)


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


def _worker_space(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def worker_loads(text: str) -> Any:
    """Decode worker JSON iteratively, applying each completed object hook once."""
    decoder = json.JSONDecoder()
    object_hook = worker_object
    pending: list[tuple[str, Any]] = [("value", None)]
    values: list[Any] = []
    index = 0
    while pending:
        operation, item = pending.pop()
        index = _worker_space(text, index)
        character = text[index : index + 1]
        if operation == "value":
            if character == "[":
                index += 1
                pending.append(("array_first", []))
            elif character == "{":
                index += 1
                pending.append(("object_first", []))
            else:
                value, index = decoder.raw_decode(text, index)
                values.append(value)
        elif operation == "array_first":
            if character == "]":
                index += 1
                values.append(item)
            else:
                pending.append(("array_item", item))
                pending.append(("value", None))
        elif operation == "array_item":
            item.append(values.pop())
            if character == "]":
                index += 1
                values.append(item)
            elif character == ",":
                index += 1
                pending.append(("array_item", item))
                pending.append(("value", None))
            else:
                raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
        elif operation in ("object_first", "object_key"):
            if operation == "object_first" and character == "}":
                index += 1
                values.append(object_hook(item))
                continue
            if character != '"':
                raise json.JSONDecodeError(
                    "Expecting property name enclosed in double quotes", text, index
                )
            key, index = decoder.raw_decode(text, index)
            index = _worker_space(text, index)
            if text[index : index + 1] != ":":
                raise json.JSONDecodeError("Expecting ':' delimiter", text, index)
            index += 1
            pending.append(("object_item", (item, key)))
            pending.append(("value", None))
        else:
            pairs, key = item
            pairs.append((key, values.pop()))
            if character == "}":
                index += 1
                values.append(object_hook(pairs))
            elif character == ",":
                index += 1
                pending.append(("object_key", pairs))
            else:
                raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
    index = _worker_space(text, index)
    if index != len(text):
        raise json.JSONDecodeError("Extra data", text, index)
    return values[0]
