"""Declared Alight completion and grid/namespace debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=True,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        stack="stack",
        views=("vars", "walker", "walkers"),
        ip_shape="grid",
    ),
)
