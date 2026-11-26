"""Lossless JSON transport for execution counters and boundary-cycle evidence."""

from __future__ import annotations

from typing import Any

from esolangs.results import ExecutionResult
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._proof import (
    BranchProof,
    CycleDecision,
    TerminationResult,
    checked_decision,
    checked_termination,
)
from esolangs.runtime._snapshot_wire import _state_from_wire, _state_wire


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
