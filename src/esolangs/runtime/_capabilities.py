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
