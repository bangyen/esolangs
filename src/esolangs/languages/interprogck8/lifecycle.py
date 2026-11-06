"""Declared Interprogck8 completion and line debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(ip="ip", memory="memory", stack="stack", ip_shape="line"),
)
