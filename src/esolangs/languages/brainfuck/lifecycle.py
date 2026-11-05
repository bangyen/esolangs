"""Declared completion and debugger attributes for brainfuck."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    debug=DebugSpec(ip="ip", memory="memory", ptr="ptr", views=("ind", "ptr", "tape")),
)
