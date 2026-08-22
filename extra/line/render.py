"""Render Line programs to PNG images.

Line (https://esolangs.org/wiki/Line) has no text format at all -- the wiki
page defines every instruction as a hand-drawn curve shape (image files), and
is tagged "Unimplemented".  This module is a standalone renderer, not an
interpreter: it takes a small opcode sequence, lays it out as a path on a
grid, and rasterizes it into an image shaped like the wiki's own examples --
straight runs, unlabeled corners, a small diagonal kink for each of the seven
instructions, and a filled triangular arrowhead marking the cursor.

The kink shapes below (``_OPS``) were measured pixel-by-pixel directly from
the wiki's own reference images (``Lineanim4.png`` through ``Lineanim11.png``,
plus ``Lineanim6.png`` for repeats), and fall into two distinct families, not
one shared template -- see the comment directly above ``_OPS`` for the full
measurement.  In short: ``+``/``-`` are a single diagonal jog with no
sideways connector, and repeating one back to back *stretches that same
diagonal* rather than drawing separate kinks (``+++`` measured at exactly 3x
a lone ``+``'s diagonal length in ``Lineanim6.png``).  ``>``/``<``/``i``/``o``
each have a short *purely sideways* connector (not another diagonal) bridging
one or two diagonal legs, are not mergeable the same way, and are always
drawn as their own fixed-size kink even when repeated.  This module does not
invent new geometry -- it replays those measured run-length templates at an
arbitrary grid position and heading.

Conditional turn (``?``) is not a 2-endpoint kink like the others: the wiki's
``Lineanim9.png`` shows a real T-branch, one incoming stem meeting a
horizontal bar with an exit to either side.  ``_layout`` gives it two
children (taken on nonzero vs zero) instead of one successor.

This is the generation direction only, and is intentionally simpler than
extracting a program back out of an image: a generator controls its own
layout, so it can keep unrelated strokes far enough apart that they never
touch except at an intended branch -- sidestepping the crossing-vs-merge
ambiguity that makes the reverse (image -> program) direction hard.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

try:
    from PIL import Image, ImageDraw
except ImportError as _exc:  # pragma: no cover - environment guard
    raise ImportError(
        "Rendering Line programs requires Pillow: pip install Pillow"
    ) from _exc

# One grid unit in output pixels.  The wiki's own images use roughly this
# scale for a single straight run between kinks.
_UNIT = 20

# Cardinal headings as (dy, dx) unit vectors in grid space.  Diagonal jogs
# combine a heading with the perpendicular ("right"/"left") direction, so
# they move one step forward *and* one step sideways at once -- matching the
# true 45-degree kink measured from the wiki's images (e.g. the `+` opcode's
# middle run was `(-1, 1)` per step: forward and right together), not two
# separate orthogonal legs.
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

    Distinguishes ``>``/``<``/``i``/``o`` from ``+``/``-``: measured directly
    from the wiki's own reference images (Lineanim7/8/10/11.png), each of
    those four kinks includes a short *purely sideways* connector -- not
    another 45-degree diagonal -- bridging its diagonal leg(s), which
    ``+``/``-`` do not have at all.
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


# Each opcode is a sequence of (relative_direction, run_length) segments,
# relative to the cursor's current heading, replaying the run-length
# breakdown measured pixel-by-pixel from the wiki's own reference images at
# _UNIT-sized steps.  Two distinct kink families, confirmed by measuring
# every one of Lineanim4/5/6/7/8/10/11.png rather than assuming a shared
# template:
#
# * `+`/`-` (Lineanim4.png, Lineanim5.png) are a single diagonal jog with no
#   sideways connector -- `vertical(2) -> diagonal(1) -> vertical(2)`.  Their
#   diagonal leg's *length in units is the run's opcode count*, not a fixed
#   1: Lineanim6.png shows three consecutive `+` as one continuous diagonal
#   3 units long, not three separate kinks stitched together (confirmed by
#   measuring its diagonal run at exactly 3x a single `+`'s).  `_OPS["+"]`
#   and `_OPS["-"]` below are therefore templates over a `count` parameter,
#   built by :func:`_op_segments` rather than being a fixed list like the
#   others -- see :func:`_Cursor.emit_op`, which is what actually supplies
#   `count` from consecutive same-op runs in the node chain.
# * `>`/`<`/`i`/`o` (Lineanim7/8/10/11.png) additionally have a short *pure
#   sideways* connector (no forward motion at all -- see `_horiz_right`/
#   `_horiz_left`) bridging their diagonal leg(s), which is what visually
#   distinguishes them from the plain `+`/`-` kink; `i`/`o` have one more
#   diagonal leg than `>`/`<` (confirmed: Lineanim10.png's path is taller
#   than Lineanim7.png's by almost exactly one extra unit-diagonal's worth of
#   rows).  Unlike `+`/`-`, repeats of these are never merged -- there is no
#   wiki example showing it, and each is always drawn as its own fixed-size
#   kink even back-to-back with an identical one.
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
    """Look up one opcode's kink template, expanding `+`/`-`'s run by `count`.

    `+`/`-` are the only opcodes whose repeats visually merge (see the
    `_OPS` comment above) -- their diagonal leg is `count` units long rather
    than the fixed length every other entry in `_OPS` uses.
    """
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

        The heading used to rotate each leg is frozen at the start of the
        opcode: the diagonal jog's own direction is not a cardinal heading,
        so letting it become ``self.heading`` mid-opcode would make the
        following leg drift instead of returning to the original travel
        direction, as the wiki's images show (vertical in, diagonal jog,
        vertical out -- same orientation before and after).

        ``count`` merges that many consecutive identical opcodes into one
        stretched kink -- only meaningful for ``+``/``-`` (see the ``_OPS``
        comment); :func:`_layout` is what actually counts a run of identical
        nodes and passes it through here.
        """
        entry_heading = self.heading
        for rel_dir, run in _op_segments(op, count):
            self.advance(_rotate(rel_dir, entry_heading), run)
        self.heading = entry_heading

    def branch(self) -> tuple[_Cursor, _Cursor]:
        """Split into two cursors (taken / not-taken) at the current point.

        Models the conditional-turn instruction's T-branch (measured from
        ``Lineanim9.png``): one incoming stem, two outgoing arms, turning
        right when the tape cell is zero and left otherwise.
        """
        self.finish()
        right = _Cursor(self.y, self.x, _turn_right(self.heading))
        left = _Cursor(self.y, self.x, _turn_left(self.heading))
        return right, left

    def finish(self) -> None:
        if len(self._current) > 1:
            self.strokes.append(self._current)
        self._current = [(self.y, self.x)]


@dataclass
class Node:
    """One step of a Line program: an opcode, or a conditional branch.

    ``op`` is one of ``+ - < > i o`` for a straight-through instruction, or
    ``?`` for the conditional turn.  ``next`` is the following node for a
    straight-through op; ``zero``/``nonzero`` are the two branches taken by
    ``?``, matching the wiki's "turn right if the current cell is 0,
    otherwise turn left" rule.
    """

    op: str
    next: Node | None = None
    zero: Node | None = None
    nonzero: Node | None = None


def chain(*ops: str) -> Node:
    """Build a straight-through Node chain from an opcode string, e.g. "+++"."""
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


# The only opcodes whose consecutive repeats visually merge into one
# stretched kink rather than drawing separately, back to back (see the
# `_OPS` comment in this module -- confirmed against Lineanim6.png, and
# there is no wiki example showing merged >/</i/o).
_MERGEABLE = {"+", "-"}


def _layout(node: Node | None, cursor: _Cursor) -> None:
    while node is not None:
        if node.op == "?":
            cursor.advance(cursor.heading, 1)  # stem into the branch point
            right, left = cursor.branch()
            _layout(node.zero, right)
            _layout(node.nonzero, left)
            right.finish()
            left.finish()
            cursor.strokes.extend(right.strokes)
            cursor.strokes.extend(left.strokes)
            return
        op, count = node.op, 1
        if op in _MERGEABLE:
            while node.next is not None and node.next.op == op:
                node = node.next
                count += 1
        cursor.emit_op(op, count)
        node = node.next
    cursor.finish()


def _arrowhead(
    draw: ImageDraw.ImageDraw, y: float, x: float, heading: tuple[int, int]
) -> None:
    """Draw the filled triangular cursor marker at (y, x), pointing ``heading``.

    Shape matches the arrowhead isolated from the wiki's reference images via
    distance-transform (a small filled triangle distinct from the 1px-wide
    path strokes), scaled to this renderer's ``_UNIT``.
    """
    hy, hx = heading
    ly, lx = _turn_left(heading)
    size = _UNIT * 0.35
    back = size * 0.6
    tip = (x + hx * size, y + hy * size)
    base_l = (x - hx * back + lx * back, y - hy * back + ly * back)
    base_r = (x - hx * back - lx * back, y - hy * back - ly * back)
    draw.polygon([tip, base_l, base_r], fill="black")


def render(root: Node, start_heading: tuple[int, int] = (-1, 0)) -> Image.Image:
    """Lay out and rasterize a Line program, returning a Pillow ``Image``.

    ``start_heading`` defaults to "up", matching every wiki example (the
    cursor starts at the bottom of the drawing and travels upward).
    """
    cursor = _Cursor(0, 0, start_heading)
    _layout(root, cursor)

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

    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)
    for stroke in cursor.strokes:
        draw.line([to_px(p) for p in stroke], fill=0, width=1)

    start_px, start_py = to_px((0, 0))
    _arrowhead(draw, start_py, start_px, start_heading)
    return image


if __name__ == "__main__":
    program = chain(*sys.argv[1]) if len(sys.argv) > 1 else chain("+", "+", "+")
    render(program).save(sys.argv[2] if len(sys.argv) > 2 else "line_out.png")
