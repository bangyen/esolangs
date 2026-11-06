"""Declared Fargo completion and debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=True,
    debug=DebugSpec(
        ip="ind", memory="memory", stack="stack", views=("frames", "ind", "number")
    ),
)
