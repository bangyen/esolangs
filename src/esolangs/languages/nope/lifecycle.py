"""Declared ordinary completion and debugger attributes for nope."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(ip="ip", views=(), ip_shape="offset"),
)
