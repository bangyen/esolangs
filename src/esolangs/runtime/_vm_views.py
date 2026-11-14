"""Compact rendering of declared interpreter-specific VM state."""

from __future__ import annotations

from esolangs.runtime.memory import format_integer, repr_value

_VIEW_ITEMS = 8


def _view_repr(value: object) -> str:
    """Keep VM views in decimal across the integer conversion cap."""
    return repr_value(value, format_large_int=format_integer)


def _abbreviate(value: object) -> str:
    """Render ``value`` short enough to sit on one row."""
    if isinstance(value, (list, tuple)) and len(value) > _VIEW_ITEMS:
        prefix = _view_repr(type(value)(value[:_VIEW_ITEMS]))
        return f"{prefix} +{len(value) - _VIEW_ITEMS} more"
    text = _view_repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _read_view(machine: object, name: str) -> str | None:
    """Return one property as short text, or ``None`` if it cannot be read."""
    try:
        value = getattr(machine, name)
    except Exception:
        return None
    return _abbreviate(value)


def machine_views(
    machine: object, names: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """Render only the declared attributes."""
    found = []
    for name in names:
        text = _read_view(machine, name)
        if text is not None:
            found.append((name, text))
    return tuple(found)
