"""Declared output completion and evidence from periodic execution."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from enum import StrEnum


class Completion(StrEnum):
    """When a machine's final output can be written."""

    HALTED = "halted"
    POST_HALT = "post_halt"
    PERIODIC = "periodic"


@dataclass(frozen=True, slots=True)
class BoundaryCycle:
    """Equal snapshots at two pass boundaries, measured in whole passes."""

    state: Hashable
    first_pass: int
    repeat_pass: int
    commands_per_pass: int

    def __post_init__(self) -> None:
        """Require ordered boundaries and a nonnegative command count."""
        if (
            self.first_pass < 0
            or self.repeat_pass <= self.first_pass
            or self.commands_per_pass < 0
        ):
            raise ValueError("a boundary cycle needs ordered passes and a stride")


@dataclass(frozen=True, slots=True)
class CompletionReport:
    """Successful completion; periodic output retains its boundary-cycle evidence."""

    kind: Completion
    cycle: BoundaryCycle | None = None

    def __post_init__(self) -> None:
        """Require cycle evidence exactly for periodic completion."""
        if not isinstance(self.kind, Completion):
            raise ValueError("completion kind must be a Completion policy")
        if self.kind is Completion.PERIODIC:
            if not isinstance(self.cycle, BoundaryCycle):
                raise ValueError("periodic completion requires cycle evidence")
        elif self.cycle is not None:
            raise ValueError("only periodic completion accepts cycle evidence")


def completion(machine: object) -> Completion:
    """Read a declared policy; ordinary machines complete at halt."""
    policy = getattr(machine, "completion", Completion.HALTED)
    if not isinstance(policy, Completion):
        raise TypeError("completion must be a Completion policy")
    return policy
