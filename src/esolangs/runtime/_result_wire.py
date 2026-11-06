"""Lossless JSON transport for execution counters and boundary-cycle evidence."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import fields, is_dataclass
from fractions import Fraction
from functools import cache
from importlib import import_module
from math import isfinite
from typing import Any, cast

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
    """Resolve an explicitly declared codec from a registered interpreter."""
    from esolangs.registry import INTERPRETERS

    if module_name not in INTERPRETERS.values():
        raise ValueError("unregistered snapshot codec module")
    for codec in getattr(import_module(module_name), "SNAPSHOT_CODECS", ()):
        if (
            isinstance(codec, SnapshotCodec)
            and codec.cls.__module__ == module_name
            and codec.cls.__qualname__ == name
        ):
            return codec
    raise ValueError("undeclared snapshot codec")


def _state_wire(state: Hashable) -> Any:
    """Tag immutable containers so JSON cannot turn snapshots into lists."""
    if type(state) is float and not isfinite(state):
        raise ValueError("non-finite cycle state")
    # A valid program's integers can exceed Python's decimal rendering cap.
    if type(state) is int and state.bit_length() > 1024:
        return {"int": hex(state)}
    if state is None or type(state) in (str, int, bool, float):
        return state
    if type(state) is Fraction:
        return {"fraction": [hex(state.numerator), hex(state.denominator)]}
    if isinstance(state, bytes):
        return {"bytes": state.hex()}
    if isinstance(state, tuple):
        return {"tuple": [_state_wire(value) for value in state]}
    if isinstance(state, frozenset):
        return {"frozenset": [_state_wire(value) for value in state]}
    if not isinstance(state, type) and is_dataclass(type(state)):
        cls = _record_type(type(state).__module__, type(state).__qualname__)
        return {
            "record": {
                "module": cls.__module__,
                "name": cls.__qualname__,
                "fields": {
                    field.name: _state_wire(getattr(state, field.name))
                    for field in fields(cls)
                },
            }
        }
    codec = _owned_codec(type(state).__module__, type(state).__qualname__)
    return {
        "owned": {
            "module": codec.cls.__module__,
            "name": codec.cls.__qualname__,
            "value": _state_wire(codec.encode(state)),
        }
    }


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


def _owned_from_wire(owned: Any) -> Hashable:
    """Restore declared owned values, normalizing malformed payload failures."""
    if (
        not isinstance(owned, dict)
        or set(owned) != {"module", "name", "value"}
        or not isinstance(owned["module"], str)
        or not isinstance(owned["name"], str)
    ):
        raise ValueError("invalid owned snapshot")
    codec = _owned_codec(owned["module"], owned["name"])
    payload = _state_from_wire(owned["value"])
    try:
        decoded_value = codec.decode(payload)
    except TypeError as error:
        raise ValueError("invalid owned snapshot payload") from error
    if type(decoded_value) is not codec.cls or codec.encode(decoded_value) != payload:
        raise ValueError("noncanonical owned snapshot")
    hash(decoded_value)
    return cast("Hashable", decoded_value)


def _state_from_wire(value: Any) -> Hashable:
    """Restore supported immutable snapshots, refusing untagged containers."""
    if type(value) is float and not isfinite(value):
        raise ValueError("non-finite cycle state")
    if value is None or type(value) in (str, int, bool, float):
        return cast("Hashable", value)
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("invalid cycle state")
    if "bytes" in value and isinstance(value["bytes"], str):
        decoded = bytes.fromhex(value["bytes"])
        if decoded.hex() != value["bytes"]:
            raise ValueError("noncanonical cycle bytes")
        return decoded
    if "int" in value:
        return canonical_integer(value["int"])
    if "fraction" in value:
        return _fraction_from_wire(value["fraction"])
    if "owned" in value:
        return _owned_from_wire(value["owned"])
    if "record" in value:
        record = value["record"]
        if (
            not isinstance(record, dict)
            or set(record) != {"module", "name", "fields"}
            or not isinstance(record["fields"], dict)
        ):
            raise ValueError("invalid snapshot record")
        if not isinstance(record["module"], str) or not isinstance(record["name"], str):
            raise ValueError("invalid snapshot record type")
        cls = _record_type(record["module"], record["name"])
        if set(record["fields"]) != {field.name for field in fields(cls)}:
            raise ValueError("invalid snapshot record fields")
        return cast(
            "Hashable",
            cls(
                **{
                    key: _state_from_wire(item)
                    for key, item in record["fields"].items()
                }
            ),
        )
    for key, build in (("tuple", tuple), ("frozenset", frozenset)):
        if key in value and isinstance(value[key], list):
            items = tuple(_state_from_wire(item) for item in value[key])
            decoded_items = build(items)
            if len(decoded_items) != len(items):
                raise ValueError("duplicate cycle state member")
            return decoded_items
    raise ValueError("invalid cycle state tag")


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
    counters = tuple(
        None if metadata[key] is None else _counter(metadata[key])
        for key in ("input_position", "input_reads", "input_past_end")
    )
    report = None
    if metadata["completion"] is not None:
        declared = metadata["completion"]
        if not isinstance(declared, dict) or set(declared) != {"kind", "cycle"}:
            raise ValueError("invalid completion report")
        cycle = _cycle_from_wire(declared["cycle"])
        report = CompletionReport(Completion(declared["kind"]), cycle)
    steps = metadata["steps"]
    return ExecutionResult(
        output,
        counters[0],
        counters[1],
        counters[2],
        report,
        None if steps is None else _counter(steps),
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
            "root": _state_wire(branch.root),
            "transitions": [
                [_state_wire(state), [_state_wire(target) for target in outcomes]]
                for state, outcomes in branch.transitions
            ],
            "halts": branch.halts,
            "terminal": _state_wire(branch.terminal),
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
            or set(value) != {"root", "transitions", "halts", "terminal"}
            or not isinstance(value["transitions"], list)
        ):
            raise ValueError("invalid branching evidence")
        transitions = []
        for row in value["transitions"]:
            if (
                not isinstance(row, list)
                or len(row) != 2
                or not isinstance(row[1], list)
            ):
                raise ValueError("invalid branching transition")
            transitions.append(
                (
                    _state_from_wire(row[0]),
                    tuple(_state_from_wire(target) for target in row[1]),
                )
            )
        branch = BranchProof(
            _state_from_wire(value["root"]),
            tuple(transitions),
            halts=value["halts"],
            terminal=_state_from_wire(value["terminal"]),
        )
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
