"""Declared post-halt completion and debugger attributes for bitdeque."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        memory="memory",
        stack="stack",
        ip="ind",
        views=("deq", "ind", "reg", "rendered"),
        ip_shape="offset",
    ),
)
