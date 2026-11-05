"""Declared stepped completion and native cycle reports for a_painter_ant."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.PERIODIC,
    self_halts=False,
    debug=DebugSpec(ip="ip", memory="memory"),
)
