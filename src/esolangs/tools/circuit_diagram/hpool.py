"""Fixed-size shared cofactor pools at prefix H-tree leaves."""

from __future__ import annotations

from dataclasses import replace

from esolangs.tools.helpers import _validate_truth_table

from .hcells import _HCellLayout
from .hlayout import (
    _Block,
    _depth,
    _h_reserve_terms,
    _h_route_literals,
    _h_route_results,
    _HTermPlan,
)
from .layout import _Layout, _Shape


def _h_pool_size(prefix_inputs: int, tail_inputs: int) -> int:
    """Return the prefix block side, with a constant-size cofactor pool."""
    if prefix_inputs < 0 or prefix_inputs % 2 or tail_inputs not in (3, 4):
        raise ValueError(
            "cofactor pools need an even prefix and three/four suffix inputs"
        )
    leaf = 96 if tail_inputs == 3 else 192
    if prefix_inputs == 0:
        return leaf
    return (
        2 * _h_pool_size(prefix_inputs - 2, tail_inputs)
        + 16 * (prefix_inputs + tail_inputs)
        + 8
    )


def _h_pool_layout(
    table: str, *, input_order: list[int] | None = None, port_inputs: int | None = None
) -> _Layout:
    """Route fixed-size cofactor pools through a prefix H tree in O(T) area."""
    from . import _circuit_diagram_model

    _validate_truth_table(table)
    n = len(table).bit_length() - 1
    order = list(range(n)) if input_order is None else input_order
    port_inputs = n if port_inputs is None else port_inputs
    if (
        len(order) != n
        or len(set(order)) != n
        or any(index < 0 or index >= port_inputs for index in order)
    ):
        raise ValueError("cofactor pool input order must name distinct original ports")
    k = 3 if n % 2 else 4
    p = n - k
    if p < 2:
        raise ValueError("cofactor pools need at least two prefix inputs")
    pool_side = 96 if k == 3 else 192
    prefix_x = pool_side - (8 if k == 3 else 16)

    def size(r: int) -> int:
        return _h_pool_size(r, k)

    blocks = {1: _Block(0, 0, size(p))}
    sites: dict[int, tuple[int, int]] = {}

    def descend(prefix: int, r: int, block: _Block) -> None:
        if r == 0:
            sites[prefix] = (block.x + prefix_x, block.y + 8)
            return
        childsize = size(r - 2)
        track = 8 * (r + k)
        left, top = block.x + childsize, block.y + childsize
        sites[prefix] = (left + 2 * track + 8, top + track + 8)
        sites[2 * prefix] = (left + track, top + track)
        sites[2 * prefix + 1] = (left + track, top + 2 * track + 8)
        for bits, child in enumerate(block.quadrants(childsize)):
            blocks[4 * prefix + bits] = child
            descend(4 * prefix + bits, r - 2, child)

    descend(1, p, blocks[1])
    margin = 8 * port_inputs + 8
    sites = {a: (x + margin, y + margin) for a, (x, y) in sites.items()}
    levels: list[list[int]] = [[] for _ in range(p + 1)]
    for prefix in sites:
        levels[_depth(prefix)].append(prefix)
    signals = {
        prefix: i
        for i, prefix in enumerate(prefix for prefix in sites if _depth(prefix) >= 2)
    }
    literal_start = len(signals)
    serial = literal_start + 2 * n

    def fresh() -> int:
        nonlocal serial
        serial += 1
        return serial - 1

    plan = _HTermPlan(p, sites, signals, literal_start, {}, set(), 0, levels)
    layout = _HCellLayout(margin + size(p) + 64)
    anchors = _h_reserve_terms(layout, plan)
    points: dict[int, tuple[int, int]] = {}
    values: dict[int, int | None] = {}
    atom_routes: list[tuple[tuple[int, int], tuple[int, int], int, _Shape]] = []
    feeds: list[tuple[int, int, tuple[int, int]]] = []
    for prefix in levels[p]:
        chunk = table[
            (prefix - (1 << p)) * (1 << k) : (prefix - (1 << p) + 1) * (1 << k)
        ]
        if "1" not in chunk:
            values[prefix] = None
            continue
        x, y = sites[prefix]
        if "0" not in chunk:
            values[prefix] = signals[prefix]
            points[prefix] = (x + 1, y)
            continue
        atom = _circuit_diagram_model(chunk, None)
        h, w = atom.bounds()
        # At most 12/25 gates for three/four inputs give 79x54/159x108
        # cells. Keep the return column outside that fixed atom rectangle.
        if w > (80 if k == 3 else 168) or h > (56 if k == 3 else 132):
            raise AssertionError(f"cofactor pool exceeded its rectangle: {w}x{h}")
        block = blocks[prefix]
        ox, oy = block.x + margin + 8, block.y + margin + 40
        owners = {i: plan.literal(p + i, "1") for i in range(k)}

        def owner(signal: int, mapping: dict[int, int] = owners) -> int:
            if signal not in mapping:
                mapping[signal] = fresh()
            return mapping[signal]

        output = next((a, b) for (a, b), char in atom.glyphs.items() if char == ":")
        for (a, b), char in atom.glyphs.items():
            if a == 0 or (a, b) in (output, (output[0] - 1, output[1])):
                continue
            layout.glyph(a + ox, b + oy, char)
        for (a, b), signal in atom.junctions.items():
            layout.junction(a + ox, b + oy, owner(signal))
        for row, runs in atom.horizontal.items():
            for a, b, signal in runs:
                layout.run_horizontal(a + ox - 1, b + ox, row + oy, owner(signal))
        for col, runs in atom.vertical.items():
            for a, b, signal in runs:
                layout.run_vertical(col + ox, a + oy - 1, b + oy, owner(signal))
        for i in range(k):
            target = (ox, oy + 2 * i)
            signal = plan.literal(p + i, "1")
            layout.junction(*target, signal)
            feeds.append((p + i, prefix, target))
        output_point = (output[0] - 2 + ox, output[1] + oy)
        atom_signal = owner(atom.junctions[output[0] - 2, output[1]])
        gx, gy = plan.result_anchor(prefix)
        result = fresh()
        layout.glyph(gx, gy, "a")
        layout.reserve((gx - 1, gy - 1), signals[prefix])
        layout.reserve((gx - 1, gy + 1), atom_signal)
        layout.reserve((gx + 1, gy), result)
        points[prefix] = (gx + 1, gy)
        values[prefix] = result
        atom_routes.append(((x + 1, y), (gx - 1, gy - 1), signals[prefix], "down"))
        atom_routes.append((output_point, (gx - 1, gy + 1), atom_signal, "across"))
    result_gates = set()
    for depth in range(p - 1, -1, -1):
        for prefix in levels[depth]:
            lo, hi = values.get(2 * prefix), values.get(2 * prefix + 1)
            if lo is not None and hi is not None:
                values[prefix] = fresh()
                result_gates.add(prefix)
            else:
                values[prefix] = lo if lo is not None else hi
    # The leaf offset puts every incoming suffix lane above the atom's
    # y=40 input bank. Without it dense n=8 routes cross another atom's
    # lower gate port at (1008,730); all eight-input controls now execute.
    for depth in range(p, n):
        for prefix, (x, y) in sites.items():
            below = 8 * (depth - _depth(prefix))
            point = x - 6 - below, y - 6 - below + (8 * k if _depth(prefix) == p else 0)
            anchors[depth, "1", prefix] = point
            layout.reserve(point, plan.literal(depth, "1"))
        row = 8 * order[depth]
        signal = plan.literal(depth, "1")
        layout.glyph(0, row, "-")
        layout.junction(2, row, signal)
        layout.run_horizontal(0, 2, row, signal)
        layout.route((2, row), anchors[depth, "1", 1], signal, "across")
    for index in range(port_inputs):
        if index not in order:
            signal = fresh()
            layout.glyph(0, 8 * index, "-")
            layout.junction(2, 8 * index, signal)
            layout.run_horizontal(0, 2, 8 * index, signal)
    _h_route_literals(
        layout,
        plan,
        {key: point for key, point in anchors.items() if key[0] < p},
        input_order=order[:p],
    )
    for depth in range(p, n):
        signal = plan.literal(depth, "1")
        for prefix in sites:
            point = anchors[depth, "1", prefix]
            layout.junction(*point, signal)
            if prefix != 1:
                layout.route(anchors[depth, "1", prefix // 2], point, signal)
    for depth, prefix, target in feeds:
        layout.route(anchors[depth, "1", prefix], target, plan.literal(depth, "1"))
    for source, target, signal, shape in atom_routes:
        layout.route(source, target, signal, shape)
    result_signal = values[1]
    if result_signal is None:
        raise ValueError("cofactor pools need a selected row")
    plan = replace(
        plan, results=values, result_gates=result_gates, result_signal=result_signal
    )
    _h_route_results(layout, plan, leaf_points=points)
    return layout.seal()
