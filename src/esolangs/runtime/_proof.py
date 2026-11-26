"""Exact-state termination evidence, separate from output finalization."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, fields
from reprlib import recursive_repr
from typing import NamedTuple

from esolangs.exceptions import EsolangError
from esolangs.results import ExecutionResult
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._validate import _has_backing_type


@dataclass(frozen=True, slots=True)
class BranchFailure:
    """One outcome that faults or would need an external input value."""

    error: EsolangError | None = None


def branch_outcomes[T](
    outcomes: list[T | BranchFailure],
) -> tuple[T | BranchFailure, ...] | None:
    """Keep failed alternatives when they share a transition with other paths."""
    if len(outcomes) == 1 and _has_backing_type(outcome := outcomes[0], BranchFailure):
        if outcome.error is not None:
            raise outcome.error from None
        return None
    return tuple(outcomes)


@dataclass(frozen=True, slots=True)
class BranchProof:
    """Explored transitions and a halted endpoint, or a closed nonhalting graph."""

    root: Hashable
    transitions: tuple[tuple[Hashable, tuple[Hashable, ...]], ...]
    halts: bool
    terminal: Hashable | None = None

    @recursive_repr()
    def __repr__(self) -> str:
        from esolangs.runtime._state import repr_snapshot_record

        return repr_snapshot_record(self, fields(BranchProof))

    def __post_init__(self) -> None:
        """Require immutable, root-reachable evidence and a valid endpoint/closure."""
        transitions = self.transitions
        if type(transitions) is not tuple or any(
            type(row) is not tuple or len(row) != 2 or type(row[1]) is not tuple
            for row in transitions
        ):
            transitions = _freeze_transitions(transitions)
            object.__setattr__(self, "transitions", transitions)
        graph = dict(transitions)
        if len(graph) != len(transitions) or type(self.halts) is not bool:
            raise ValueError("invalid branching evidence")
        reachable: set[Hashable] = set()
        pending = [self.root]
        while pending:
            state = pending.pop()
            if state not in reachable:
                reachable.add(state)
                pending.extend(graph.get(state, ()))
        if graph.keys() - reachable:
            raise ValueError("branching evidence contains unreachable states")
        if self.halts:
            if self.terminal not in reachable:
                raise ValueError("branching halt needs a reached endpoint")
            if self.terminal in graph:
                raise ValueError("branching terminal cannot have outgoing transitions")
        elif (
            self.terminal is not None
            or self.root not in graph
            or any(not outcomes for outcomes in graph.values())
            or any(
                next_state not in graph for row in graph.values() for next_state in row
            )
        ):
            raise ValueError("branching divergence needs a closed graph")

    @property
    def states_examined(self) -> int:
        """Count explored nonhalting states plus the first halted endpoint."""
        return len(self.transitions) + self.halts

    @property
    def forked(self) -> bool:
        """Whether an explored transition had multiple possible outcomes."""
        return any(len(successors) > 1 for _, successors in self.transitions)


def _freeze_transitions(
    transitions: tuple[tuple[Hashable, tuple[Hashable, ...]], ...],
) -> tuple[tuple[Hashable, tuple[Hashable, ...]], ...]:
    """Validate and freeze actual tuple storage at every graph level."""
    if not _has_backing_type(transitions, tuple):
        raise ValueError("invalid branching evidence containers")
    rows = []
    for row in tuple.__iter__(transitions):
        if not _has_backing_type(row, tuple) or tuple.__len__(row) != 2:
            raise ValueError("invalid branching evidence containers")
        state, successors = tuple.__iter__(row)
        if not _has_backing_type(successors, tuple):
            raise ValueError("invalid branching evidence containers")
        rows.append((state, tuple(tuple.__iter__(successors))))
    return tuple(rows)


class _BranchResult(NamedTuple):
    halts: bool
    forked: bool
    proof: BranchProof | None


class CycleDecision(NamedTuple):
    """A proved halt or exact repetition; branching counts states, not commands."""

    halts: bool
    commands: int | None
    cycle: BoundaryCycle | None = None
    branches: BranchProof | None = None

    def __repr__(self) -> str:
        from esolangs.runtime.memory import repr_value

        return (
            f"{type(self).__name__}(halts={self.halts!r}, "
            f"commands={repr_value(self.commands)}, cycle={self.cycle!r}, "
            f"branches={self.branches!r})"
        )


def checked_decision(value: object) -> CycleDecision:
    """Reject Boolean returns and decisions missing their claimed evidence."""
    if not _has_backing_type(value, CycleDecision) or type(value.halts) is not bool:
        raise ValueError("termination requires decision evidence")
    if value.branches is not None:
        if (
            not _has_backing_type(value.branches, BranchProof)
            or value.branches.halts is not value.halts
            or value.cycle is not None
            or value.commands is not None
        ):
            raise ValueError("invalid branching decision")
        if value.halts and value.branches.forked:
            raise ValueError("branching halt depends on this run's draws")
    elif type(value.commands) is not int or value.commands < 0:
        raise ValueError("a deterministic decision needs its command count")
    elif value.halts:
        if value.cycle is not None:
            raise ValueError("a halted decision cannot claim a cycle")
    elif (
        not _has_backing_type(value.cycle, BoundaryCycle)
        or value.cycle.commands_per_pass != 1
        or value.cycle.repeat_pass != value.commands
    ):
        raise ValueError("divergence requires command-boundary evidence")
    return value


class TerminationResult(NamedTuple):
    """Live IO observation and a proof; output finalization has not been requested."""

    observation: ExecutionResult
    decision: CycleDecision


def checked_termination(value: object) -> TerminationResult:
    """Require observed IO and valid proof without claiming finalized output."""
    if (
        not _has_backing_type(value, TerminationResult)
        or not _has_backing_type(value.observation, ExecutionResult)
        or not _has_backing_type(value.observation.output, str)
        or value.observation.completion is not None
    ):
        raise ValueError("termination requires an unfinalized IO observation")
    checked_decision(value.decision)
    steps = value.observation.steps
    if steps is not None and (
        type(steps) is not int or steps != value.decision.commands
    ):
        raise ValueError("execution steps disagree with termination evidence")
    return value
