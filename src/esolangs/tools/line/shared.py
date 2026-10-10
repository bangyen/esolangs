"""Share one residual through a consumed input and a native ancestor return."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from esolangs.tools.helpers import (
    _residual_ids,
    _validate_truth_table,
    permute_truth_table,
)

from .render import (
    _UNIT,
    Canvas,
    Node,
    _arrowhead,
    _Cursor,
    _layout,
    _Plan,
    chain,
)
from .tree_layout import tree_extents


def shared_tree(
    table: str, *, command_budget: int | None = None
) -> tuple[Node, int] | None:
    """Return a guarded single-return graph and its conservative command bound."""
    n = _validate_truth_table(table)
    if n < 3:
        return None
    # Testing input 1 before input 0 shortens both the loader's return and
    # the shared suffix's entry by one move; reads retain their original order.
    order = (1, 0, *range(2, n))
    levels, children, constants = _residual_ids(permute_truth_table(table, order), n)
    zero, one = children[levels[0][0]]
    if zero == one or constants[zero] is not None:
        return None
    state, depth = zero, 1
    aligned = [one]
    row = None
    while depth < n and children[state][0] == children[state][1]:
        state = children[state][0]
        depth += 1
        aligned = [child for parent in aligned for child in children[parent]]
        if depth < n and state in aligned:
            row = (1 << (depth - 1)) + aligned.index(state)
            break
    if row is None:
        return None
    root = Node("?")

    def moved(pointer: int, cell: int, rest: Node) -> Node:
        for _ in range(abs(cell - pointer)):
            rest = Node(">" if cell > pointer else "<", next=rest)
        return rest

    shared_cost = 0
    returns = 0

    def build(
        residual: int, level: int, pointer: int, known: int, start: int
    ) -> tuple[Node, int]:
        nonlocal returns
        while True:
            if level == depth and start == row:
                returns += 1
                # The nonzero root arm still holds 1 in its consumed input.
                # Clear it, return, and take the already-drawn zero arm once.
                return (
                    moved(pointer, order[0], Node("-", goto=root)),
                    abs(pointer - order[0]) + 3 + shared_cost,
                )
            if level == n or children[residual][0] != children[residual][1]:
                break
            residual = children[residual][0]
            level += 1
            start *= 2
        if level == n:
            correction = {1: ["+"], 0: [], -1: ["-"]}[residual - known]
            return chain(*correction, "o"), len(correction) + 2
        cell = order[level]
        lo, hi = children[residual]
        node = Node("?")
        node.zero, zero_cost = build(lo, level + 1, cell, 0, 2 * start)
        node.nonzero, one_cost = build(hi, level + 1, cell, 1, 2 * start + 1)
        return moved(pointer, cell, node), abs(pointer - cell) + 1 + max(
            zero_cost, one_cost
        )

    root.zero, shared_cost = build(zero, 1, order[0], 0, 0)
    root.nonzero, other_cost = build(one, 1, order[0], 1, 1)
    # The return clears an original cell; every tape value stays 0/1.
    # Removing a nonconstant subtree pays for the synthetic resume frame,
    # preserving the ledger's n+1 frame-index and 3n-2 opcode-index bits.
    commands = 3 * n - 2 + max(shared_cost, other_cost)
    budget = 5 * n if command_budget is None else command_budget
    if returns != 1 or commands > budget:
        return None
    head = chain(*("i" + ">i" * (n - 1)))
    tail = head
    while tail.next is not None:
        tail = tail.next
    tail.next = moved(n - 1, order[0], root)
    return head, commands


@dataclass(frozen=True, slots=True)
class CanvasPlan:
    """A checked return layout with its area before pixel allocation."""

    draw: Callable[[], Canvas]
    area: int

    def __call__(self) -> Canvas:
        """Rasterize the checked strokes."""
        return self.draw()


def shared_canvas(root: Node, old_area: int) -> CanvasPlan | None:
    """Return a lazy rasterizer only for a smaller, separated ancestor return."""
    contains_return: dict[int, bool] = {}

    def classify(node: Node | None) -> bool:
        if node is None:
            return False
        if node.goto is not None:
            result = True
        elif node.op == "?":
            zero, one = classify(node.zero), classify(node.nonzero)
            result = zero or one
        else:
            result = classify(node.next)
        contains_return[id(node)] = result
        return result

    classify(root)
    plan = _Plan()

    def seed(node: Node | None) -> None:
        if node is None:
            return
        if not contains_return[id(node)]:
            plan.extents.update(tree_extents(node))
        elif node.op == "?":
            seed(node.zero)
            seed(node.nonzero)
        else:
            seed(node.next)

    seed(root)
    plan.tree = set(plan.extents)
    cursor = _Cursor(0, 0, (-1, 0), occupied=set())
    try:
        _layout(root, cursor, plan)
    except ValueError:
        # The existing return rule requires its tip on the body's perimeter
        # and rejects intersections. An interior repeat stays inline.
        return None
    ys = [y for stroke in cursor.strokes for y, _ in stroke]
    xs = [x for stroke in cursor.strokes for _, x in stroke]
    top, bottom, left, right = min(ys), max(ys), min(xs), max(xs)
    width, height = (right - left + 2) * _UNIT, (bottom - top + 2) * _UNIT
    if width * height >= old_area:
        return None

    def rasterize() -> Canvas:
        canvas = Canvas(width, height)
        for stroke in cursor.strokes:
            canvas.line(
                [((x - left + 1) * _UNIT, (y - top + 1) * _UNIT) for y, x in stroke]
            )
        _arrowhead(canvas, (1 - top) * _UNIT, (1 - left) * _UNIT, (-1, 0))
        return canvas

    return CanvasPlan(rasterize, width * height)
