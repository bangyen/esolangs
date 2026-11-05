"""Declared completion and debugger surfaces without loading an interpreter."""

from dataclasses import dataclass
from typing import Literal

from esolangs.runtime._lifecycle import Completion

type IpShape = Literal["offset", "grid", "line", "opaque"]


@dataclass(frozen=True)
class DebugSpec:
    """Explicit machine attributes; absent views expose no state."""

    ip: str | None = None
    memory: str | None = None
    ptr: str | None = None
    stack: str | None = None
    views: tuple[str, ...] = ()
    ip_shape: IpShape = "offset"


@dataclass(frozen=True)
class MachineCapabilities:
    """Completion policy and optional debugger attributes for a machine factory."""

    completion: Completion = Completion.HALTED
    self_halts: bool = True
    eof_is_a_value: bool = False
    debug: DebugSpec | None = None
    #: Native execution may prove a repeat before the stepped EOF halt.
    native_completions: frozenset[Completion] | None = None

    def accepts_native(self, kind: Completion) -> bool:
        """Whether the native runner declares this completion kind."""
        if self.native_completions is None:
            return kind is self.completion
        return kind in self.native_completions
