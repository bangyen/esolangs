"""Declared flowchart completion and grid debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=True,
    debug=DebugSpec(
        ip="ip", memory="memory", views=("deques", "pointers"), ip_shape="grid"
    ),
)
