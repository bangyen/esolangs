"""Declared post-halt completion and debugger attributes for minsky_swap."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        ptr="ptr",
        views=("dumped", "ind", "ptr", "reg"),
        ip_shape="offset",
    ),
)
