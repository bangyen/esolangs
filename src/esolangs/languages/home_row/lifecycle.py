"""Declared ordinary completion and debugger attributes for home_row."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        ptr="ptr",
        views=("grid", "ind", "ptr"),
        ip_shape="offset",
    ),
)
