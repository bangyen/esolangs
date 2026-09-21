"""Render Line programs to PNG images.

Line (https://esolangs.org/wiki/Line) has no text format: the wiki defines
each instruction as a hand-drawn curve and is tagged "Unimplemented".
This is a renderer, not an interpreter: it lays an opcode sequence out as
a path and rasterizes it like the wiki's examples -- straight runs,
corners, a diagonal kink per instruction, a filled arrowhead cursor.
The kink shapes (``_OPS``) were measured from ``Lineanim4-11.png`` and
fall into two families: ``+``/``-`` are one diagonal jog whose repeats
stretch it (``+++`` is exactly 3x in ``Lineanim6.png``); ``>``/``<``/
``i``/``o`` have a purely sideways connector and never merge.  ``?``
(``Lineanim9.png``) is a T-branch with two children.  Generation keeps
unrelated strokes apart, sidestepping the crossing-vs-merge ambiguity
that makes extraction hard.
"""

from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass, field

from esolangs.raster import png

# One grid unit in pixels; roughly the wiki's own scale per straight run.
_UNIT = 20

# Headings as (dy, dx).  A diagonal jog is one step forward *and* one
# sideways at once -- the true 45-degree kink measured from the wiki (the
# `+` opcode's middle run was `(-1, 1)` per step), not two orthogonal legs.
_FORWARD = (1, 0)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return dx, -dy


def _turn_left(d: tuple[int, int]) -> tuple[int, int]:
    dy, dx = d
    return -dx, dy


def _diag_right(d: tuple[int, int]) -> tuple[int, int]:
    """Forward-and-right diagonal: one step in ``d``, one step turned right."""
    dy, dx = d
    ry, rx = _turn_right(d)
    return dy + ry, dx + rx


def _diag_left(d: tuple[int, int]) -> tuple[int, int]:
    """Forward-and-left diagonal: one step in ``d``, one step turned left."""
    dy, dx = d
    ly, lx = _turn_left(d)
    return dy + ly, dx + lx


def _horiz_right(d: tuple[int, int]) -> tuple[int, int]:
    """Pure sideways step, turned right relative to ``d`` (no forward motion).

    The connector that distinguishes ``>``/``<``/``i``/``o`` from ``+``/``-``.
    """
    return _turn_right(d)


def _horiz_left(d: tuple[int, int]) -> tuple[int, int]:
    """Pure sideways step, turned left relative to ``d`` (no forward motion)."""
    return _turn_left(d)


def _rotate(d: tuple[int, int], heading: tuple[int, int]) -> tuple[int, int]:
    """Rotate a direction defined relative to "forward" onto ``heading``."""
    dy, dx = d
    hy, hx = heading
    # Forward (1, 0) maps to heading; right/left rotate along with it.
    ly, lx = _turn_left(heading)
    return hy * dy + ly * dx, hx * dy + lx * dx


# Each opcode as (relative_direction, run_length) segments relative to the
# cursor heading, measured pixel-by-pixel from Lineanim4/5/6/7/8/10/11.png
# at _UNIT steps.  Two kink families:
# * `+`/`-` (Lineanim4/5): `vertical(2) -> diagonal(1) -> vertical(2)`, no
#   sideways connector.  The diagonal's length is the run's opcode count:
#   Lineanim6 draws three `+` as one 3-unit diagonal (measured at exactly
#   3x), so these are templates over `count`, built by :func:`_op_segments`
#   and fed by :func:`_Cursor.emit_op`.
# * `>`/`<`/`i`/`o` (Lineanim7/8/10/11): a pure sideways connector
#   (`_horiz_right`/`_horiz_left`) bridging the diagonal legs; `i`/`o` have
#   one more diagonal leg (Lineanim10 is one unit-diagonal taller than
#   Lineanim7).  Repeats never merge: no wiki example shows it.
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
    """Look up one opcode's kink template, expanding `+`/`-`'s run by `count`."""
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
    # Every pixel drawn so far, shared by reference with every `branch()`
    # child so `_layout`'s drift guard sees sibling and trunk ink.  `None`
    # turns tracking off, for `_subtree_extent`'s dry runs.
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
        """Emit one opcode's kink, all legs rotated onto the heading at entry.

        The heading is frozen at the opcode's start: a diagonal jog is not a
        cardinal heading, and the wiki shows the same orientation before and
        after.  ``count`` merges consecutive ``+``/``-`` (:func:`_layout` counts them).
        """
        entry_heading = self.heading
        for rel_dir, run in _op_segments(op, count):
            self.advance(_rotate(rel_dir, entry_heading), run)
        self.heading = entry_heading

    def branch(self) -> tuple[_Cursor, _Cursor]:
        """Split into two cursors (taken / not-taken) at the current point.

        The T-branch of ``Lineanim9.png``: right when the cell is zero, left otherwise.
        """
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
    """One step of a Line program: an opcode, or a conditional branch.

    ``op`` is one of ``+ - < > i o``, or ``?`` with ``zero``/``nonzero``
    children.  ``goto`` (with ``next`` ``None``) is a drawn loop-back: the
    layout draws a return path to a point strictly inside the stem of the
    target ``?`` -- the fork's own vertex, approached with its arrival
    heading, would retrace the stem (:func:`_loop_return_legs`).  This is
    the shape :mod:`simulate`'s ``find_merge`` handles (``addition.png``
    reconnects mid-stem) and how a brainfuck ``[...]`` translates: a ``?``
    whose ``nonzero`` arm ends in a ``goto`` back to it.
    """

    op: str
    next: Node | None = None
    zero: Node | None = None
    nonzero: Node | None = None
    goto: Node | None = None


def chain(*ops: str) -> Node:
    """Build a straight-through Node chain from an opcode string, e.g. "+++"."""
    head: Node | None = None
    tail: Node | None = None
    for op in ops:
        node = Node(op)
        if head is None:
            head = node
        else:
            if tail is None:
                raise AssertionError("non-empty node chain lost its tail")
            tail.next = node
        tail = node
    if head is None:
        raise ValueError("chain() requires at least one opcode")
    return head


# The only opcodes whose repeats merge into one kink (Lineanim6.png; see `_OPS`).
_MERGEABLE = {"+", "-"}

# Grid cells (`_UNIT` pixels each) a loop-back keeps from unrelated ink.
# Abutting strokes rasterize into one ribbon and `lattice._band_lit`'s
# off-centre rays read the neighbour as a spurious 3-lit `"fork"`.  At 0,
# every `TestStrokeSeparation` program develops adjacency (up to 76 cells);
# at 1 none does, and the output-asserting suites do not catch it.
_CLEARANCE = 1


def _leg_cells(
    start: tuple[int, int], legs: list[tuple[tuple[int, int], int]]
) -> list[tuple[int, int]]:
    """Every grid cell a run of ``legs`` walks through, starting from ``start``."""
    cells = [start]
    y, x = start
    for (dy, dx), length in legs:
        for _ in range(length):
            y, x = y + dy, x + dx
            cells.append((y, x))
    return cells


# Stem `_layout` walks into a `?` node's branch point; a loop-back lands
# inside it at `_RETURN_STEM_T`, so the landing diagonal must fit.
_STEM_LEN = 10


# Loop-back's final diagonal leg, in cells (6 = 120px, longer than
# `lattice.star`'s 15px probe).  Must be diagonal: a cardinal approach is
# perpendicular to the stem and lights the T signature `_classify` calls
# `"fork"`, so the extractor reads a branch instead of a jump; a diagonal
# lights a non-perpendicular third direction, `"merge"`, which `find_merge`
# rescues into a `goto` (`addition.png` reconnects the same way).  Must be
# longer than the probe: too short and the merge point reads `"straight"`.
_DIAGONAL_APPROACH = 6


# Floor on a fork arm's run before content, on top of what
# :func:`_arm_spacing` measures from real subtree extent (arms used to be
# sized by fork count, blind to ink).  Lowered 20 -> 5 after a sweep at
# 20/8/5/3/2/1 all extracted and executed correctly.
_BRANCH_SPACING = 5


# Corridor a loop-back needs to pass an arm: one stroke cell plus
# `_CLEARANCE` each side.  :func:`_arm_spacing` reserves one per
# goto-carrying arm, guaranteeing :func:`_loop_return_legs` a bay of
# ``_BRANCH_SPACING + _GOTO_CORRIDOR`` = 8.  A fixed `_GOTO_CHANNEL` was
# tried and removed as an unmeasured guess.
_GOTO_CORRIDOR = 1 + 2 * _CLEARANCE


# `_subtree_extent` memo per `render()`, keyed by node id.  Measuring is a
# dry-run `_layout`, exponential in nesting depth unmemoized (a depth-3
# program stalled past two minutes vs under a second).  Cleared per render
# because `id()` is reused once a `Node` is freed.
_EXTENT_CACHE: dict[int, tuple[int, int, int, int]] = {}


def _has_goto(node: Node | None, seen: set[int] | None = None) -> bool:
    """Whether ``node``'s subtree contains a loop-back needing a bay corridor.

    Stops at a ``goto`` rather than following it.  A boolean: one corridor
    per goto-carrying arm, not per goto (:func:`_arm_spacing`).
    """
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
    """Measure the bounding box ``node``'s subtree actually draws.

    ``(min_forward, max_forward, min_lateral, max_lateral)`` in grid units
    from the entry point, heading "forward".  Fork-count spacing was blind
    to ink: ``+[>+[>+[>+<-]<-]<-]>>>.`` and ``++[>++[>++[>+<-]<-]<-]>>>.``
    got identical 40/20/10 spacing, and a fork's arms were sized alike at 4
    ops vs 14.  Runs the real :func:`_layout` on a scratch cursor so it
    cannot drift, drawing every nested loop-back (their forks are inside the
    chain); only the chain's outermost ``goto`` is terminal.
    """
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
    """How far a fork arm runs before laying out ``arm``'s own content.

    Far enough that the subtree's measured reach back toward the trunk
    clears it, plus :data:`_BRANCH_SPACING` as floor and margin.  No sibling
    term: ``reach_back`` already puts each box on its own side, and a lateral
    term amplified with depth (7760x3800 vs ~1600 at depth 3).  A
    goto-carrying arm adds one :data:`_GOTO_CORRIDOR`, which guarantees
    :func:`_loop_return_legs` a bay of ``_BRANCH_SPACING + _GOTO_CORRIDOR``
    = 8 -- exactly the lane at :data:`_DIAGONAL_APPROACH` plus
    ``_CLEARANCE`` both sides.  One per arm, not per goto: nested returns ride
    their own fork's bay (dropping the multiplier shrank areas 17% at depth
    4 to 44% at depth 10).  A goto-free program renders pixel-identically.
    """
    if arm is None:
        return _BRANCH_SPACING
    # In the arm's frame, negative forward-extent is content behind the
    # entry point, toward the trunk.
    min_forward, _, _, _ = _subtree_extent(arm)
    corridors = _GOTO_CORRIDOR if _has_goto(arm) else 0
    return _BRANCH_SPACING + max(-min_forward, 0) + corridors


# Ring offset outside the body's bounding box: the smallest satisfying
# `_CLEARANCE` against ink on the box edge.
_RING_OFFSET = _CLEARANCE + 1

# Where a loop-back lands on the stem, from the fork vertex.  Any interior
# offset works (the landing geometry is reserved); the midpoint keeps the
# diagonal clear of both stem ends.
_RETURN_STEM_T = _STEM_LEN // 2


def _loop_return_legs(
    start: tuple[int, int],
    target: Node,
    entries: dict[int, tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], int]] | None:
    """Construct a loop-back's legs deterministically, without search.

    What makes nesting unbounded: search-based routing was a new congestion
    problem at every depth, and since the dry runs draw returns too, every
    parent's extent already contains its children's rings.  In the target
    fork's frame (``+y`` the body arm's heading): ``B0`` is the body's
    memoized extent; from the body's end on ``B0``'s perimeter step
    :data:`_RING_OFFSET` out, walk the ring to the corner nearest the stem
    (never crossing the arm stroke at ``x = 0``), ride the bay, and close
    with a :data:`_DIAGONAL_APPROACH` diagonal (a ``"merge"`` to the
    extractor, not a fork).  ``None`` when a premise fails, which only a
    hand-built graph produces; :func:`_layout` rejects it loudly.
    """
    stem_start, h = entries[id(target)]
    a_h = _turn_left(h)
    arm_run = _arm_spacing(target.nonzero)
    vertex = (
        stem_start[0] + h[0] * _STEM_LEN,
        stem_start[1] + h[1] * _STEM_LEN,
    )
    entry_pt = (vertex[0] + a_h[0] * arm_run, vertex[1] + a_h[1] * arm_run)
    y0, y1, x0, x1 = _subtree_extent(target.nonzero)

    # `start` in the canonical frame (+y = a_h, +x = turn_left(a_h));
    # projection inverts `_rotate` exactly.
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
    # Guaranteed by `_arm_spacing`'s floor + corridor; a failure here is a
    # hand-built graph.
    if bay_y < axis_y + _DIAGONAL_APPROACH:
        return None

    tgt_x = _STEM_LEN - _RETURN_STEM_T
    approach = (axis_y + _DIAGONAL_APPROACH, tgt_x + _DIAGONAL_APPROACH)

    # Enter the bay via the rear corner `(bay_y, hi_x)` so no bay segment
    # crosses the arm stroke at x = 0.
    pts: list[tuple[int, int]] = [(ey, ex)]
    if on_x and ex == x1:  # rear side: out, then down to the bay corner
        pts += [(ey, hi_x), (bay_y, hi_x)]
    elif on_y and ey == y1:  # far side: out, over the far-rear corner, down
        pts += [(far_y, ex), (far_y, hi_x), (bay_y, hi_x)]
    elif on_x and ex == x0:  # vertex-ward side: the long way around
        pts += [(ey, lo_x), (far_y, lo_x), (far_y, hi_x), (bay_y, hi_x)]
    else:  # bay side
        if ex == 0:
            # Would land on the arm stroke's own line.
            return None
        if ex >= 1:
            pts += [(bay_y, ex)]
        else:
            # Left of the arm stroke: go around the ring.
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
    """Lay out ``node``'s chain from ``cursor``'s current point.

    ``entries`` maps a ``?``'s ``id`` to its stem's ``(stem_start, heading)``;
    a ``goto`` reconnects inside that stem at :data:`_RETURN_STEM_T`.
    ``depth`` is informational.  ``measuring`` runs the layout for
    :func:`_subtree_extent`: nested ``goto`` returns are drawn in both modes,
    and only a ``goto`` whose fork is outside the chain is terminal.
    """
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
            # Flush this stroke into `occupied` so the loop-back sees it.
            cursor.finish()
            # Return path (:func:`_loop_return_legs`), drawn in measuring
            # mode too so extents contain it and ancestors reserve room --
            # this is what makes nesting unbounded.  The target is in
            # `entries` for any compiled graph; a subtree measured alone
            # lacks its outermost fork, which the caller's frame draws.
            legs = None
            if id(node.goto) in entries:
                legs = _loop_return_legs((cursor.y, cursor.x), node.goto, entries)
            if legs is not None and cursor.occupied is not None:
                # Drift guard, real mode only: the construction never reads
                # ink, so a hand-built graph must be caught, not drawn
                # through.  Endpoints (body tip, stem merge) are legitimate ink.
                cells = _leg_cells((cursor.y, cursor.x), legs)
                if any(c in cursor.occupied for c in cells[1:-1]):
                    legs = None
            if legs is not None:
                for direction, length in legs:
                    cursor.advance(direction, length)
                cursor.finish()
                return
            if measuring:
                # Target outside this measured subtree: the owner draws it.
                return
            # Only a hand-built graph (target not an ancestor fork, or body
            # end off its box) gets here.  Never draw a reconnection through ink.
            raise ValueError(
                "loop-back could not be constructed for this goto -- its "
                "target must be an ancestor '?' fork whose body chain the "
                "goto ends (the shape bf_to_line compiles); see "
                "_loop_return_legs for the geometric premises"
            )
        node = node.next
    cursor.finish()


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
            wide = bytearray()
            for level in row:
                wide += bytes([level]) * factor
            for k in range(factor):
                out.pixels[y * factor + k] = bytearray(wide)
        return out

    def save(self, path: str) -> None:
        """Write the canvas to ``path`` as an 8-bit greyscale PNG."""
        png.write_grey_file(path, self.pixels)


def _arrowhead(draw: Canvas, y: float, x: float, heading: tuple[int, int]) -> None:
    """Draw the filled triangular cursor marker at (y, x), pointing ``heading``."""
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
    """Lay out and rasterize a Line program, returning a :class:`Canvas`.

    ``start_heading`` defaults to "up", as every wiki example.  ``scale``
    replicates pixels (:func:`extract.normalize_scale` divides it out); 1
    matches the wiki.  Raise it for lossy storage: against JPEG a 1px
    drawing extracts exactly down to quality 34 and is destroyed by 28, 2x
    holds to 15, 4x to 10.  Redundancy at write time, not leniency at read
    time; :func:`extract.coverage_gap` stays strict.
    """
    # See `_EXTENT_CACHE`: `id()`-keyed, so it must not outlive its nodes.
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
