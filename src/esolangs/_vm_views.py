"""Discovery and compact rendering of interpreter-specific VM state."""

from __future__ import annotations

_NOT_A_VIEW = frozenset(
    {
        "ip",
        "memory",
        "stack",
        "output",
        "halted",
        "snapshot",
        "branching_snapshot",
        "branching_halted",
        "branching_successors",
        "frame_entry_key",
        "self_halts",
        "steppable_to_answer",
        "dumps_on_the_post_halt_step",
        "eof_is_a_value",
        "ip_shape",
        "reproducible_seed",
    }
)

_VIEW_ITEMS = 8


def _abbreviate(value: object) -> str:
    """Render ``value`` short enough to sit on one row."""
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        return f"{type(value)(value[:_VIEW_ITEMS])!r} +{len(value) - _VIEW_ITEMS} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _read_view(machine: object, name: str) -> str | None:
    """Return one property as short text, or ``None`` if it cannot be read."""
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def machine_views(machine: object) -> tuple[tuple[str, str], ...]:
    """Return the readable public properties unique to ``machine``."""
    found = []
    for name, attribute in sorted(vars(type(machine)).items()):
        if name.startswith("_") or name in _NOT_A_VIEW:
            continue
        if not isinstance(attribute, property):
            continue
        text = _read_view(machine, name)
        if text is not None:
            found.append((name, text))
    return tuple(found)
