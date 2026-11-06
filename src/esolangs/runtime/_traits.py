"""Driving traits from explicit runtime capabilities."""

from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._lifecycle import Completion

_TRAITS = (
    "self_halts",
    "dumps_on_the_post_halt_step",
    "steppable_to_answer",
    "eof_is_a_value",
)


def trait(capabilities: MachineCapabilities, name: str) -> bool:
    """Return one declared or completion-derived driving trait."""
    if name == "dumps_on_the_post_halt_step":
        return capabilities.completion is Completion.POST_HALT
    if name == "steppable_to_answer":
        return capabilities.completion is not Completion.PERIODIC
    return bool(getattr(capabilities, name))


def traits(capabilities: MachineCapabilities) -> dict[str, bool]:
    """Return the runtime's declared driving traits."""
    return {name: trait(capabilities, name) for name in _TRAITS}
