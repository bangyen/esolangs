"""Line's emitted pixels: the full residual tree's box, worst over leaf shapes."""

from esolangs.languages.line.generator.layout import (
    _FORWARD,
    _TREE_GAP,
    _op_segments,
    _rotate,
    _turn_left,
    _turn_right,
)
from esolangs.languages.line.generator.render import _UNIT

type Box = tuple[int, int, int, int]  # (top, bottom, left, right), in units


def _corners(box: Box) -> list[tuple[int, int]]:
    return [(y, x) for y in box[:2] for x in box[2:]]


def _span(points: list[tuple[int, int]]) -> Box:
    ys, xs = zip(*points, strict=True)
    return min(ys), max(ys), min(xs), max(xs)


def _chain(ops: str, tail: Box) -> Box:
    """Box of ``ops`` drawn one after another, then ``tail`` from where they end."""
    for op in reversed(ops):
        points = [(0, 0)]
        y = x = 0
        for (dy, dx), steps in _op_segments(op, 1):
            y, x = y + dy * steps, x + dx * steps
            points.append((y, x))
        points += [(y + cy, x + cx) for cy, cx in _corners(tail)]
        tail = _span(points)
    return tail


def _fork(zero: Box, nonzero: Box) -> Box:
    """Box of a ``?`` whose arms turn right (zero) and left (nonzero)."""
    points = [(0, 0), (_TREE_GAP, 0)]
    for box, heading in (
        (zero, _turn_right(_FORWARD)),
        (nonzero, _turn_left(_FORWARD)),
    ):
        margin = 1 if box[0] == 0 else _TREE_GAP
        spacing = margin + max(-box[0], 0)
        for corner in _corners(box):
            dy, dx = _rotate(corner, heading)
            points.append(
                (_TREE_GAP + heading[0] * spacing + dy, heading[1] * spacing + dx)
            )
    return _span(points)


def _maximal(boxes: set[Box]) -> set[Box]:
    """Drop every box another contains: _fork and _chain only grow with their arms."""
    return {
        a
        for a in boxes
        if not any(
            b != a and b[0] <= a[0] and b[1] >= a[1] and b[2] <= a[2] and b[3] >= a[3]
            for b in boxes
        )
    }


def _pixels(n: int, _: str) -> int:
    """F: the tree's box in pixels for the worst leaf shapes, n >= 6.

    A leaf is `o`, `+o` (zero arm) or `-o` (nonzero arm); every subtree's leaf
    shapes are free, so each level keeps every box a subtree can have.
    """
    nothing: Box = (0, 0, 0, 0)
    zero = {_chain("o", nothing), _chain("+o", nothing)}
    one = {_chain("o", nothing), _chain("-o", nothing)}
    boxes = {_fork(a, b) for a in zero for b in one}
    for _step in range(n - 1):
        boxes = _maximal({_chain(">", box) for box in boxes})
        boxes = _maximal({_fork(a, b) for a in boxes for b in boxes})
    root = {_chain("i" + ">i" * (n - 1) + "<" * (n - 1), box) for box in boxes}
    return max((b[1] - b[0] + 2) * (b[3] - b[2] + 2) for b in root) * _UNIT**2


FORMULAS = {"scaling": (_pixels, True, (6, 7))}
