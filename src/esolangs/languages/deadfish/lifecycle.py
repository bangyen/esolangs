"""Declared ordinary completion and debugger attributes for deadfish."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(
        ip="ip", memory="memory", views=("ind", "value"), ip_shape="offset"
    ),
)
