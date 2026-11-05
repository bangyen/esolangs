"""Typed preparation of a source into fresh step machines."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from esolangs._cycles import _StepMachine
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO


type MachineFactory = Callable[[IO], _StepMachine]


class MachinePreparation(Protocol):
    """Prepare source and options; each factory call owns fresh state."""

    def __call__(
        self, source: RunnerProgram, options: Mapping[str, Any], /
    ) -> MachineFactory:
        """Return an IO-bound machine factory without consuming input."""
