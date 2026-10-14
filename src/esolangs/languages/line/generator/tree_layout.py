"""Bottom-up extents for goto-free Line trees."""

from .render import (
    _BRANCH_SPACING,
    _FORWARD,
    _STEM_LEN,
    _TREE_GAP,
    Node,
    _op_segments,
    _rotate,
    _turn_left,
    _turn_right,
)

Extent = tuple[int, int, int, int]


def _corners(box: Extent) -> list[tuple[int, int]]:
    y0, y1, x0, x1 = box
    return [(y, x) for y in (y0, y1) for x in (x0, x1)]


def _arm_points(
    box: Extent, heading: tuple[int, int], stem: int, margin: int
) -> list[tuple[int, int]]:
    """``box``'s corners in the fork's frame, for an arm run ``margin`` clear."""
    spacing = margin + max(-box[0], 0)
    start_y = stem + heading[0] * spacing
    start_x = heading[1] * spacing
    return [
        (start_y + dy, start_x + dx)
        for point in _corners(box)
        for dy, dx in [_rotate(point, heading)]
    ]


def tree_extents(
    root: Node, *, compact: bool = True, tight: bool = True
) -> dict[int, Extent]:
    """Return every subtree's exact bounding box in one postorder pass."""
    extents: dict[int, Extent] = {}
    runs: dict[int, tuple[Node, int]] = {}
    stem = _TREE_GAP if compact else _STEM_LEN
    gap = _TREE_GAP if compact else _BRANCH_SPACING

    def fork_points(node: Node) -> list[tuple[int, int]]:
        points = [(stem, 0)]
        for arm, heading in (
            (node.zero, _turn_right(_FORWARD)),
            (node.nonzero, _turn_left(_FORWARD)),
        ):
            box = visit(arm)
            margin = 1 if compact and tight and arm is not None and box[0] == 0 else gap
            points.extend(_arm_points(box, heading, stem, margin))
        return points

    def chain_points(node: Node) -> list[tuple[int, int]]:
        visit(node.next)
        tail, count = node, 1
        if node.op in "+-" and node.next is not None and node.next.op == node.op:
            tail, following = runs[id(node.next)]
            count += following
        runs[id(node)] = tail, count
        points = []
        y = x = 0
        for (dy, dx), steps in _op_segments(node.op, count):
            y, x = y + dy * steps, x + dx * steps
            points.append((y, x))
        points.extend((y + dy, x + dx) for dy, dx in _corners(visit(tail.next)))
        return points

    def visit(node: Node | None) -> Extent:
        if node is None:
            return 0, 0, 0, 0
        if id(node) in extents:
            return extents[id(node)]
        if node.goto is not None:
            raise ValueError("a tree layout cannot contain a goto")
        points = [(0, 0)]
        points += fork_points(node) if node.op == "?" else chain_points(node)
        ys, xs = zip(*points, strict=True)
        result = min(ys), max(ys), min(xs), max(xs)
        extents[id(node)] = result
        return result

    visit(root)
    return extents
