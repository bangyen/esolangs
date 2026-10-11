"""Layered residual stems with first-arrival ownership and interior joins."""

from __future__ import annotations

from esolangs.tools.helpers import (
    _residual_ids,
    _validate_truth_table,
    essential_inputs,
    permute_truth_table,
    read_at,
)

from .render import _UNIT, Canvas, Node, _arrowhead, _Cursor, chain
from .shared import CanvasPlan

type State = tuple[int, int]
type Edge = tuple[int, int, int]


class _StemCursor(_Cursor):
    def advance(self, direction: tuple[int, int], steps: int = 1) -> None:
        if steps < 0:
            raise ValueError("forward route runs backward")
        self.y += direction[0] * steps
        self.x += direction[1] * steps
        if steps:
            self._current.append((self.y, self.x))
        self.heading = direction


def forward_canvas(table: str, old_area: int) -> tuple[Node, CanvasPlan] | None:
    """Return a smaller descending residual DAG with at most 5n commands."""
    original_n = _validate_truth_table(table)
    kept = essential_inputs(table, original_n)
    n = len(kept)
    if n < 2:
        return None
    reduced = read_at(table, kept, original_n)
    levels, children, constants = _residual_ids(
        permute_truth_table(reduced, tuple(range(n - 1, -1, -1))), n
    )
    root = (0, levels[0][0])
    seen: set[State] = set()
    first: dict[State, Edge] = {}
    incoming: list[list[tuple[Edge, State]]] = [[] for _ in range(n)]

    def visit(state: State) -> None:
        if state in seen:
            return
        seen.add(state)
        depth, residual = state
        arms = (0, 1) if children[residual][0] != children[residual][1] else (0,)
        for bit in arms:
            target = children[residual][bit]
            if constants[target] is None:
                edge = depth, residual, bit
                dest = depth + 1, target
                first.setdefault(dest, edge)
                incoming[depth + 1].append((edge, dest))
                visit(dest)

    visit(root)
    joins = sum(len(edges) for edges in incoming) - len(first)
    if not joins:
        return None
    members = [
        [residual for residual in level if (depth, residual) in seen]
        for depth, level in enumerate(levels[:-1])
    ]
    forks: dict[State, tuple[int, int]] = {}
    entry: dict[State, tuple[int, int]] = {}
    join: dict[Edge, tuple[int, int]] = {}
    base = 0
    for depth, level in enumerate(members):
        extras = [(edge, dest) for edge, dest in incoming[depth] if first[dest] != edge]
        for index, residual in enumerate(level):
            state = depth, residual
            entry[state] = base + 4 + 4 * index, 25 * index
            forks[state] = (
                base + 16 + 4 * len(level) + 4 * len(extras) + 6 * index,
                25 * index,
            )
        for index, (edge, dest) in enumerate(extras):
            join[edge] = base + 8 + 4 * len(level) + 4 * index, entry[dest][1]
        # The last leaf ends 15 units below its fork; the next entry starts
        # 16 below, retaining a full 20px gap for the 15px extraction probe.
        base = forks[depth, level[-1]][0] + 12

    reads = "".join(
        "i" + (">" if index in kept and index < original_n - 1 else "")
        for index in range(original_n)
    )
    if kept[-1] < original_n - 1:
        reads += "<"
    start = -12 * original_n - 10, -40
    loader = _StemCursor(*start, (1, 0))
    for op in reads:
        loader.emit_op(op)
    loader.advance((1, 0), 6)
    loader.advance((0, 1), -loader.x)
    loader.advance((1, 0), forks[root][0] - loader.y)
    loader.finish()
    strokes = loader.strokes[:]
    graph: dict[State, Node] = {}

    def build(state: State) -> Node:
        if state in graph:
            return graph[state]
        depth, residual = state
        is_fork = children[residual][0] != children[residual][1]
        node = Node("?" if is_fork else "<")
        graph[state] = node
        y, x = forks[state]
        for bit in (0, 1) if is_fork else (0,):
            direction = (0, -1) if bit == 0 else (0, 1)
            cursor = _StemCursor(y, x, direction if is_fork else (1, 0))
            if is_fork:
                cursor.advance(direction, 8)
            else:
                cursor.advance((1, 0), 4)
                cursor.advance((0, -1), 8)
            cursor.advance((1, 0), 4)
            target = children[residual][bit]
            value = constants[target]
            if value is not None:
                correction = "" if value == bit else "+" if value else "-"
                arm = chain(*correction, "o")
                for op in correction + "o":
                    cursor.emit_op(op)
            else:
                cursor.emit_op("<")
                edge = depth, residual, bit
                dest = depth + 1, target
                tail = build(dest)
                if edge in join:
                    tail = Node("", goto=tail)
                arm = Node("<", next=tail)
                ey, ex = join.get(edge, entry[dest])
                cursor.advance((1, 0), ey - cursor.y)
                dx = ex - cursor.x
                sign = 1 if dx > 0 else -1
                if edge not in join:
                    cursor.advance((0, sign), abs(dx))
                    cursor.advance((1, 0), forks[dest][0] - cursor.y)
                else:
                    cursor.advance((0, sign), abs(dx) - 1)
                    cursor.advance((1, sign), 1)
            cursor.finish()
            strokes.extend(cursor.strokes)
            if is_fork:
                if bit == 0:
                    node.zero = arm
                else:
                    node.nonzero = arm
            else:
                node.next = arm.next
        return node

    decision = build(root)
    head = chain(*reads)
    tail = head
    while tail.next is not None:
        tail = tail.next
    tail.next = decision
    points = [point for stroke in strokes for point in stroke]
    top, bottom = min(y for y, _ in points), max(y for y, _ in points)
    left, right = min(x for _, x in points), max(x for _, x in points)
    width, height = (right - left + 2) * _UNIT, (bottom - top + 2) * _UNIT
    if width * height >= old_area:
        return None

    def rasterize() -> Canvas:
        canvas = Canvas(width, height)
        for stroke in strokes:
            canvas.line(
                [((x - left + 1) * _UNIT, (y - top + 1) * _UNIT) for y, x in stroke]
            )
        _arrowhead(
            canvas,
            (start[0] - top + 1) * _UNIT,
            (start[1] - left + 1) * _UNIT,
            (1, 0),
        )
        return canvas

    # Descending tests remove the loader rewind. At most n-1 join ticks
    # replace those moves: 2n-1 loads, n tests, n-1 moves, n-1 joins, two
    # output ops and one halt tick give 5n. Projection adds fewer than
    # 5(original_n-n) commands and never enlarges the original tape.
    return head, CanvasPlan(rasterize, width * height)
