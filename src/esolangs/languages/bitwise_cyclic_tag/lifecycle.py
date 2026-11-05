"""Declared post-halt completion and debugger attributes for bitwise_cyclic_tag."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        views=("answer", "head", "live", "read"),
        ip_shape="offset",
    ),
)
