"""Declared post-halt completion and debugger attributes for ram0."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        views=("dumped", "ind", "n", "ram", "z"),
        ip_shape="offset",
    ),
)
