"""Stroke plans: a drawing's area is checked before any pixel is allocated."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .render import Canvas, _arrowhead


@dataclass(frozen=True, slots=True)
class CanvasPlan:
    """A checked layout with its area before pixel allocation."""

    draw: Callable[[], Canvas]
    area: int

    def __call__(self) -> Canvas:
        """Rasterize the checked strokes."""
        return self.draw()


def stroke_plan(
    strokes: list[list[tuple[int, int]]],
    start: tuple[int, int],
    heading: tuple[int, int],
    old_area: int,
    unit: int,
) -> CanvasPlan | None:
    """Plan the strokes' bounding canvas, arrowhead at ``start`` facing ``heading``.

    None unless that canvas is smaller than ``old_area``.
    """
    points = [point for stroke in strokes for point in stroke]
    top, bottom = min(y for y, _ in points), max(y for y, _ in points)
    left, right = min(x for _, x in points), max(x for _, x in points)
    width, height = (right - left + 2) * unit, (bottom - top + 2) * unit
    if width * height >= old_area:
        return None

    def rasterize() -> Canvas:
        canvas = Canvas(width, height)
        for stroke in strokes:
            canvas.line(
                [((x - left + 1) * unit, (y - top + 1) * unit) for y, x in stroke]
            )
        y, x = (start[0] - top + 1) * unit, (start[1] - left + 1) * unit
        _arrowhead(canvas, y, x, heading, unit)
        return canvas

    return CanvasPlan(rasterize, width * height)
