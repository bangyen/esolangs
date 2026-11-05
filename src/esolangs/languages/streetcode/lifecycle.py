"""Declared cached preparation and grid debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(
        ip="ip", memory="memory", views=("col", "heading", "row"), ip_shape="grid"
    ),
)
