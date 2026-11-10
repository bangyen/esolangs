"""Typed preparation of a source into fresh step machines."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from esolangs._cycles import _StepMachine
    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO


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

    def __call__(self, io: IO) -> _StepMachine:
        """Construct independent state from the retained parse data."""
        return self.machine(io)
