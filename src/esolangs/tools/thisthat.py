"""thisthat boolean generator: a bistack-routed planar decision tree."""

from itertools import pairwise
from typing import Literal

from esolangs.tools.helpers import _validate_truth_table, best_input_order, read_at

_STEP = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}
_SINGLE = {
    frozenset("EW"): "─",
    frozenset("NS"): "│",
    frozenset("ES"): "┌",
    frozenset("WS"): "┐",
    frozenset("EN"): "└",
    frozenset("WN"): "┘",
    frozenset("ENS"): "├",
    frozenset("WNS"): "┤",
    frozenset("EWS"): "┬",
    frozenset("EWN"): "┴",
    frozenset("EWNS"): "┼",
}
_DOUBLE = {
    frozenset("EW"): "═",
    frozenset("NS"): "║",
    frozenset("ES"): "╔",
    frozenset("WS"): "╗",
    frozenset("EN"): "╚",
    frozenset("WN"): "╝",
    frozenset("ENS"): "╠",
    frozenset("WNS"): "╣",
    frozenset("EWS"): "╦",
    frozenset("EWN"): "╩",
    frozenset("EWNS"): "╬",
}


def _path(
    start: tuple[int, int],
    end: tuple[int, int],
    first_axis: Literal["horizontal", "vertical"],
) -> list[tuple[int, int]]:
    x, y = start
    points = [(x, y)]
    axes: tuple[tuple[int, int], ...] = ((0, end[0]), (1, end[1]))
    if first_axis == "vertical":
        axes = tuple(reversed(axes))
    for axis, target in axes:
        while (x, y)[axis] != target:
            if axis == 0:
                x += 1 if target > x else -1
            else:
                y += 1 if target > y else -1
            points.append((x, y))
    return points


def _first_axis(horizontal: int) -> Literal["horizontal", "vertical"]:
    return "horizontal" if horizontal else "vertical"


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[tuple[int, int], str] = {}
        self.wires: dict[tuple[int, int], tuple[str, set[str]]] = {}

    def node(self, point: tuple[int, int], glyph: str) -> None:
        if point in self.nodes:
            raise ValueError("thisthat layout collision")
        self.wires.pop(point, None)
        self.nodes[point] = glyph

    def connect(self, points: list[tuple[int, int]], kind: str) -> None:
        for left, right in pairwise(points):
            delta = (right[0] - left[0], right[1] - left[1])
            direction = next(name for name, step in _STEP.items() if step == delta)
            for point, port in ((left, direction), (right, _OPPOSITE[direction])):
                if point in self.nodes:
                    continue
                old_kind, ports = self.wires.setdefault(point, (kind, set()))
                if old_kind != kind:
                    raise ValueError("thisthat wire collision")
                ports.add(port)

    def render(self) -> str:
        cells = set(self.nodes) | set(self.wires)
        min_x = min(x for x, _ in cells)
        min_y = min(y for _, y in cells)
        width = max(x for x, _ in cells) - min_x + 1
        height = max(y for _, y in cells) - min_y + 1
        rows = [[" "] * width for _ in range(height)]
        for (x, y), glyph in self.nodes.items():
            rows[y - min_y][x - min_x] = glyph
        for (x, y), (kind, ports) in self.wires.items():
            glyphs = _SINGLE if kind == "single" else _DOUBLE
            rows[y - min_y][x - min_x] = glyphs[frozenset(ports)]
        return "\n".join("".join(row).rstrip() for row in rows)


def _span_ids(truth_table: str) -> list[list[int]]:
    """Name every aligned span so that equal spans share a name, in O(T).

    ``ids[level][k]`` names the ``k``-th of the ``2**level`` spans by its two
    halves' names; an all-0 span is always 0 and an all-1 span 1.
    """
    levels = [[int(bit) for bit in truth_table]]
    names = {(0, 0): 0, (1, 1): 1}
    while len(levels[-1]) > 1:
        below = levels[-1]
        levels.append(
            [
                names.setdefault(pair, len(names))
                for pair in zip(below[::2], below[1::2], strict=True)
            ]
        )
    return levels[::-1]


def _deque_plan(order: tuple[int, ...]) -> tuple[list[bool], list[bool]] | None:
    """Return head pushes by input and head pops by level that pop ``order``.

    Inputs are read in order and each goes to the row's head or tail, so
    the row reads (head first) the head-pushed inputs descending, input 0,
    then the tail-pushed ones ascending; the tree pops either end at each
    level.  Before input 0 is popped each pop is the largest left on its
    side, so that prefix splits into two descending runs, the tail run
    above every input popped after 0; those are all tail-pushed, so they
    leave the row as a run each pop takes the least or the greatest of.
    ``None`` when ``order`` has no such split: the plan is the greedy fit
    (a tie goes to the lower run), which finds every poppable order.
    """
    depth = len(order)
    zero = order.index(0)
    floor = max(order[zero + 1 :], default=-1)
    head_push = [False] * depth
    head_pop = []
    last = {True: depth, False: depth}
    for x in order[:zero]:
        fits = [
            head for head in (True, False) if x < last[head] and (head or x > floor)
        ]
        if not fits:
            return None
        head = min(fits, key=last.__getitem__)
        last[head] = x
        head_push[x] = head
        head_pop.append(head)
    head_pop.append(True)
    rest = sorted(order[zero + 1 :])
    for x in order[zero + 1 :]:
        if x not in (rest[0], rest[-1]):
            return None
        head_pop.append(x == rest[0])
        rest.remove(x)
    return head_push, head_pop


def thisthat(truth_table: str) -> str:
    """Return a planar thisthat decision tree with linear source area."""
    return _tree(truth_table)


def _tree(truth_table: str, *, prune: bool = True, reorder: bool = True) -> str:
    """Build the tree; ``prune=False`` tests every input at every node.

    Every input is read in order.  An ignored input is pushed onto the column
    stack, which nothing pops, and the tree is the projected table's; inside
    it a constant span is a leaf and a node whose halves agree pops its bit
    onto the column stack too, as Line's tree skips such a level.  The row
    is a deque, so the tree may test the kept inputs in the greedy order
    (:func:`~esolangs.tools.helpers.best_input_order`) when
    :func:`_deque_plan` can pop them in it: a read pushes to the head or the
    tail and a node pops either end, one glyph for another.  ``reorder=False``
    keeps input order.
    """
    n = _validate_truth_table(truth_table)
    ids = _span_ids(truth_table)
    # Input ``level`` is essential when some node on it has unequal halves.
    essential = [
        level
        for level in range(n)
        if not prune or ids[level + 1][::2] != ids[level + 1][1::2]
    ]
    if len(essential) < n:
        truth_table = read_at(truth_table, essential, n)
    if not (prune and reorder and essential):
        order = tuple(range(len(essential)))
        return _layout(truth_table, n, essential, order, prune=prune)
    return best_input_order(
        truth_table,
        lambda table, order: _layout(table, n, essential, order, prune=True),
    )


def _layout(
    truth_table: str,
    n: int,
    essential: list[int],
    order: tuple[int, ...],
    *,
    prune: bool,
) -> str:
    """Lay out the tree over ``truth_table``, whose level ``k`` pops ``order[k]``.

    ``order`` names essential inputs by their rank; ``""`` when the row
    cannot pop them in that order.
    """
    plan = _deque_plan(order) if order else ([], [])
    if plan is None:
        return ""
    head_push, head_pop = plan
    ids = _span_ids(truth_table)
    depth = len(essential)
    builder = _Builder()
    axes = ((1, 0), (0, 1))

    def span(level: int) -> int:
        return 8 * (1 << ((depth - level - 1) // 2)) - 2

    def tree(
        level: int,
        lo: int,
        hi: int,
        pop: tuple[int, int],
        incoming: tuple[int, int],
    ) -> None:
        index = lo >> (depth - level)
        if hi - lo == 1 or (prune and ids[level][index] < 2):
            # A constant span is a leaf wherever it sits: what it has not
            # popped is left on the stack.
            builder.node(pop, "■" if truth_table[lo] == "1" else "□")
            output = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
            builder.node(output, "◇")
            builder.connect(_path(pop, output, _first_axis(incoming[0])), "double")
            return
        builder.node(pop, "◧" if head_pop[level] else "◨")
        router = (pop[0] + 2 * incoming[0], pop[1] + 2 * incoming[1])
        axis = axes[level % 2]
        mid = (lo + hi) // 2
        children: tuple[tuple[int, int, int], ...] = ((-1, lo, mid), (1, mid, hi))
        if prune and ids[level + 1][2 * index] == ids[level + 1][2 * index + 1]:
            # The halves agree: pop the bit onto the column stack, which
            # nothing pops, and go on into the one half both values share.
            builder.node(router, "⬒")
            children = children[:1]
        else:
            builder.node(router, "◑" if axis[0] else "◒")
        builder.connect(_path(pop, router, _first_axis(incoming[0])), "double")
        for sign, child_lo, child_hi in children:
            child_incoming = (sign * axis[0], sign * axis[1])
            child = (
                router[0] + span(level) * child_incoming[0],
                router[1] + span(level) * child_incoming[1],
            )
            builder.connect(_path(router, child, _first_axis(axis[0])), "single")
            tree(level + 1, child_lo, child_hi, child, child_incoming)

    root = (0, 0)
    tree(0, 0, len(truth_table), root, (0, 1))
    min_x = min(x for x, _ in set(builder.nodes) | set(builder.wires))
    min_y = min(y for _, y in set(builder.nodes) | set(builder.wires))
    loader_y = min_y - 2
    start_x = min(min_x, root[0] - 4 * n - 2)
    builder.node((start_x, loader_y), "▣")
    previous = (start_x, loader_y)
    for i in range(n):
        diamond = (start_x + 2 + 4 * i, loader_y)
        push = (diamond[0] + 2, loader_y)
        builder.node(diamond, "◇")
        if i in essential:
            builder.node(push, "◧" if head_push[essential.index(i)] else "◨")
        else:
            builder.node(push, "⬒")
        builder.connect(_path(previous, diamond, "horizontal"), "single")
        builder.connect(_path(diamond, push, "horizontal"), "double")
        previous = push
    entry = (root[0], root[1] - 1)
    route = _path(previous, (root[0], loader_y), "horizontal")
    route += _path((root[0], loader_y), entry, "vertical")[1:]
    route.append(root)
    builder.connect(route, "single")
    return builder.render()
