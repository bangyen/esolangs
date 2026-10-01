"""Bottom-up extents for goto-free Line trees."""

from .render import (
    _BRANCH_SPACING,
    _FORWARD,
    _STEM_LEN,
    Node,
    _op_segments,
    _rotate,
    _turn_left,
    _turn_right,
)

Extent = tuple[int, int, int, int]


def tree_extents(root: Node) -> dict[int, Extent]:
    """Return every subtree's exact bounding box in one postorder pass."""
    extents: dict[int, Extent] = {}
    runs: dict[int, tuple[Node, int]] = {}

    def corners(box: Extent) -> list[tuple[int, int]]:
        y0, y1, x0, x1 = box
        return [(y, x) for y in (y0, y1) for x in (x0, x1)]

    def visit(node: Node | None) -> Extent:
        if node is None:
            return 0, 0, 0, 0
        if id(node) in extents:
            return extents[id(node)]
        if node.goto is not None:
            raise ValueError("a tree layout cannot contain a goto")
        points = [(0, 0)]
        if node.op == "?":
            points.append((_STEM_LEN, 0))
            for arm, heading in (
                (node.zero, _turn_right(_FORWARD)),
                (node.nonzero, _turn_left(_FORWARD)),
            ):
                box = visit(arm)
                spacing = _BRANCH_SPACING + max(-box[0], 0)
                start_y = _STEM_LEN + heading[0] * spacing
                start_x = heading[1] * spacing
                points.extend(
                    (start_y + dy, start_x + dx)
                    for point in corners(box)
                    for dy, dx in [_rotate(point, heading)]
                )
        else:
            visit(node.next)
            tail, count = node, 1
            if node.op in "+-" and node.next is not None and node.next.op == node.op:
                tail, following = runs[id(node.next)]
                count += following
            runs[id(node)] = tail, count
            y = x = 0
            for (dy, dx), steps in _op_segments(node.op, count):
                y, x = y + dy * steps, x + dx * steps
                points.append((y, x))
            points.extend((y + dy, x + dx) for dy, dx in corners(visit(tail.next)))
        ys, xs = zip(*points, strict=True)
        result = min(ys), max(ys), min(xs), max(xs)
        extents[id(node)] = result
        return result

    visit(root)
    return extents
