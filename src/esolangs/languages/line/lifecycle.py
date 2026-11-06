"""Declared Line raster preparation and grid debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    supports_scale=True,
    debug=DebugSpec(ip="ip", memory="memory", ip_shape="grid"),
)
