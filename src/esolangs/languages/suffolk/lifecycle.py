"""Declared stepped completion and native cycle reports for suffolk."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    self_halts=False,
    debug=DebugSpec(
        ip="ip",
        memory="memory",
        ptr="ptr",
        views=("acc", "clamp_slack", "ind", "key", "ptr", "tape", "values"),
    ),
    native_completions=frozenset((Completion.HALTED, Completion.PERIODIC)),
)
