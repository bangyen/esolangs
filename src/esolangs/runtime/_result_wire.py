"""Lossless JSON transport for execution counters and boundary-cycle evidence."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import fields, is_dataclass
from fractions import Fraction
from functools import cache, lru_cache
from importlib import import_module
from math import isfinite
from typing import Any, NamedTuple, cast

from esolangs.results import ExecutionResult
from esolangs.runtime._json import canonical_integer
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._proof import (
    BranchProof,
    CycleDecision,
    TerminationResult,
    checked_decision,
    checked_termination,
)
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
    identity: int | None


def _state_wire(state: Hashable) -> Any:
    """Tag immutable snapshots, referring back to completed shared nodes."""
    result: list[Any] = [None]
    pending: list[_EncodeTask] = [_EncodeTask("visit", state, result, 0, None)]
    active: set[int] = set()
    completed: dict[int, _EncodeTask] = {}
    references: dict[int, int] = {}
    while pending:
        task = pending.pop()
        action, node, parent, key, attribute = task
        if action == "finish":
            active.remove(id(node))
            # Keep a strong reference and its first wire slot until the walk ends.
            completed[id(node)] = task
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
            first = completed.get(identity)
            if first is not None:
                reference = references.get(identity)
                if reference is None:
                    reference = len(references)
                    references[identity] = reference
                    assert first.key is not None
                    first.parent[first.key] = {
                        "define": [reference, first.parent[first.key]]
                    }
                parent[key] = {"ref": reference}
                continue
            active.add(identity)
            pending.append(_EncodeTask("finish", node, parent, key, None))
            cls = type(node)
            codec = (
                _tuple_owned_codec(cls)
                if cls is not tuple and type(cls) is type and issubclass(cls, tuple)
                else None
            )
            if codec is None and isinstance(node, (tuple, frozenset)):
                values = [value for value in node]  # noqa: C416 - preserve iteration without length hints
                items: list[Any] = [None] * len(values)
                parent[key] = {
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
                parent[key] = {
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
                parent[key] = {"owned": owned}
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
    node: dict[str, Any], parent: Any, key: str | int, pending: list[_DecodeTask]
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
        pending.append(_DecodeTask("owned", codec, payload, parent, key, id(node)))
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
        pending.append(_DecodeTask("record", cls, arguments, parent, key, id(node)))
        pending.extend(
            _DecodeTask("visit", record["fields"][name], None, arguments, name, None)
            for name in reversed(names)
        )
    else:
        tag = next(iter(node))
        if tag not in ("tuple", "frozenset") or not isinstance(node[tag], list):
            raise ValueError("invalid cycle state tag")
        decoded_values: list[Any] = [None] * len(node[tag])
        pending.append(_DecodeTask(tag, None, decoded_values, parent, key, id(node)))
        pending.extend(
            _DecodeTask("visit", node[tag][index], None, decoded_values, index, None)
            for index in reversed(range(len(node[tag])))
        )


def _state_from_wire(value: Any) -> Hashable:
    """Restore tagged immutable snapshots with an explicit build stack."""
    result: list[Any] = [None]
    pending: list[_DecodeTask] = [_DecodeTask("visit", value, None, result, 0, None)]
    active: set[int] = set()
    declared: set[int] = set()
    definitions: dict[int, Hashable] = {}
    used: set[int] = set()
    while pending:
        action, node, items, parent, key, identity = pending.pop()
        if action != "visit":
            assert identity is not None
            if action == "define":
                definitions[node] = parent[key] = items[0]
            elif action == "record":
                parent[key] = node(**items)
            elif action == "owned":
                parent[key] = _owned_from_wire(node, items[0])
            else:
                decoded_items = tuple(items) if action == "tuple" else frozenset(items)
                if len(decoded_items) != len(items):
                    raise ValueError("duplicate cycle state member")
                parent[key] = decoded_items
            active.remove(identity)
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
            used.add(reference)
        elif "bytes" in node and isinstance(node["bytes"], str):
            parent[key] = _bytes_from_wire(node["bytes"])
        elif "int" in node:
            parent[key] = canonical_integer(node["int"])
        elif "fraction" in node:
            parent[key] = _fraction_from_wire(node["fraction"])
        else:
            if id(node) in active:
                raise ValueError("cyclic cycle state")
            active.add(id(node))
            if "define" in node:
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
                if reference in declared:
                    raise ValueError("duplicate snapshot reference definition")
                declared.add(reference)
                shared: list[Any] = [None]
                pending.append(
                    _DecodeTask("define", reference, shared, parent, key, id(node))
                )
                pending.append(
                    _DecodeTask("visit", definition[1], None, shared, 0, None)
                )
            else:
                _schedule_compound(node, parent, key, pending)
    if declared != used:
        raise ValueError("unused snapshot reference definition")
    return cast("Hashable", result[0])


def _counter(value: Any) -> int:
    """Require an actual nonnegative integer, including for cycle boundaries."""
    if type(value) is not int or value < 0:
        raise ValueError("invalid execution counter")
    return value


def _cycle_wire(cycle: BoundaryCycle | None) -> dict[str, Any] | None:
    if cycle is None:
        return None
    return {
        "state": _state_wire(cycle.state),
        "first_pass": cycle.first_pass,
        "repeat_pass": cycle.repeat_pass,
        "commands_per_pass": cycle.commands_per_pass,
    }


def _cycle_from_wire(value: Any) -> BoundaryCycle | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "state",
        "first_pass",
        "repeat_pass",
        "commands_per_pass",
    }:
        raise ValueError("invalid boundary cycle")
    return BoundaryCycle(
        _state_from_wire(value["state"]),
        _counter(value["first_pass"]),
        _counter(value["repeat_pass"]),
        _counter(value["commands_per_pass"]),
    )


def encode_result(result: ExecutionResult) -> dict[str, Any]:
    """Encode metadata separately from the protocol's output string."""
    report = result.completion
    cycle = report.cycle if report is not None else None
    return {
        "steps": result.steps,
        "input_position": result.input_position,
        "input_reads": result.input_reads,
        "input_past_end": result.input_past_end,
        "completion": None
        if report is None
        else {
            "kind": report.kind.value,
            "cycle": _cycle_wire(cycle),
        },
    }


def decode_result(output: Any, metadata: Any) -> ExecutionResult:
    """Validate worker metadata before publishing a successful result."""
    if (
        not isinstance(output, str)
        or not isinstance(metadata, dict)
        or set(metadata)
        != {"steps", "input_position", "input_reads", "input_past_end", "completion"}
    ):
        raise ValueError("invalid execution result")
    report = None
    if metadata["completion"] is not None:
        declared = metadata["completion"]
        if not isinstance(declared, dict) or set(declared) != {"kind", "cycle"}:
            raise ValueError("invalid completion report")
        cycle = _cycle_from_wire(declared["cycle"])
        report = CompletionReport(Completion(declared["kind"]), cycle)
    return ExecutionResult(
        output,
        metadata["input_position"],
        metadata["input_reads"],
        metadata["input_past_end"],
        completion=report,
        steps=metadata["steps"],
    )


def encode_decision(decision: CycleDecision) -> dict[str, Any]:
    """Encode exact-state or complete branching evidence, never a bare verdict."""
    checked_decision(decision)
    branch = decision.branches
    return {
        "halts": decision.halts,
        "commands": decision.commands,
        "cycle": _cycle_wire(decision.cycle),
        "branches": None
        if branch is None
        else {
            "halts": branch.halts,
            # Successors reuse states and their immutable workspace storage.
            "graph": _state_wire((branch.root, branch.transitions, branch.terminal)),
        },
    }


def decode_decision(metadata: Any) -> CycleDecision:
    """Validate all proof fields before a worker can decide termination."""
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"halts", "commands", "cycle", "branches"}
        or type(metadata["halts"]) is not bool
    ):
        raise ValueError("invalid termination decision")
    branch = None
    if metadata["branches"] is not None:
        value = metadata["branches"]
        if (
            not isinstance(value, dict)
            or set(value) != {"graph", "halts"}
            or type(value["halts"]) is not bool
        ):
            raise ValueError("invalid branching evidence")
        graph = _state_from_wire(value["graph"])
        if type(graph) is not tuple or len(graph) != 3 or type(graph[1]) is not tuple:
            raise ValueError("invalid branching evidence graph")
        root, transitions, terminal = graph
        if any(
            type(row) is not tuple or len(row) != 2 or type(row[1]) is not tuple
            for row in transitions
        ):
            raise ValueError("invalid branching transition")
        branch = BranchProof(root, transitions, halts=value["halts"], terminal=terminal)
    return checked_decision(
        CycleDecision(
            halts=metadata["halts"],
            commands=None
            if metadata["commands"] is None
            else _counter(metadata["commands"]),
            cycle=_cycle_from_wire(metadata["cycle"]),
            branches=branch,
        )
    )


def decode_termination(output: Any, execution: Any, proof: Any) -> TerminationResult:
    """Restore one observed execution and its validated termination evidence."""
    return checked_termination(
        TerminationResult(decode_result(output, execution), decode_decision(proof))
    )
