"""Compact rendering of declared interpreter-specific VM state."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from esolangs.runtime._execution import _hit_digit_cap
from esolangs.runtime.memory import format_integer

_VIEW_ITEMS = 8
_CONTAINERS = (dict, list, tuple, set, frozenset)
_PRIMITIVES = (int, bool, str, bytes, bytearray, float, complex, type(None))
type _Container = (
    dict[object, object]
    | list[object]
    | tuple[object, ...]
    | set[object]
    | frozenset[object]
)


def _plain_repr(value: object, seen: set[int]) -> bool:
    """Refuse to repeat a custom repr after a surrounding builtin repr failed."""
    if any(type(value) is kind for kind in _PRIMITIVES):
        return True
    if not any(type(value) is kind for kind in _CONTAINERS):
        return False
    if id(value) in seen:
        return True
    seen.add(id(value))
    if isinstance(value, dict):
        return all(
            _plain_repr(k, seen) and _plain_repr(v, seen) for k, v in value.items()
        )
    return all(_plain_repr(item, seen) for item in cast(_Container, value))


def _container_repr(value: _Container, render: Callable[[object], str]) -> str:
    """Render only exact builtin containers; preserve their punctuation and order."""
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(render(k) + ": " + render(v) for k, v in value.items())
            + "}"
        )
    shown = ", ".join(map(render, value))
    if isinstance(value, list):
        return "[" + shown + "]"
    if isinstance(value, tuple):
        return "(" + shown + ("," if len(value) == 1 else "") + ")"
    return (
        "frozenset({" + shown + "})"
        if isinstance(value, frozenset)
        else "{" + shown + "}"
    )


def _view_repr(value: object, active: set[int] | None = None) -> str:
    """Keep ordinary repr; render capped integers in purely builtin value graphs."""
    try:
        return repr(value)
    except ValueError as error:
        if not _hit_digit_cap(error) or (
            active is None and not _plain_repr(value, set())
        ):
            raise
    if type(value) is int:
        return format_integer(value)
    if active is None:
        active = set()
    if id(value) in active:
        markers: dict[type[object], str] = {
            list: "[...]",
            dict: "{...}",
            tuple: "(...)",
        }
        return markers.get(type(value), "...")
    active.add(id(value))
    try:
        return _container_repr(
            cast(_Container, value), lambda item: _view_repr(item, active)
        )
    finally:
        active.remove(id(value))


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
