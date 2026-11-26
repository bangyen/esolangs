"""Draw and price shared residual diagrams for thisthat."""

from collections import defaultdict
from typing import NamedTuple

from esolangs.generation.decision import DecisionLayers, decision_layers
from esolangs.languages.thisthat._drawing import _Builder, _draw_loader, _path

_MIN_NODE_BUDGET = 8


class _Dag(NamedTuple):
    layers: list[list[tuple[int, int]]]
    children: dict[tuple[int, int], list[tuple[int, int]]]
    terminal: set[tuple[int, int]]
    incoming: dict[tuple[int, int], int]


def _build_dag(diagram: DecisionLayers) -> _Dag:
    """Plan buses and distinct-parent counts over canonical decision layers."""
    root = (0, diagram.root)
    seen = {root}
    pending = [[root]] + [[] for _ in range(len(diagram.children) - 1)]
    layers = []
    incoming: dict[tuple[int, int], int] = defaultdict(int)
    children = {}
    terminal = set()
    for level, under in enumerate(diagram.children):
        layer = pending[level]
        layers.append(layer)
        for key in layer:
            zero_id, one_id = under[key[1]]
            kids = []
            for side, state in enumerate((zero_id, one_id)):
                child = (-1, state) if state < 2 else (level + 1, state)
                if child[0] < 0:
                    terminal.add(child)
                elif child not in seen:
                    seen.add(child)
                    pending[level + 1].append(child)
                # A node's two arms to one child count once: sharing means
                # distinct parents, which is what admits a DAG at all.
                if side == 0 or zero_id != one_id:
                    incoming[child] += 1
                kids.append(child)
            children[key] = kids
    return _Dag(layers, children, terminal, incoming)


def _draw_nodes(
    builder: _Builder,
    nodes: list[tuple[int, int]],
    ys: dict[tuple[int, int], int],
    columns: dict[tuple[int, int], int],
    children: dict[tuple[int, int], list[tuple[int, int]]],
) -> tuple[dict[tuple[int, int], int], dict[int, dict[int, int]]]:
    """Draw every node and its outgoing wires; return (costs, bus events)."""
    # Two column banks alternate with depth. A bank's old edges end before
    # its next parents begin; constants retain their own two downward buses.
    costs: dict[tuple[int, int], int] = {}
    buses: dict[int, dict[int, int]] = {}
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
            builder.node(point, "◧")
            zero, one = children[key]
            builder.node(router, "◒")
            steps = []
            for sign, child in ((-1, zero), (1, one)):
                row = y + 2 * sign
                col = columns[child]
                target_y = ys[child] - 4
                builder.node((col, row), "▼")
                builder.connect(_path(router, (2, row), "vertical"), "single")
                builder.connect(_path((2, row), (col, row), "horizontal"), "single")
                events = buses.setdefault(col, {})
                events[row] = events.get(row, 0) + 1
                events[target_y] = events.get(target_y, 0) - 1
                steps.append(6 + 2 * col + target_y - row + costs[child])
            costs[key] = max(steps)
        builder.connect(_path(point, router, "horizontal"), "double")
    return costs, buses


def _draw_buses(builder: _Builder, buses: dict[int, dict[int, int]]) -> None:
    """Draw each bus column as its merged runs of overlapping edges."""
    # Merge overlapping bus edges before drawing: independently tracing every
    # route to a terminal costs N² on a narrow N-node DAG. Each bus is scanned
    # once within the admitted rectangle, keeping construction O(T).
    for col, events in buses.items():
        active = 0
        begin = None
        for row in range(min(events), max(events) + 1):
            active += events.get(row, 0)
            if active and begin is None:
                begin = row
            elif not active and begin is not None:
                builder.connect(_path((col, begin), (col, row), "vertical"), "single")
                begin = None


def _hollow_crossings(builder: _Builder) -> None:
    """Turn four-way single-wire crossings into hollow arrows."""
    # Hollow downward arrows pass horizontal traffic straight through while
    # keeping vertical traffic downward; solid arrows merge at destinations.
    for point, (kind, ports) in list(builder.wires.items()):
        if kind == "single" and ports == set("EWNS"):
            builder.node(point, "▽")


def _draw_input_chain(builder: _Builder, n: int, m: int, ess: list[int]) -> None:
    """Draw the input-reading chain feeding the root entry."""
    previous = _draw_loader(builder, (-(2 * n + 2 * m + 2), -6), n, ess)
    builder.connect(
        _path(previous, (0, -6), "horizontal")
        + _path((0, -6), (0, -4), "vertical")[1:],
        "single",
    )


def _draw_shared(
    table: str, n: int, ess: list[int], limit: int
) -> tuple[str, int] | None:
    """Return the shared grid and its maximum cycles if it fits."""
    m = len(ess)
    layers, children, terminal, incoming = _build_dag(decision_layers(table))
    if not any(key[0] >= 0 and count > 1 for key, count in incoming.items()):
        return None
    nodes = [key for layer in layers for key in layer] + sorted(terminal)
    banks = [
        max((len(layer) for layer in layers[parity::2]), default=0) for parity in (0, 1)
    ]
    # The former node cap bounded both dimensions independently. Price their
    # product instead, admitting long narrow DAGs within the same O(T) envelope.
    count = len(nodes)
    width = 2 * sum(banks) + 2 * n + 2 * m + 9
    height = 8 * count - 1
    if width * height > (4 * limit + 4 * n + 9) * (8 * limit - 1):
        return None
    slots = {key: slot for layer in layers for slot, key in enumerate(layer)}
    columns = {
        key: 4 + 2 * key[1]
        if key[0] < 0
        else 8 + 2 * (slots[key] + banks[0] * (key[0] % 2))
        for key in nodes
    }
    ys = {key: 8 * i for i, key in enumerate(nodes)}
    builder = _Builder()
    costs, buses = _draw_nodes(builder, nodes, ys, columns, children)
    _draw_buses(builder, buses)
    _hollow_crossings(builder)
    _draw_input_chain(builder, n, m, ess)
    return builder.render(), 2 * n + 2 * m + 4 + costs[nodes[0]]
