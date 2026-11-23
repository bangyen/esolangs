"""Unambiguous objects for JSON metadata and worker protocols."""

import json
import re
from base64 import b64encode
from collections.abc import Callable, Iterator
from dataclasses import dataclass
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
    """Check UTF-8 text in a record without serializing it."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if not str.isascii(item) and _SURROGATES.search(item):
                str.encode(item, "utf-8")
        elif isinstance(item, dict):
            pending.extend(item)
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
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


_WORKER_TAGS = ("$python_text", "$python_object", "$python_integer")
# Keep decimal tokens below even the smallest Python digit cap.
_WORKER_INTEGER_BITS = 1024
_WORKER_TEXT_BLOCK = 4096
_WORKER_REQUEST_BLOCK = 65_536


@dataclass(frozen=True, slots=True)
class _WorkerBase64:
    """A compressed request body whose base64 string is encoded in pieces."""

    data: bytes


@dataclass(frozen=True, slots=True)
class _WorkerSurrogates:
    text: str


def _contains_surrogate(text: str, checkpoint: Callable[[], None]) -> bool:
    for offset in range(0, str.__len__(text), _WORKER_TEXT_BLOCK):
        checkpoint()
        if _SURROGATES.search(text, offset, offset + _WORKER_TEXT_BLOCK):
            return True
    return False


def _worker_values(value: Any, checkpoint: Callable[[], None] | None = None) -> Any:
    pending: list[tuple[str, Any]] = [("value", value)]
    values: list[Any] = []
    active: set[int] = set()
    while pending:
        if checkpoint is not None:
            checkpoint()
        operation, item = pending.pop()
        if operation != "value":
            identity, keys, count = item
            children = values[-count:] if count else []
            if count:
                del values[-count:]
            active.remove(identity)
            if operation == "object":
                result = dict(zip(keys, children, strict=True))
                if len(result) == 1 and next(iter(result)) in _WORKER_TAGS:
                    values.append({"$python_object": list(map(list, result.items()))})
                else:
                    values.append(result)
            else:
                values.append(children)
        elif isinstance(item, str) and (
            _SURROGATES.search(item)
            if checkpoint is None
            else _contains_surrogate(item, checkpoint)
        ):
            payload = (
                item.encode("utf-8", "surrogatepass").hex()
                if checkpoint is None
                else _WorkerSurrogates(item)
            )
            values.append({"$python_text": payload})
        elif type(item) is int and item.bit_length() > _WORKER_INTEGER_BITS:
            values.append({"$python_integer": hex(item)})
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


def _request_string(
    item: str | _WorkerSurrogates | _WorkerBase64,
    checkpoint: Callable[[], None],
) -> Iterator[str]:
    yield '"'
    if isinstance(item, _WorkerBase64):
        # A multiple of three leaves padding only at the end of the stream.
        block = 3 * _WORKER_TEXT_BLOCK
        for offset in range(0, len(item.data), block):
            checkpoint()
            yield b64encode(item.data[offset : offset + block]).decode("ascii")
    else:
        text = item.text if isinstance(item, _WorkerSurrogates) else item
        for offset in range(0, str.__len__(text), _WORKER_TEXT_BLOCK):
            checkpoint()
            piece = str.__getitem__(text, slice(offset, offset + _WORKER_TEXT_BLOCK))
            yield (
                piece.encode("utf-8", "surrogatepass").hex()
                if isinstance(item, _WorkerSurrogates)
                else json.dumps(piece)[1:-1]
            )
    yield '"'


def _worker_fragments(
    value: Any, checkpoint: Callable[[], None] | None = None
) -> Iterator[str]:
    pending: list[tuple[str, Any]] = [("value", _worker_values(value, checkpoint))]
    while pending:
        if checkpoint is not None:
            checkpoint()
        operation, item = pending.pop()
        if operation == "text":
            yield item
        elif operation == "key" and not isinstance(item, str):
            yield _worker_key(item)
        elif isinstance(item, dict):
            pairs = list(item.items())
            yield "{"
            pending.append(("text", "}"))
            for index in range(len(pairs) - 1, -1, -1):
                if index < len(pairs) - 1:
                    pending.append(("text", ", "))
                key, child = pairs[index]
                pending.append(("value", child))
                pending.append(("text", ": "))
                pending.append(
                    ("text", _worker_key(key)) if checkpoint is None else ("key", key)
                )
        elif isinstance(item, list):
            yield "["
            pending.append(("text", "]"))
            for index in range(len(item) - 1, -1, -1):
                if index < len(item) - 1:
                    pending.append(("text", ", "))
                pending.append(("value", item[index]))
        elif checkpoint is not None and (
            isinstance(item, (_WorkerSurrogates, _WorkerBase64))
            or (isinstance(item, str) and str.__len__(item) > _WORKER_TEXT_BLOCK)
        ):
            yield from _request_string(item, checkpoint)
        else:
            yield json.dumps(item)


def worker_dumps(value: Any) -> str:
    """Preserve Python code points and large integers in iterative JSON encoding."""
    return "".join(_worker_fragments(value))


class _WorkerRequestStoppedError(Exception):
    """The caller cancelled request acquisition or reached its deadline."""


def worker_request(value: Any, stopped: Callable[[], bool]) -> str | list[str] | None:
    """Assemble canonical JSON in bounded writes, or abandon a cancelled request."""

    def checkpoint() -> None:
        if stopped():
            raise _WorkerRequestStoppedError

    blocks: list[str] = []
    parts: list[str] = []
    size = 0
    try:
        for part in _worker_fragments(value, checkpoint):
            checkpoint()
            if parts and size + len(part) > _WORKER_REQUEST_BLOCK:
                blocks.append("".join(parts))
                parts.clear()
                size = 0
            parts.append(part)
            size += len(part)
        tail = "".join(parts)
        checkpoint()
    except _WorkerRequestStoppedError:
        return None
    if not blocks:
        return tail
    blocks.append(tail)
    return blocks


def worker_object(pairs: list[tuple[str, Any]]) -> Any:
    """Decode canonical worker tags after rejecting repeated fields."""
    result = unique_object(pairs)
    if set(result) == {"$python_object"}:
        entries = result["$python_object"]
        if (
            not isinstance(entries, list)
            or len(entries) != 1
            or not isinstance(entries[0], list)
            or len(entries[0]) != 2
            or entries[0][0] not in _WORKER_TAGS
        ):
            raise ValueError("invalid worker object")
        return dict(entries)
    if set(result) == {"$python_integer"}:
        integer = canonical_integer(result["$python_integer"])
        if integer.bit_length() <= _WORKER_INTEGER_BITS:
            raise ValueError("noncanonical worker integer")
        return integer
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
