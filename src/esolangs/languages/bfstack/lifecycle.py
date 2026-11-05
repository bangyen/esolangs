"""Declared ordinary completion and debugger attributes for bfstack."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(
        ip="ip", stack="stack", views=("ind", "lst", "stk"), ip_shape="offset"
    ),
)
