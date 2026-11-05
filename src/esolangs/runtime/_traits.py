"""Driving trait defaults shared by interpreter wrappers and runners."""

from esolangs.runtime._lifecycle import Completion, completion

_DEFAULTS = {
    "self_halts": True,
    "dumps_on_the_post_halt_step": False,
    "steppable_to_answer": True,
    "eof_is_a_value": False,
}


def trait(machine: object, name: str) -> bool:
    """Read a driving trait from a machine class or instance."""
    if getattr(machine, "completion", None) is not None:
        if name == "dumps_on_the_post_halt_step":
            return completion(machine) is Completion.POST_HALT
        if name == "steppable_to_answer":
            return completion(machine) is not Completion.PERIODIC
    return bool(getattr(machine, name, _DEFAULTS[name]))


def traits(machine: object) -> dict[str, bool]:
    """Return the driving traits with their shared defaults."""
    return {name: trait(machine, name) for name in _DEFAULTS}
