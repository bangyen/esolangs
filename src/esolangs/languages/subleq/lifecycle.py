"""Declared subleq completion and debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=False,
    debug=DebugSpec(ip="ip", memory="memory", ip_shape="opaque"),
)
