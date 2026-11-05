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


def completion(machine: object) -> Completion:
    """Read an explicit policy, adapting unmigrated machine traits."""
    policy = getattr(machine, "completion", None)
    if policy is not None:
        if not isinstance(policy, Completion):
            raise TypeError("completion must be a Completion policy")
        return policy
    if getattr(machine, "dumps_on_the_post_halt_step", False):
        return Completion.POST_HALT
    if not getattr(machine, "steppable_to_answer", True):
        return Completion.PERIODIC
    return Completion.HALTED
