"""Render Line programs to PNG images.

Line (https://esolangs.org/wiki/Line) has no text format: the wiki defines
each instruction as a hand-drawn curve and is tagged "Unimplemented".
This is a renderer, not an interpreter: it lays an opcode sequence out as
a path and rasterizes it like the wiki's examples -- straight runs,
corners, a diagonal kink per instruction, a filled arrowhead cursor.
The kink shapes (``_OPS``) were measured from ``Lineanim4-11.png`` and
fall into two families: ``+``/``-`` are one diagonal jog whose repeats
stretch it (``+++`` is exactly three times in ``Lineanim6.png``); ``>``/``<``/
``i``/``o`` have a purely sideways connector and never merge.  ``?``
(``Lineanim9.png``) is a T-branch with two children.  Generation keeps
unrelated strokes apart, sidestepping the crossing-vs-merge ambiguity
that makes extraction hard.
"""

from __future__ import annotations

import itertools

from esolangs.raster import png

from .layout import (
    _BRANCH_SPACING,
    _STEM_LEN,
    _TREE_GAP,
    Node,
    _Cursor,
    _layout,
    _Plan,
    _turn_left,
)

# One grid unit in pixels; roughly the wiki's own scale per straight run.
_UNIT = 20


class Canvas:
    """An 8-bit greyscale raster with the two drawing primitives Line needs.

    Bresenham and a scanline fill over one ``bytearray`` per row, the shape
    :mod:`png` writes.  What matters is that :mod:`extract` reads it back:
    strokes exactly 1px (:func:`extract.detect_scale`), the arrowhead the
    only region surviving erosion, inside :data:`extract._FILL_RATIO_RANGE`.
    """

    def __init__(self, width: int, height: int, colour: int = 255) -> None:
        """Create a ``width`` x ``height`` canvas filled with ``colour``."""
        self.width = width
        self.height = height
        self.pixels = [bytearray([colour]) * width for _ in range(height)]

    def line(self, points: list[tuple[float, float]], colour: int = 0) -> None:
        """Stroke a 1px-wide polyline through ``points`` given as ``(x, y)``."""
        for (x0, y0), (x1, y1) in itertools.pairwise(points):
            self._segment(round(x0), round(y0), round(x1), round(y1), colour)

    def _segment(self, x0: int, y0: int, x1: int, y1: int, colour: int) -> None:
        """Bresenham's line algorithm, plotting one pixel per step."""
        height, width = self.height, self.width
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            if 0 <= y0 < height and 0 <= x0 < width:
                self.pixels[y0][x0] = colour
            if x0 == x1 and y0 == y1:
                return
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += step_x
            if doubled <= dx:
                error += dx
                y0 += step_y

    def polygon(self, points: list[tuple[float, float]], colour: int = 0) -> None:
        """Fill the polygon through ``points`` given as ``(x, y)``.

        Scanline fill plus a stroked outline, so a thin triangle stays connected.
        """
        height, width = self.height, self.width
        ys = [y for _, y in points]
        for row in range(max(0, int(min(ys))), min(height, int(max(ys)) + 2)):
            centre = row + 0.5
            crossings = []
            for (x0, y0), (x1, y1) in itertools.pairwise([*points, points[0]]):
                if (y0 > centre) != (y1 > centre):
                    crossings.append(x0 + (centre - y0) / (y1 - y0) * (x1 - x0))
            crossings.sort()
            for left, right in zip(crossings[::2], crossings[1::2], strict=False):
                start = max(0, round(left))
                stop = min(width, round(right) + 1)
                if stop > start:
                    self.pixels[row][start:stop] = bytes([colour]) * (stop - start)
        self.line([*points, points[0]], colour)

    def upscale(self, factor: int) -> Canvas:
        """Replicate every pixel into a ``factor`` x ``factor`` block.

        Exactly what :func:`extract.normalize_scale` undoes; redrawing at a
        larger unit would move vertices onto a different lattice.
        """
        if factor < 1:
            raise ValueError(f"scale factor must be at least 1, got {factor}")
        if factor == 1:
            return self
        out = Canvas(self.width * factor, self.height * factor)
        for y, row in enumerate(self.pixels):
            wide = bytearray(len(row) * factor)
            for k in range(factor):
                wide[k::factor] = row
            for k in range(factor):
                out.pixels[y * factor + k] = bytearray(wide)
        return out

    def save(self, path: str) -> None:
        """Write the canvas to ``path`` as an 8-bit greyscale PNG."""
        png.write_grey_file(path, self.pixels)


def _arrowhead(
    draw: Canvas,
    y: float,
    x: float,
    heading: tuple[int, int],
    unit: int = _UNIT,
) -> None:
    """Draw the filled triangular cursor marker at (y, x), pointing ``heading``."""
    hy, hx = heading
    ly, lx = _turn_left(heading)
    size = unit * 0.35
    back = size * 0.6
    tip = (x + hx * size, y + hy * size)
    base_l = (x - hx * back + lx * back, y - hy * back + ly * back)
    base_r = (x - hx * back - lx * back, y - hy * back - ly * back)
    draw.polygon([tip, base_l, base_r], colour=0)


def _rasterize(
    strokes: list[list[tuple[int, int]]], start_heading: tuple[int, int], unit: int
) -> Canvas:
    """Draw ``strokes`` (cell coordinates) and the start arrowhead on a canvas."""
    ys = [p[0] for stroke in strokes for p in stroke]
    xs = [p[1] for stroke in strokes for p in stroke]
    if not ys:
        raise ValueError("program produced an empty path")
    min_y, max_y = min(ys), max(ys)
    min_x, max_x = min(xs), max(xs)

    margin = unit
    width = (max_x - min_x) * unit + margin * 2
    height = (max_y - min_y) * unit + margin * 2

    def to_px(pt: tuple[int, int]) -> tuple[float, float]:
        y, x = pt
        return (x - min_x) * unit + margin, (y - min_y) * unit + margin

    canvas = Canvas(width, height)
    for stroke in strokes:
        canvas.line([to_px(p) for p in stroke])

    start_px, start_py = to_px((0, 0))
    _arrowhead(canvas, start_py, start_px, start_heading, unit)
    return canvas


def render(
    root: Node,
    start_heading: tuple[int, int] = (-1, 0),
    scale: int = 1,
    *,
    acyclic: bool = False,
    compact: bool = True,
    tight: bool = True,
    unit: int = _UNIT,
) -> Canvas:
    """Lay out and rasterize a Line program, returning a :class:`Canvas`.

    ``start_heading`` defaults to "up", as every wiki example; ``compact=False``
    keeps the previous acyclic spacing for balancing's no-growth fallback.
    """
    _check_unit(unit)
    plan = _Plan()
    if acyclic:
        from .tree_layout import tree_extents

        plan.stem = _TREE_GAP if compact else _STEM_LEN
        plan.arm = _TREE_GAP if compact else _BRANCH_SPACING
        plan.tight = compact and tight
        plan.extents = tree_extents(root, compact=compact, tight=tight)
        plan.tree = set(plan.extents)
    occupied: set[tuple[int, int]] = set()
    cursor = _Cursor(0, 0, start_heading, occupied=occupied)
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
    _layout(root, cursor, plan, entries)

    canvas = _rasterize(cursor.strokes, start_heading, unit)
    # scale replicates pixels (extract.normalize_scale divides it out); 1 matches
    # the wiki.  Against JPEG a 1px drawing extracts exactly down to quality 34
    # and is destroyed by 28, 2x holds to 15, 4x to 10: redundancy at write time,
    # not leniency at read time (extract.coverage_gap stays strict).
    return canvas.upscale(scale)


def _check_unit(unit: int) -> None:
    """Require integer half-units and a cursor large enough for extraction."""
    if isinstance(unit, bool) or not isinstance(unit, int) or unit < 8 or unit % 2:
        raise ValueError("Line unit must be an even integer of at least 8 pixels")
