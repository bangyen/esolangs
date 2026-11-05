"""Declared ordinary completion and debugger attributes for abcdirection."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=True,
    debug=DebugSpec(ip="ip", memory="memory", views=("key",), ip_shape="grid"),
)
