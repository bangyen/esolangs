"""Declared Piet completion and grid/stack debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    supports_scale=True,
    eof_is_a_value=True,
    debug=DebugSpec(
        ip="ip", stack="stack", views=("cc", "current", "dp"), ip_shape="grid"
    ),
)
