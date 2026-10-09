"""Tight pixel layout of a Line tree, used for n <= 5 (see ``__init__``).

Draws the same ``Node`` tree as the lattice layout, on a southbound stroke
with 30 px stems and fork arms set to the measured subtree extent plus a
30 px gap, rounded to 10 mod 20 px so a corner never lands on a whole 20 px
unit and reads as a kink.  Mean area vs the lattice layout, smaller by
n=1 62%, n=2 62%, n=3 60%, n=4 41%, n=5 37%; at n=6 only 4% (6 of 22 tables
larger), so the lattice layout takes over there.
"""

from __future__ import annotations

from esolangs.tools.line.render import _UNIT, Canvas, Node, _arrowhead

_DIRS = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
_SOUTH = 4
_STEM = _GAP = 30
_MARGIN = 3
_TIP = 7  # _arrowhead's tip offset (0.35 unit); the base trails 4 px behind
# Kink legs per op: (turn from south in eighths, length in units).
_KINKS = {
    ">": [(1, 1), (-2, 1)],
    "<": [(-1, 1), (2, 1)],
    "i": [(1, 1), (-2, 2), (1, 1)],
    "o": [(-2, 1), (1, 2), (-2, 1)],
    "+": [(1, 1)],
    "-": [(-1, 1)],
}

Point = tuple[int, int]  # (y, x) in pixels


def _stroke(ops: list[str]) -> list[Point]:
    """Points of a southbound stroke performing ``ops``, from (0, 0)."""
    pts, (y, x) = [(0, 0)], (0, 0)
    for op in ops:
        legs = [(_SOUTH, _STEM)] + [(_SOUTH + t, _UNIT * u) for t, u in _KINKS[op]]
        for d, length in legs:
            dy, dx = _DIRS[d % 8]
            y, x = y + dy * length, x + dx * length
            pts.append((y, x))
    pts.append((y + _STEM, x))
    return pts


def _draw(node: Node) -> tuple[list[list[Point]], int, int]:
    """Strokes of the subtree at ``node`` relative to its entry, and its x extent."""
    ops = [node.op]
    while node.next is not None:
        node = node.next
        ops.append(node.op)
    fork = node if node.op == "?" else None
    pts = _stroke(ops[:-1] if fork else ops)
    if fork is None or fork.zero is None or fork.nonzero is None:
        return [pts], min(x for _, x in pts), max(x for _, x in pts)
    (zs, zlo, zhi), (ns, nlo, nhi) = _draw(fork.zero), _draw(fork.nonzero)
    arm = (zhi - nlo + _GAP) // 2 + 1
    arm += (10 - arm) % _UNIT
    fy, fx = pts[-1]
    strokes = [pts, [(fy, fx), (fy, fx - arm)], [(fy, fx), (fy, fx + arm)]]
    for sign, sub in ((-1, zs), (1, ns)):
        strokes += [[(fy + y, fx + sign * arm + x) for y, x in s] for s in sub]
    xs = [x for _, x in pts]
    return (
        strokes,
        min(fx - arm + zlo, fx + arm + nlo, *xs),
        max(fx - arm + zhi, fx + arm + nhi, *xs),
    )


def small_tree_canvas(root: Node) -> Canvas:
    """Rasterize the tree at ``root`` with the repo's stroke and arrow primitives."""
    strokes, _, _ = _draw(root)
    ys = [y for s in strokes for y, _ in s]
    xs = [x for s in strokes for _, x in s]
    top, left = min(ys) - 2 * _TIP, min(xs)
    canvas = Canvas(max(xs) - left + 2 * _MARGIN + 1, max(ys) - top + 2 * _MARGIN + 1)
    for s in strokes:
        canvas.line([(x - left + _MARGIN, y - top + _MARGIN) for y, x in s])
    _arrowhead(canvas, -_TIP - top + _MARGIN, _MARGIN - left, (1, 0))
    return canvas
