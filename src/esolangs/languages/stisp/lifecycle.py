"""Declared post-halt completion and debugger attributes for stisp."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(ip="ip", stack="stack", views=(), ip_shape="opaque"),
)
