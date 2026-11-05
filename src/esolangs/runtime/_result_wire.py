"""Lossless JSON transport for execution counters and boundary-cycle evidence."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any, cast

from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._result import ExecutionResult


def _state_wire(state: Hashable) -> Any:
    """Tag immutable containers so JSON cannot turn snapshots into lists."""
    if state is None or type(state) in (str, int, bool, float):
        return state
    if isinstance(state, bytes):
        return {"bytes": state.hex()}
    if isinstance(state, tuple):
        return {"tuple": [_state_wire(value) for value in state]}
    if isinstance(state, frozenset):
        return {"frozenset": [_state_wire(value) for value in state]}
    raise ValueError(f"unsupported cycle state: {type(state).__name__}")


def _state_from_wire(value: Any) -> Hashable:
    """Restore supported immutable snapshots, refusing untagged containers."""
    if value is None or type(value) in (str, int, bool, float):
        return cast("Hashable", value)
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("invalid cycle state")
    if "bytes" in value and isinstance(value["bytes"], str):
        return bytes.fromhex(value["bytes"])
    for key, build in (("tuple", tuple), ("frozenset", frozenset)):
        if key in value and isinstance(value[key], list):
            return build(_state_from_wire(item) for item in value[key])
    raise ValueError("invalid cycle state tag")


def _counter(value: Any) -> int:
    """Require an actual nonnegative integer, including for cycle boundaries."""
    if type(value) is not int or value < 0:
        raise ValueError("invalid execution counter")
    return value


def encode_result(result: ExecutionResult) -> dict[str, Any]:
    """Encode metadata separately from the protocol's output string."""
    report = result.completion
    cycle = report.cycle if report is not None else None
    return {
        "input_position": result.input_position,
        "input_reads": result.input_reads,
        "input_past_end": result.input_past_end,
        "completion": None
        if report is None
        else {
            "kind": report.kind.value,
            "cycle": None
            if cycle is None
            else {
                "state": _state_wire(cycle.state),
                "first_pass": cycle.first_pass,
                "repeat_pass": cycle.repeat_pass,
                "commands_per_pass": cycle.commands_per_pass,
            },
        },
    }


def decode_result(output: Any, metadata: Any) -> ExecutionResult:
    """Validate worker metadata before publishing a successful result."""
    if not isinstance(output, str) or not isinstance(metadata, dict):
        raise ValueError("invalid execution result")
    counters = tuple(
        None if metadata[key] is None else _counter(metadata[key])
        for key in ("input_position", "input_reads", "input_past_end")
    )
    report = None
    if metadata["completion"] is not None:
        declared = metadata["completion"]
        if not isinstance(declared, dict):
            raise ValueError("invalid completion report")
        cycle = None
        if declared["cycle"] is not None:
            evidence = declared["cycle"]
            if not isinstance(evidence, dict):
                raise ValueError("invalid boundary cycle")
            cycle = BoundaryCycle(
                _state_from_wire(evidence["state"]),
                _counter(evidence["first_pass"]),
                _counter(evidence["repeat_pass"]),
                _counter(evidence["commands_per_pass"]),
            )
        report = CompletionReport(Completion(declared["kind"]), cycle)
    return ExecutionResult(output, counters[0], counters[1], counters[2], report)
