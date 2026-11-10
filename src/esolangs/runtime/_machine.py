"""Typed preparation of a source into fresh step machines."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from esolangs._cycles import _StepMachine
    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO
    from esolangs.runtime.randomness import Randomness


type MachineFactory = Callable[[IO], _StepMachine]


class MachinePreparation(Protocol):
    """Prepare source and options; each factory call owns fresh state."""

    def __call__(
        self, source: RunnerProgram, options: Mapping[str, Any], /
    ) -> MachineFactory:
        """Return an IO-bound machine factory without consuming input."""


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    """Language-owned parsed source shared by native runs and fresh machines.

    Both callables must create invocation state; retained parse data is read-only.
    """

    machine: MachineFactory
    run: Callable[[IO], CompletionReport]
    random_source: RandomRuntimePlan | None = field(
        default=None, repr=False, compare=False
    )

    def __call__(self, io: IO) -> _StepMachine:
        """Construct independent state from the retained parse data."""
        return self.machine(io)


@dataclass(frozen=True, slots=True)
class RandomRuntimePlan:
    """Read-only parsed source with randomness supplied for each invocation."""

    machine: Callable[[IO, Randomness | None], _StepMachine]
    run: Callable[[IO, Randomness | None], CompletionReport]

    def bind(self, rng: Randomness | None) -> RuntimePlan:
        """Bind caller-owned randomness without retaining it in the source plan."""
        return RuntimePlan(
            lambda io: self.machine(io, rng),
            lambda io: self.run(io, rng),
            random_source=self,
        )
