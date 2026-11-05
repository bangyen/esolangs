"""Declared post-halt completion and debugger attributes for smallfuck."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.POST_HALT,
    debug=DebugSpec(
        ip="ip", memory="memory", ptr="ptr", views=("ptr", "tape"), ip_shape="offset"
    ),
)
