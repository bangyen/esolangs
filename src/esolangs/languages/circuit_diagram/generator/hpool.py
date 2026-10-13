"""Fixed-size shared cofactor pools at prefix H-tree leaves."""

from __future__ import annotations

from dataclasses import dataclass, replace

from esolangs.generation.helpers import _validate_truth_table

from .hcells import _HCellLayout
from .hlayout import (
    _depth,
    _h_reserve_terms,
    _h_route_literals,
    _h_route_results,
    _HTermPlan,
)
from .layout import _Layout, _Shape


@dataclass(frozen=True)
class _PoolBlock:
    x: int
    y: int
    width: int
    height: int

    def quadrants(self, width: int, height: int) -> tuple[_PoolBlock, ...]:
        far_x, far_y = self.width - width, self.height - height
        return tuple(
            _PoolBlock(self.x + dx, self.y + dy, width, height)
            for dx, dy in ((0, 0), (far_x, 0), (0, far_y), (far_x, far_y))
        )


@dataclass(frozen=True)
class _FooterPlan(_HTermPlan):
    leaf_height: int

    def result_anchor(self, prefix: int) -> tuple[int, int]:
        x, y = self.sites[prefix]
        return (
            (x + 4, y + self.leaf_height - 24)
            if _depth(prefix) == self.inputs
            else (x + 4, y - 3)
        )


def _atom_gate_bound(inputs: int) -> int:
    # Eight one-gate and two three-gate two-variable functions use fourteen
    # binary gates. Higher levels have at most 2**(inputs-level) residuals;
    # each takes three gates. Selector complements contribute at most inputs.
    return 14 + 3 * ((1 << (inputs - 2)) - 1) + inputs


def _large_leaf_height(inputs: int) -> int:
    # The builder uses two input rows and four rows per gate. Reserve the
    # suffix bank plus a footer below every atom, rounded to the H lattice.
    return 8 * ((_atom_gate_bound(inputs) * 4 + 10 * inputs + 59) // 8)


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


def _h_pool_area_floor(inputs: int, ports: int) -> int:
    """Bound small-pool area from its bottom-right retained term glyph."""
    tail = 3 if inputs % 2 else 4
    prefix = inputs - tail
    if prefix < 2:
        return 0
    side = _h_pool_size(prefix, tail)
    leaf, inset = (96, 8) if tail == 3 else (192, 16)
    margin = 8 * ports + 8
    return (margin + side - inset + 1) * (margin + side - leaf + 9)


def _h_pool_layout(
    table: str, *, input_order: list[int] | None = None, port_inputs: int | None = None
) -> _Layout:
    """Route fixed-size cofactor pools through a prefix H tree in O(T) area."""
    return _pool_layout(
        table,
        3 if (len(table).bit_length() - 1) % 2 else 4,
        input_order=input_order,
        port_inputs=port_inputs,
    )


def _large_pool_layout(
    table: str,
    *,
    input_order: list[int] | None = None,
    port_inputs: int | None = None,
    ceiling: int | None = None,
) -> _Layout | None:
    """Share seven/eight-input atoms under linear work, area and state bounds.

    Atom gate caps are 114/211; total G<=T+n keeps state below 7T+2n-9.
    Prefix gating and OR returns take at most 2n+2 commands. Across dense
    n=8/10/12 and n=9/11/13, native emitted growth ratios are 3.369/4.209.
    """
    n, order, ports = _pool_inputs(table, input_order, port_inputs)
    k = 7 if n % 2 else 8
    if ceiling is not None and n > k:
        leaf = _large_leaf_height(k)
        side = leaf
        for remaining in range(2, n - k + 1, 2):
            side = 2 * side + 16 * (remaining + k) + 8
        margin = 8 * ports + 8
        # Every prefix leaf retains its AND glyph, even if unselected.
        # The bottom-right one proves this floor before atoms are built.
        if (margin + side - 15) * (margin + side - leaf + 9) > ceiling:
            return None
    model = _pool_layout(table, k, input_order=order, port_inputs=ports)
    height, width = model.bounds()
    return model if ceiling is None or height * width <= ceiling else None


def _pool_inputs(
    table: str,
    order: list[int] | None,
    ports: int | None,
) -> tuple[int, list[int], int]:
    _validate_truth_table(table)
    n = len(table).bit_length() - 1
    order = list(range(n)) if order is None else order
    ports = n if ports is None else ports
    if (
        len(order) != n
        or len(set(order)) != n
        or any(index < 0 or index >= ports for index in order)
    ):
        raise ValueError("cofactor pool input order must name distinct original ports")
    return n, order, ports


def _pool_layout(
    table: str,
    k: int,
    *,
    input_order: list[int] | None,
    port_inputs: int | None,
) -> _Layout:
    from . import _circuit_diagram_model

    n, order, port_inputs = _pool_inputs(table, input_order, port_inputs)
    large = k >= 7
    if large and n <= k:
        return _circuit_diagram_model(
            table, None, input_order=order, port_inputs=port_inputs
        )
    atoms = {}
    p = n - k
    if p < 2:
        raise ValueError("cofactor pools need at least two prefix inputs")
    for i in range(0, len(table), 1 << k):
        chunk = table[i : i + (1 << k)]
        if "0" in chunk and "1" in chunk and chunk not in atoms:
            atoms[chunk] = _circuit_diagram_model(chunk, None)
    if large:
        leaf_height = _large_leaf_height(k)
        atom_width = max((atom.bounds()[1] for atom in atoms.values()), default=0)
        leaf_width = max(leaf_height, 8 * ((atom_width + 8 * k + 55) // 8))
        prefix_x, bank_y = leaf_width - 16, 8 * k + 8
    else:
        leaf_width = leaf_height = 96 if k == 3 else 192
        prefix_x, bank_y = leaf_width - (8 if k == 3 else 16), 40
    dimensions = {0: (leaf_width, leaf_height)}
    for remaining in range(2, p + 1, 2):
        width, height = dimensions[remaining - 2]
        band = 16 * (remaining + k) + 8
        dimensions[remaining] = 2 * width + band, 2 * height + band
    width, height = dimensions[p]
    blocks = {1: _PoolBlock(0, 0, width, height)}
    sites: dict[int, tuple[int, int]] = {}

    def descend(prefix: int, r: int, block: _PoolBlock) -> None:
        if r == 0:
            sites[prefix] = (block.x + prefix_x, block.y + 8)
            return
        child_width, child_height = dimensions[r - 2]
        track = 8 * (r + k)
        left, top = block.x + child_width, block.y + child_height
        sites[prefix] = (left + 2 * track + 8, top + track + 8)
        sites[2 * prefix] = (left + track, top + track)
        sites[2 * prefix + 1] = (left + track, top + 2 * track + 8)
        for bits, child in enumerate(block.quadrants(child_width, child_height)):
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

    plan: _HTermPlan = (
        _FooterPlan(p, sites, signals, literal_start, {}, set(), 0, levels, leaf_height)
        if large
        else _HTermPlan(p, sites, signals, literal_start, {}, set(), 0, levels)
    )
    layout = _HCellLayout(margin + dimensions[p][0] + 64)
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
        atom = atoms[chunk]
        h, w = atom.bounds()
        # Three/four-input bounds retain the original leaf geometry.
        # Larger atoms reserve their proven height and measured width.
        too_large = (
            w + 8 * k + 48 > leaf_width or h + 8 * k + 48 > leaf_height
            if large
            else w > (80 if k == 3 else 168) or h > (56 if k == 3 else 132)
        )
        if too_large:
            raise AssertionError(f"cofactor pool exceeded its rectangle: {w}x{h}")
        block = blocks[prefix]
        ox, oy = block.x + margin + 8, block.y + margin + bank_y
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
        # A footer's lower input must be approached from below: descending
        # along its input column would cross the upper prefix port.
        atom_routes.append(
            (
                output_point,
                (gx - 1, gy + 1),
                atom_signal,
                "under" if large else "across",
            )
        )
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
