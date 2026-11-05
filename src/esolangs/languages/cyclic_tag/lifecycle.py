"""Cyclic tag completion and debugger attributes independent of its interpreter."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(ip="ip", memory="memory", views=("answer", "head", "live")),
)
