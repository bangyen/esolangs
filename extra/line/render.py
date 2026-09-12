r"""Render Line programs to PNG images."""

from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass, field

import png

# One grid unit in output.
# scale for a single straight.
_UNIT = 20

# Cardinal headings as (dy, dx).
# combine a heading with the.
# they move one step forward.
# true 45-degree kink measured.
# middle run was `(-1, 1)` per.
# separate orthogonal legs.
_FORWARD = (1, 0)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return dx, -dy


def _turn_left(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return -dx, dy


def _diag_right(d: tuple[int, int]) -> tuple[int, int]:
    r"""Forward-and-right diagonal: one step in ``d``, one step turned."""
    dy, dx = d
    ry, rx = _turn_right(d)
    return dy + ry, dx + rx


def _diag_left(d: tuple[int, int]) -> tuple[int, int]:
    r"""Forward-and-left diagonal: one step in ``d``, one step turned left."""
    dy, dx = d
    ly, lx = _turn_left(d)
    return dy + ly, dx + lx


def _horiz_right(d: tuple[int, int]) -> tuple[int, int]:
    r"""Pure sideways step, turned right relative to ``d`` (no forward."""
    return _turn_right(d)


def _horiz_left(d: tuple[int, int]) -> tuple[int, int]:
    r"""Pure sideways step, turned left relative to ``d`` (no forward."""
    return _turn_left(d)


def _rotate(d: tuple[int, int], heading: tuple[int, int]) -> tuple[int, int]:
    r"""Rotate a direction defined relative to "forward" onto ``heading``."""
    dy, dx = d
    hy, hx = heading
    # Forward (1, 0) maps to.
    ly, lx = _turn_left(heading)
    return hy * dy + ly * dx, hx * dy + lx * dx


# Each opcode is a sequence of.
# relative to the cursor's.
# breakdown measured.
# _UNIT-sized steps.
# every one of.
# template:.
# .
# * `+`/`-` (Lineanim4.png,.
# sideways connector --.
# diagonal leg's *length in.
# 1: Lineanim6.png shows three.
# 3 units long, not three.
# measuring its diagonal run at.
# and `_OPS["-"]` below are.
# built by :func:`_op_segments`.
# others -- see.
# `count` from consecutive.
# * `>`/`<`/`i`/`o`.
# sideways* connector (no.
# `_horiz_left`) bridging their.
# distinguishes them from the.
# diagonal leg than `>`/`<`.
# than Lineanim7.png's by.
# rows).
# wiki example showing it, and.
# kink even back-to-back with.
_OPS: dict[str, list[tuple[tuple[int, int], int]]] = {
    ">": [
        (_FORWARD, 2),
        (_diag_right(_FORWARD), 1),
        (_horiz_left(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "<": [
        (_FORWARD, 2),
        (_diag_left(_FORWARD), 1),
        (_horiz_right(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "i": [
        (_FORWARD, 2),
        (_diag_right(_FORWARD), 1),
        (_horiz_left(_FORWARD), 2),
        (_diag_right(_FORWARD), 1),
        (_FORWARD, 2),
    ],
    "o": [
        (_FORWARD, 2),
        (_horiz_left(_FORWARD), 1),
        (_diag_right(_FORWARD), 2),
        (_horiz_left(_FORWARD), 1),
        (_FORWARD, 2),
    ],
}


def _op_segments(op: str, count: int) -> list[tuple[tuple[int, int], int]]:
    r"""Look up one opcode's kink template, expanding `+`/`-`'s run by."""
    if op == "+":
        return [(_FORWARD, 2), (_diag_right(_FORWARD), count), (_FORWARD, 2)]
    if op == "-":
        return [(_FORWARD, 2), (_diag_left(_FORWARD), count), (_FORWARD, 2)]
    return _OPS[op]


@dataclass
class _Cursor:
    y: int
    x: int
    heading: tuple[int, int]
    strokes: list[list[tuple[int, int]]] = field(default_factory=list)
    _current: list[tuple[int, int]] = field(default_factory=list)
    # Every pixel any stroke has.
    # being laid out -- shared by.
    # cursor `branch()` creates.
    # check a constructed loop-back.
    # trunk, not just its own.
    # occupancy tracking is off --.
    # measuring dry runs, whose.
    # guard.
    occupied: set[tuple[int, int]] | None = None

    def __post_init__(self) -> None:
        self._current = [(self.y, self.x)]

    def advance(self, direction: tuple[int, int], steps: int = 1) -> None:
        for _ in range(steps):
            self.y += direction[0]
            self.x += direction[1]
            self._current.append((self.y, self.x))
        self.heading = direction

    def emit_op(self, op: str, count: int = 1) -> None:
        r"""Emit one opcode's kink, all legs rotated onto the heading at entry."""
        entry_heading = self.heading
        for rel_dir, run in _op_segments(op, count):
            self.advance(_rotate(rel_dir, entry_heading), run)
        self.heading = entry_heading

    def branch(self) -> tuple[_Cursor, _Cursor]:
        r"""Split into two cursors (taken / not-taken) at the current point."""
        self.finish()
        right = _Cursor(
            self.y, self.x, _turn_right(self.heading), occupied=self.occupied
        )
        left = _Cursor(self.y, self.x, _turn_left(self.heading), occupied=self.occupied)
        return right, left

    def finish(self) -> None:
        if len(self._current) > 1:
            self.strokes.append(self._current)
            if self.occupied is not None:
                self.occupied.update(self._current)
        self._current = [(self.y, self.x)]


@dataclass
class Node:
    r"""One step of a Line program: an opcode, or a conditional branch."""

    op: str
    next: Node | None = None
    zero: Node | None = None
    nonzero: Node | None = None
    goto: Node | None = None


def chain(*ops: str) -> Node:
    r"""Build a straight-through Node chain from an opcode string, e.g."""
    head: Node | None = None
    tail: Node | None = None
    for op in ops:
        node = Node(op)
        if head is None:
            head = node
        else:
            assert tail is not None
            tail.next = node
        tail = node
    if head is None:
        raise ValueError("chain() requires at least one opcode")
    return head


# The only opcodes whose.
# stretched kink rather than.
# `_OPS` comment in this module.
# there is no wiki example.
_MERGEABLE = {"+", "-"}

# How many *grid cells* of.
# itself and any unrelated.
# One cell here is `_UNIT`.
# works entirely in cursor-grid.
# when rasterizing.
# .
# Non-overlap alone is not.
# rasterize into one.
# pixel to each side of its.
# and an ordinary point becomes.
# puts those off-centre rays.
# `test_bf_to_line.py`'s.
# abutting cells); at 1 none.
# do not catch the difference.
_CLEARANCE = 1


def _leg_cells(
    start: tuple[int, int], legs: list[tuple[tuple[int, int], int]]
) -> list[tuple[int, int]]:
    r"""Every grid cell a run of ``legs`` walks through, starting from."""
    cells = [start]
    y, x = start
    for (dy, dx), length in legs:
        for _ in range(length):
            y, x = y + dy, x + dx
            cells.append((y, x))
    return cells


# Length (in grid units) of the.
# branch point.
# `_RETURN_STEM_T` from the.
# the landing diagonal fits.
_STEM_LEN = 10


# Length of a loop-back's final.
# 6 here is 120 raster pixels,.
# 15px probe).
# .
# The diagonal arrival is.
# return path is cardinal, and.
# run, so a cardinal final.
# stem -- and a perpendicular.
# arrival direction plus the.
# signature `lattice._classify`.
# then read the loop-back merge.
# execute the reconnection as a.
# diagonally lights that same.
# to it, which `_classify`.
# what `simulate._compile`'s.
# matches how the wiki's own.
# loop-body arm arrives at its.
# .
# Being *longer* than the probe.
# probe must find a full,.
# merge point lights that third.
# `"merge"`.
# reading only the stem's own.
# bend, which the walker sails.
# stopping the stroke as a leaf.
_DIAGONAL_APPROACH = 6


# Minimum gap (grid units) a.
# the safety margin added on.
# .
# This used to be the whole.
# is blind to how much ink a.
# measures each subtree's real.
# ``docs/line_tooling.md``.
# count failed.
# .
# What remains here is a floor,.
# back barely at all still.
# trunk.
# every program in all three.
# at 20/8/5/3/2/1, and with.
# no longer the constant that.
_BRANCH_SPACING = 5


# Width, in grid cells, of the.
# an arm -- see.
# `goto`-carrying arm, and.
# :func:`_loop_return_legs` a.
# _GOTO_CORRIDOR`` = 8 cells.
# .
# Not a chosen number: a fixed.
# depth-3 work and removed.
# measured.
# own stroke, plus `_CLEARANCE`.
# the expression rather than.
# the corridors with it.
_GOTO_CORRIDOR = 1 + 2 * _CLEARANCE


# Memoized `_subtree_extent`.
# .
# Measuring is a full dry-run.
# that themselves contain.
# exponential in nesting depth:.
# program (no output after two.
# .
# Cleared at the start of every.
# global, because `id()` is.
# between two renders can have.
# next one, which a persistent.
_EXTENT_CACHE: dict[int, tuple[int, int, int, int]] = {}


def _has_goto(node: Node | None, seen: set[int] | None = None) -> bool:
    r"""Whether ``node``'s subtree contains a loop-back needing a bay."""
    if seen is None:
        seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if node.goto is not None:
            return True
        if node.op == "?":
            return _has_goto(node.zero, seen) or _has_goto(node.nonzero, seen)
        node = node.next
    return False


def _subtree_extent(node: Node | None) -> tuple[int, int, int, int]:
    r"""Measure the bounding box ``node``'s subtree actually draws."""
    if node is None:
        return (0, 0, 0, 0)
    cached = _EXTENT_CACHE.get(id(node))
    if cached is not None:
        return cached
    scratch = _Cursor(0, 0, _FORWARD)
    _layout(node, scratch, measuring=True)
    points = [p for stroke in scratch.strokes for p in stroke] or [(0, 0)]
    ys = [p[0] for p in points]
    xs = [p[1] for p in points]
    extent = (min(ys), max(ys), min(xs), max(xs))
    _EXTENT_CACHE[id(node)] = extent
    return extent


def _arm_spacing(arm: Node | None) -> int:
    r"""How far a fork arm runs before laying out ``arm``'s own content."""
    if arm is None:
        return _BRANCH_SPACING
    # Measured in the arm's own.
    # travels, so anything at.
    # *behind* the subtree's entry.
    # in the canonical frame avoids.
    min_forward, _, _, _ = _subtree_extent(arm)
    corridors = _GOTO_CORRIDOR if _has_goto(arm) else 0
    return _BRANCH_SPACING + max(-min_forward, 0) + corridors


# Offset, in grid cells, at.
# its body's bounding box.
# `_CLEARANCE` = 1 against ink.
# between is empty).
_RING_OFFSET = _CLEARANCE + 1

# The fixed stem offset a.
# vertex (so `_STEM_LEN -.
# interior offset works -- the.
# geometry, so unlike the.
# choice in -- and the midpoint.
_RETURN_STEM_T = _STEM_LEN // 2


def _loop_return_legs(
    start: tuple[int, int],
    target: Node,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], int]] | None:
    r"""Construct a loop-back's legs deterministically, without search."""
    stem_start, h = entries[id(target)]
    a_h = _turn_left(h)
    arm_run = _arm_spacing(target.nonzero)
    vertex = (
        stem_start[0] + h[0] * _STEM_LEN,
        stem_start[1] + h[1] * _STEM_LEN,
    )
    entry_pt = (vertex[0] + a_h[0] * arm_run, vertex[1] + a_h[1] * arm_run)
    y0, y1, x0, x1 = _subtree_extent(target.nonzero)

    # `start` in the canonical.
    # frame's axes (+y = a_h, +x =.
    # orthonormal, so projection.
    ly, lx = _turn_left(a_h)
    off = (start[0] - entry_pt[0], start[1] - entry_pt[1])
    ey = off[0] * a_h[0] + off[1] * a_h[1]
    ex = off[0] * ly + off[1] * lx
    on_y = ey in (y0, y1) and x0 <= ex <= x1
    on_x = ex in (x0, x1) and y0 <= ey <= y1
    if not (on_y or on_x):
        return None

    axis_y = -arm_run
    bay_y = y0 - _RING_OFFSET
    far_y = y1 + _RING_OFFSET
    lo_x = x0 - _RING_OFFSET
    hi_x = x1 + _RING_OFFSET
    # The bay must clear both the.
    # span; `_arm_spacing`'s floor.
    # goto-carrying arm, so a.
    # arm the corridor term never.
    if bay_y < axis_y + _DIAGONAL_APPROACH:
        return None

    tgt_x = _STEM_LEN - _RETURN_STEM_T
    approach = (axis_y + _DIAGONAL_APPROACH, tgt_x + _DIAGONAL_APPROACH)

    # Waypoints around the ring,.
    # rear corner `(bay_y, hi_x)`.
    # arm stroke at x = 0 (every.
    pts: list[tuple[int, int]] = [(ey, ex)]
    if on_x and ex == x1:  # rear side: out, then down to.
        pts += [(ey, hi_x), (bay_y, hi_x)]
    elif on_y and ey == y1:  # far side: out, over the.
        pts += [(far_y, ex), (far_y, hi_x), (bay_y, hi_x)]
    elif on_x and ex == x0:  # vertex-ward side: the long.
        pts += [(ey, lo_x), (far_y, lo_x), (far_y, hi_x), (bay_y, hi_x)]
    else:  # bay side.
        if ex == 0:
            # The escape would land exactly.
            return None
        if ex >= 1:
            pts += [(bay_y, ex)]
        else:
            # Left of the arm stroke: the.
            # take the long way around the.
            pts += [(bay_y, ex), (bay_y, lo_x), (far_y, lo_x), (far_y, hi_x)]
            pts += [(bay_y, hi_x)]
    pts += [(bay_y, approach[1]), approach]

    legs: list[tuple[tuple[int, int], int]] = []
    for a, b in itertools.pairwise(pts):
        dy, dx = b[0] - a[0], b[1] - a[1]
        if dy and dx:  # pragma: no cover - geometry guard
            return None
        if not dy and not dx:
            continue
        direction = (
            0 if dy == 0 else (1 if dy > 0 else -1),
            0 if dx == 0 else (1 if dx > 0 else -1),
        )
        legs.append((direction, abs(dy) + abs(dx)))
    legs.append(((-1, -1), _DIAGONAL_APPROACH))

    return [(_rotate(d, a_h), n) for d, n in legs]


def _layout(
    node: Node | None,
    cursor: _Cursor,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    depth: int = 0,
    *,
    measuring: bool = False,
) -> None:
    r"""Lay out ``node``'s chain from ``cursor``'s current point."""
    if entries is None:
        entries = {}
    while node is not None:
        if node.op == "?":
            stem_start = (cursor.y, cursor.x)
            cursor.advance(cursor.heading, _STEM_LEN)
            entries[id(node)] = (stem_start, cursor.heading)
            right, left = cursor.branch()
            right.advance(right.heading, _arm_spacing(node.zero))
            right.finish()
            left.advance(left.heading, _arm_spacing(node.nonzero))
            left.finish()
            _layout(node.zero, right, entries, depth + 1, measuring=measuring)
            _layout(node.nonzero, left, entries, depth + 1, measuring=measuring)
            right.finish()
            left.finish()
            cursor.strokes.extend(right.strokes)
            cursor.strokes.extend(left.strokes)
            return
        op, count = node.op, 1
        if op in _MERGEABLE:
            while (
                node.next is not None and node.next.op == op and node.next.goto is None
            ):
                node = node.next
                count += 1
        cursor.emit_op(op, count)
        if node.goto is not None:
            # Flush the in-progress.
            # going any further, so.
            # treats the body just drawn.
            # kink) as real ink.
            cursor.finish()
            # The constructed return path.
            # Drawn *here*, in both real.
            # nesting unbounded: a dry run.
            # reports extents that contain.
            # room for them exactly as it.
            # already be in `entries`.
            # graph, where a goto ends its.
            # measured in isolation lacks.
            # precisely the ink the.
            legs = None
            if id(node.goto) in entries:
                legs = _loop_return_legs((cursor.y, cursor.x), node.goto, entries)
            if legs is not None and cursor.occupied is not None:
                # Drift guard, real mode only:.
                # consults ink, so a violated.
                # outside the compiled.
                # than drawn through existing.
                # first cell is the body's own.
                # merge, both legitimately ink.
                cells = _leg_cells((cursor.y, cursor.x), legs)
                if any(c in cursor.occupied for c in cells[1:-1]):
                    legs = None
            if legs is not None:
                for direction, length in legs:
                    cursor.advance(direction, length)
                cursor.finish()
                return
            if measuring:
                # No constructed return (the.
                # measured subtree): stop here,.
                # semantics of extents require.
                return
            # A goto whose return path.
            # a hand-built graph outside.
            # an ancestor fork whose body.
            # off its own box perimeter).
            # invariant that survives from.
            # never draw a reconnection.
            # extractor misread it.
            raise ValueError(
                "loop-back could not be constructed for this goto -- its "
                "target must be an ancestor '?' fork whose body chain the "
                "goto ends (the shape bf_to_line compiles); see "
                "_loop_return_legs for the geometric premises"
            )
        node = node.next
    cursor.finish()


class Canvas:
    r"""An 8-bit greyscale raster with the two drawing primitives Line."""

    def __init__(self, width: int, height: int, colour: int = 255) -> None:
        r"""Create a ``width`` x ``height`` canvas filled with ``colour``."""
        self.width = width
        self.height = height
        self.pixels = [bytearray([colour]) * width for _ in range(height)]

    def line(self, points: list[tuple[float, float]], colour: int = 0) -> None:
        r"""Stroke a 1px-wide polyline through ``points`` given as ``(x, y)``."""
        for (x0, y0), (x1, y1) in itertools.pairwise(points):
            self._segment(round(x0), round(y0), round(x1), round(y1), colour)

    def _segment(self, x0: int, y0: int, x1: int, y1: int, colour: int) -> None:
        r"""Bresenham's line algorithm, plotting one pixel per step."""
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
        r"""Fill the polygon through ``points`` given as ``(x, y)``."""
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
        r"""Replicate every pixel into a ``factor`` x ``factor`` block."""
        if factor < 1:
            raise ValueError(f"scale factor must be at least 1, got {factor}")
        if factor == 1:
            return self
        out = Canvas(self.width * factor, self.height * factor)
        for y, row in enumerate(self.pixels):
            wide = bytearray()
            for level in row:
                wide += bytes([level]) * factor
            for k in range(factor):
                out.pixels[y * factor + k] = bytearray(wide)
        return out

    def save(self, path: str) -> None:
        r"""Write the canvas to ``path`` as an 8-bit greyscale PNG."""
        png.write_grey_file(path, self.pixels)


def _arrowhead(draw: Canvas, y: float, x: float, heading: tuple[int, int]) -> None:
    r"""Draw the filled triangular cursor marker at (y, x), pointing."""
    hy, hx = heading
    ly, lx = _turn_left(heading)
    size = _UNIT * 0.35
    back = size * 0.6
    tip = (x + hx * size, y + hy * size)
    base_l = (x - hx * back + lx * back, y - hy * back + ly * back)
    base_r = (x - hx * back - lx * back, y - hy * back - ly * back)
    draw.polygon([tip, base_l, base_r], colour=0)


def render(
    root: Node, start_heading: tuple[int, int] = (-1, 0), scale: int = 1
) -> Canvas:
    r"""Lay out and rasterize a Line program, returning a :class:`Canvas`."""
    # See `_EXTENT_CACHE`: keyed by.
    # it describes.
    # from `root` for as long as.
    _EXTENT_CACHE.clear()
    occupied: set[tuple[int, int]] = set()
    cursor = _Cursor(0, 0, start_heading, occupied=occupied)
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
    _layout(root, cursor, entries)

    ys = [p[0] for stroke in cursor.strokes for p in stroke]
    xs = [p[1] for stroke in cursor.strokes for p in stroke]
    if not ys:
        raise ValueError("program produced an empty path")
    min_y, max_y = min(ys), max(ys)
    min_x, max_x = min(xs), max(xs)

    margin = _UNIT
    width = (max_x - min_x) * _UNIT + margin * 2
    height = (max_y - min_y) * _UNIT + margin * 2

    def to_px(pt: tuple[int, int]) -> tuple[float, float]:
        y, x = pt
        return (x - min_x) * _UNIT + margin, (y - min_y) * _UNIT + margin

    canvas = Canvas(width, height)
    for stroke in cursor.strokes:
        canvas.line([to_px(p) for p in stroke])

    start_px, start_py = to_px((0, 0))
    _arrowhead(canvas, start_py, start_px, start_heading)
    return canvas.upscale(scale)


if __name__ == "__main__":
    program = chain(*sys.argv[1]) if len(sys.argv) > 1 else chain("+", "+", "+")
    render(program).save(sys.argv[2] if len(sys.argv) > 2 else "line_out.png")
