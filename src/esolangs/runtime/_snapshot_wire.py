"""Lossless transport for shared immutable snapshot graphs."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import fields, is_dataclass
from fractions import Fraction
from functools import cache, lru_cache
from importlib import import_module
from math import isfinite
from typing import Any, NamedTuple, cast

from esolangs.runtime._json import canonical_integer
from esolangs.runtime._snapshot import SnapshotCodec


@cache
def _record_type(module_name: str, name: str) -> type[Any]:
    """Resolve only frozen record types declared by a registered interpreter."""
    from esolangs.registry import INTERPRETERS

    if module_name not in INTERPRETERS.values():
        raise ValueError("unregistered snapshot record module")
    for cls in getattr(import_module(module_name), "SNAPSHOT_RECORDS", ()):
        params = getattr(cls, "__dataclass_params__", None)
        if (
            isinstance(cls, type)
            and cls.__module__ == module_name
            and cls.__qualname__ == name
            and is_dataclass(cls)
            and params is not None
            and params.frozen
            and all(field.init for field in fields(cls))
        ):
            return cls
    raise ValueError("undeclared immutable snapshot record")


@cache
def _owned_codec(module_name: str, name: str) -> SnapshotCodec[Any]:
    """Resolve codecs from registered interpreters and named implementation modules."""
    from esolangs.registry import INTERPRETERS

    if (
        module_name
        not in (
            "esolangs.runtime.bit_tape",
            "esolangs.languages.streetcode.interpreter.geometry",
        )
        and module_name not in INTERPRETERS.values()
    ):
        raise ValueError("unregistered snapshot codec module")
    for codec in getattr(import_module(module_name), "SNAPSHOT_CODECS", ()):
        if (
            isinstance(codec, SnapshotCodec)
            and codec.cls.__module__ == module_name
            and codec.cls.__qualname__ == name
        ):
            return codec
    raise ValueError("undeclared snapshot codec")


@lru_cache(maxsize=64)
def _tuple_owned_codec(cls: type[Any]) -> SnapshotCodec[Any] | None:
    """Keep an owned tuple type only when the declaration names that exact class."""
    module_name, name = cls.__module__, cls.__qualname__
    if type(module_name) is not str or type(name) is not str:
        return None
    try:
        codec = _owned_codec(module_name, name)
    except ValueError:
        return None
    return codec if codec.cls is cls else None


class _EncodeTask(NamedTuple):
    """A snapshot visit, delayed field access, or completed ancestor."""

    action: str
    node: Any
    parent: Any
    key: str | int | None
    attribute: str | None


class _DecodeTask(NamedTuple):
    """A wire visit or bottom-up immutable value construction."""

    action: str
    node: Any
    items: Any
    parent: Any
    key: str | int
    reference: int | None


def _state_wire(state: Hashable) -> Any:
    """Define each compound snapshot node once and refer back to it by ID."""
    result: list[Any] = [None]
    pending: list[_EncodeTask] = [_EncodeTask("visit", state, result, 0, None)]
    active: set[int] = set()
    # Keep the nodes alive so temporary codec payloads cannot reuse their IDs.
    references: dict[int, tuple[Hashable, int]] = {}
    while pending:
        task = pending.pop()
        action, node, parent, key, attribute = task
        if action == "finish":
            active.remove(id(node))
            continue
        assert key is not None
        if attribute is not None:
            node = getattr(node, attribute)
        if type(node) is float and (not isfinite(node)):
            raise ValueError("non-finite cycle state")
        # Valid integers may exceed CPython's decimal rendering cap.
        if type(node) is int and node.bit_length() > 1024:
            parent[key] = {"int": hex(node)}
        elif node is None or type(node) in (str, int, bool, float):
            parent[key] = node
        elif type(node) is Fraction:
            parent[key] = {"fraction": [hex(node.numerator), hex(node.denominator)]}
        elif isinstance(node, bytes):
            parent[key] = {"bytes": node.hex()}
        else:
            identity = id(node)
            if identity in active:
                raise ValueError("cyclic cycle state")
            first = references.get(identity)
            if first is not None:
                parent[key] = {"ref": first[1]}
                continue
            reference = len(references)
            references[identity] = (node, reference)
            definition: list[Any] = [reference, None]
            parent[key] = {"define": definition}
            active.add(identity)
            pending.append(_EncodeTask("finish", node, None, None, None))
            cls = type(node)
            codec = (
                _tuple_owned_codec(cls)
                if cls is not tuple and type(cls) is type and issubclass(cls, tuple)
                else None
            )
            if codec is None and isinstance(node, (tuple, frozenset)):
                values = [value for value in node]  # noqa: C416 - preserve iteration without length hints
                items: list[Any] = [None] * len(values)
                definition[1] = {
                    "tuple" if isinstance(node, tuple) else "frozenset": items
                }
                pending.extend(
                    _EncodeTask("visit", values[index], items, index, None)
                    for index in reversed(range(len(values)))
                )
            elif codec is None and not isinstance(node, type) and is_dataclass(cls):
                cls = _record_type(cls.__module__, cls.__qualname__)
                declared = fields(cls)
                values_by_name: dict[str, Any] = {
                    field.name: None for field in declared
                }
                definition[1] = {
                    "record": {
                        "module": cls.__module__,
                        "name": cls.__qualname__,
                        "fields": values_by_name,
                    }
                }
                pending.extend(
                    _EncodeTask("visit", node, values_by_name, field.name, field.name)
                    for field in reversed(declared)
                )
            else:
                if codec is None:
                    codec = _owned_codec(cls.__module__, cls.__qualname__)
                owned: dict[str, Any] = {
                    "module": codec.cls.__module__,
                    "name": codec.cls.__qualname__,
                    "value": None,
                }
                definition[1] = {"owned": owned}
                pending.append(
                    _EncodeTask("visit", codec.encode(node), owned, "value", None)
                )
    return result[0]


def _bytes_from_wire(value: str) -> bytes:
    """Require the lowercase compact spelling emitted for immutable bytes."""
    decoded = bytes.fromhex(value)
    if decoded.hex() != value:
        raise ValueError("noncanonical cycle bytes")
    return decoded


def _fraction_from_wire(pair: Any) -> Fraction:
    """Require the reduced positive-denominator representation from Fraction."""
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("invalid snapshot fraction")
    numerator, denominator = map(canonical_integer, pair)
    if denominator <= 0:
        raise ValueError("invalid snapshot denominator")
    fraction = Fraction(numerator, denominator)
    if (fraction.numerator, fraction.denominator) != (numerator, denominator):
        raise ValueError("noncanonical snapshot fraction")
    return fraction


def _owned_from_wire(codec: SnapshotCodec[Any], payload: Hashable) -> Hashable:
    """Restore a validated owned payload, normalizing malformed payload failures."""
    try:
        decoded_value = codec.decode(payload)
    except TypeError as error:
        raise ValueError("invalid owned snapshot payload") from error
    if type(decoded_value) is not codec.cls or codec.encode(decoded_value) != payload:
        raise ValueError("noncanonical owned snapshot")
    hash(decoded_value)
    return cast("Hashable", decoded_value)


def _reference_id(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("invalid snapshot reference id")
    return value


def _schedule_compound(
    node: dict[str, Any],
    parent: Any,
    key: str | int,
    reference: int,
    pending: list[_DecodeTask],
) -> None:
    """Validate a compound and queue its children before building it."""
    if "owned" in node:
        owned = node["owned"]
        if (
            not isinstance(owned, dict)
            or set(owned) != {"module", "name", "value"}
            or (not isinstance(owned["module"], str))
            or (not isinstance(owned["name"], str))
        ):
            raise ValueError("invalid owned snapshot")
        codec = _owned_codec(owned["module"], owned["name"])
        payload: list[Any] = [None]
        pending.append(_DecodeTask("owned", codec, payload, parent, key, reference))
        pending.append(_DecodeTask("visit", owned["value"], None, payload, 0, None))
    elif "record" in node:
        record = node["record"]
        if (
            not isinstance(record, dict)
            or set(record) != {"module", "name", "fields"}
            or (not isinstance(record["fields"], dict))
        ):
            raise ValueError("invalid snapshot record")
        if not isinstance(record["module"], str) or not isinstance(record["name"], str):
            raise ValueError("invalid snapshot record type")
        cls = _record_type(record["module"], record["name"])
        names = tuple(field.name for field in fields(cls))
        if record["fields"].keys() != set(names):
            raise ValueError("invalid snapshot record fields")
        arguments: dict[str, Any] = dict.fromkeys(names)
        pending.append(_DecodeTask("record", cls, arguments, parent, key, reference))
        pending.extend(
            _DecodeTask("visit", record["fields"][name], None, arguments, name, None)
            for name in reversed(names)
        )
    else:
        tag = next(iter(node))
        if tag not in ("tuple", "frozenset") or not isinstance(node[tag], list):
            raise ValueError("invalid cycle state tag")
        decoded_values: list[Any] = [None] * len(node[tag])
        pending.append(_DecodeTask(tag, None, decoded_values, parent, key, reference))
        pending.extend(
            _DecodeTask("visit", node[tag][index], None, decoded_values, index, None)
            for index in reversed(range(len(node[tag])))
        )


def _state_from_wire(value: Any) -> Hashable:
    """Restore tagged immutable snapshots with an explicit build stack."""
    result: list[Any] = [None]
    pending: list[_DecodeTask] = [_DecodeTask("visit", value, None, result, 0, None)]
    next_reference = 0
    definitions: dict[int, Hashable] = {}
    while pending:
        action, node, items, parent, key, reference = pending.pop()
        if action != "visit":
            assert reference is not None
            if action == "record":
                decoded = node(**items)
            elif action == "owned":
                decoded = _owned_from_wire(node, items[0])
            else:
                decoded = tuple(items) if action == "tuple" else frozenset(items)
                if len(decoded) != len(items):
                    raise ValueError("duplicate cycle state member")
            definitions[reference] = parent[key] = decoded
            continue
        if type(node) is float and (not isfinite(node)):
            raise ValueError("non-finite cycle state")
        if node is None or type(node) in (str, int, bool, float):
            parent[key] = node
            continue
        if not isinstance(node, dict) or len(node) != 1:
            raise ValueError("invalid cycle state")
        if "ref" in node:
            reference = _reference_id(node["ref"])
            if reference not in definitions:
                raise ValueError("snapshot reference needs a completed definition")
            parent[key] = definitions[reference]
        elif "bytes" in node and isinstance(node["bytes"], str):
            parent[key] = _bytes_from_wire(node["bytes"])
        elif "int" in node:
            parent[key] = canonical_integer(node["int"])
        elif "fraction" in node:
            parent[key] = _fraction_from_wire(node["fraction"])
        elif "define" in node:
            definition = node["define"]
            if (
                not isinstance(definition, list)
                or len(definition) != 2
                or not isinstance(definition[1], dict)
                or len(definition[1]) != 1
                or next(iter(definition[1]))
                not in ("tuple", "frozenset", "record", "owned")
            ):
                raise ValueError("invalid snapshot reference definition")
            reference = _reference_id(definition[0])
            if reference != next_reference:
                raise ValueError("out-of-order snapshot reference definition")
            next_reference += 1
            _schedule_compound(definition[1], parent, key, reference, pending)
        else:
            raise ValueError("invalid cycle state tag without snapshot definition")
    return cast("Hashable", result[0])
