"""A bounded residual DAG with downward buses and directed crossings."""

from collections import defaultdict
from math import isqrt

from esolangs.tools.helpers import (
    _validate_truth_table,
    deque_plan,
    read_at,
    subtree_ids,
)

_MIN_NODE_BUDGET = 8


def shared_tree(table: str) -> tuple[str, int] | None:
    """Return a shared grid and maximum cycles within a two-square-root node budget."""
    from esolangs.tools.thisthat import _Builder, _essential, _path

    n = _validate_truth_table(table)
    limit = max(_MIN_NODE_BUDGET, 2 * isqrt(len(table)))
    ess = _essential(subtree_ids(table), n)
    if not ess:
        return None
    table = read_at(table, ess, n)
    m = len(ess)
    ids = subtree_ids(table)
    representatives = {(0, ids[0][0]): 0}
    layers = []
    incoming: dict[tuple[int, int], int] = defaultdict(int)
    children = {}
    terminal = set()
    for level in range(m):
        layer = [key for key in representatives if key[0] == level]
        layers.append(layer)
        for key in layer:
            lo = representatives[key]
            span = 1 << (m - level)
            idx = lo // span
            zero_id, one_id = ids[level + 1][2 * idx : 2 * idx + 2]
            kids = []
            for side, (state, row) in enumerate(
                ((zero_id, lo), (one_id, lo + span // 2))
            ):
                child = (-1, state) if state < 2 else (level + 1, state)
                if child[0] < 0:
                    terminal.add(child)
                else:
                    representatives.setdefault(child, row)
                if side == 0 or zero_id != one_id:
                    incoming[child] += 1
                kids.append(child)
            if len(representatives) + len(terminal) > limit:
                return None
            children[key] = kids
    if not any(key[0] >= 0 and count > 1 for key, count in incoming.items()):
        return None
    nodes = [key for layer in layers for key in layer] + sorted(terminal)
    maximum = max(map(len, layers))
    slots = {key: slot for layer in layers for slot, key in enumerate(layer)}
    columns = {
        key: 4 + 2 * key[1]
        if key[0] < 0
        else 8 + 2 * (slots[key] + maximum * (key[0] % 2))
        for key in nodes
    }
    ys = {key: 8 * i for i, key in enumerate(nodes)}
    builder = _Builder()
    plan = deque_plan(tuple(range(m)))
    if plan is None:
        raise ValueError("input order has no deque plan")
    push, pop = plan
    # Two column banks alternate with depth. A bank's old edges end before
    # its next parents begin; constants retain their own two downward buses.
    costs: dict[tuple[int, int], int] = {}
    for key in reversed(nodes):
        y = ys[key]
        entry = (0, y - 4)
        point = (0, y)
        router = (2, y)
        bus = columns[key]
        builder.node(entry, "▼")
        builder.node((bus, y - 4), "◀")
        builder.connect(_path((bus, y - 4), entry, "horizontal"), "single")
        builder.connect(_path(entry, point, "vertical"), "single")
        if key[0] < 0:
            builder.node(point, "■" if key[1] else "□")
            builder.node(router, "◇")
            costs[key] = 7
        else:
            level = key[0]
            builder.node(point, "◧" if pop[level] else "◨")
            zero, one = children[key]
            builder.node(router, "⬒" if zero == one else "◒")
            edges = [(1, one)] if zero == one else [(-1, zero), (1, one)]
            steps = []
            for sign, child in edges:
                row = y + 2 * sign
                col = columns[child]
                target_y = ys[child] - 4
                builder.node((col, row), "▼")
                builder.connect(_path(router, (2, row), "vertical"), "single")
                builder.connect(_path((2, row), (col, row), "horizontal"), "single")
                builder.connect(
                    _path((col, row), (col, target_y), "vertical"), "single"
                )
                steps.append(6 + 2 * col + target_y - row + costs[child])
            costs[key] = max(steps)
        builder.connect(_path(point, router, "horizontal"), "double")
    # Hollow downward arrows pass horizontal traffic straight through while
    # keeping vertical traffic downward; solid arrows merge at destinations.
    for point, (kind, ports) in list(builder.wires.items()):
        if kind == "single" and ports == set("EWNS"):
            builder.node(point, "▽")
    start = (-(2 * n + 2 * m + 2), -6)
    builder.node(start, "▣")
    previous = start
    for i in range(n):
        diamond = (previous[0] + 2, -6)
        builder.node(diamond, "◇")
        builder.connect(_path(previous, diamond, "horizontal"), "single")
        previous = diamond
        if i in ess:
            p = (previous[0] + 2, -6)
            builder.node(p, "◧" if push[ess.index(i)] else "◨")
            builder.connect(_path(previous, p, "horizontal"), "double")
            previous = p
    builder.connect(
        _path(previous, (0, -6), "horizontal")
        + _path((0, -6), (0, -4), "vertical")[1:],
        "single",
    )
    return builder.render(), 2 * n + 2 * m + 4 + costs[nodes[0]]
