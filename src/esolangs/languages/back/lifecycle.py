"""Declared post-halt completion and debugger attributes for back."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        ptr="ptr",
        views=("a", "b", "cell", "col", "dumped", "ptr", "row", "tape"),
        ip_shape="grid",
    ),
)
