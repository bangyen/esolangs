"""Compact rendering of declared interpreter-specific VM state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from esolangs.exceptions import InterpreterLimitError
from esolangs.runtime._validate import _MAX_CELLS
from esolangs.runtime.memory import format_integer, repr_value

if TYPE_CHECKING:
    from collections.abc import Mapping

_VIEW_ITEMS = 8


def sparse_memory(cells: Mapping[int, int], *, start: int = 0) -> list[int]:
    """Materialize the mapped cells from ``start`` through the highest address or 0."""
    if not cells:
        return []
    highest = max(cells)
    size = max(0, highest) - start + 1
    if size > _MAX_CELLS:
        raise InterpreterLimitError(
            f"memory exceeds the {_MAX_CELLS}-cell dense view limit",
            hint="inspect individual cells with debugger watches or breakpoints",
        )
    result = [0] * size
    for address, value in cells.items():
        result[address - start] = value
    return result


def sparse_cell(cells: Mapping[int, int], index: int, *, start: int = 0) -> int | None:
    """Read the same index as ``sparse_memory`` without allocating the span."""
    if index < 0:
        return None
    address = start + index
    if (value := cells.get(address)) is not None:
        return value
    if cells and (address <= 0 or any(key >= address for key in cells)):
        return 0
    return None


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
