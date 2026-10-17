"""Fixed-size shared cofactor pools at prefix H-tree leaves."""

from __future__ import annotations

from dataclasses import dataclass, replace

from esolangs.generation.helpers import _validate_truth_table

from .hcells import _HCellLayout
from .hlayout import (
    _Block,
    _depth,
    _h_reserve_terms,
    _h_route_literals,
    _h_route_results,
    _HTermPlan,
    _merge_results,
)
from .layout import _Layout, _resolve_order, _Shape


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


def _atom_inputs(n: int) -> int:
    """Return a class's input width: seven when ``n`` is odd, else eight."""
    return 7 if n % 2 else 8


def _atom_gate_bound(inputs: int) -> int:
    # Eight one-gate and two three-gate two-variable functions use fourteen
    # binary gates. Higher levels have at most 2**(inputs-level) residuals;
    # each takes three gates. Selector complements contribute at most inputs.
    return 14 + 3 * ((1 << (inputs - 2)) - 1) + inputs


def _large_leaf_height(inputs: int) -> int:
    # The builder uses two input rows and four rows per gate. Reserve the
    # suffix bank plus a footer below every atom, rounded to the H lattice.
    return 8 * ((_atom_gate_bound(inputs) * 4 + 10 * inputs + 59) // 8)


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
    k = _atom_inputs(n)
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
    order, ports = _resolve_order(order, n, ports, "cofactor pool")
    return n, order, ports


def _pool_atoms(table: str, k: int, p: int) -> dict[str, _Layout]:
    """Return one atom layout per distinct mixed suffix chunk."""
    from . import _circuit_diagram_model

    if p < 2:
        raise ValueError("cofactor pools need at least two prefix inputs")
    atoms: dict[str, _Layout] = {}
    for i in range(0, len(table), 1 << k):
        chunk = table[i : i + (1 << k)]
        if "0" in chunk and "1" in chunk and chunk not in atoms:
            atoms[chunk] = _circuit_diagram_model(chunk, None)
    return atoms


@dataclass(frozen=True)
class _PoolGeometry:
    leaf_height: int
    prefix_x: int
    bank_y: int
    dimensions: dict[int, tuple[int, int]]


def _pool_geometry(k: int, p: int) -> _PoolGeometry:
    """Leaf rectangle plus the block size at every even prefix depth."""
    # Every atom is at most 375 (k=7) / 587 (k=8) wide, inside the leaf's
    # 584 / 976 square, whatever the table: the stride lemma bounds an atom's
    # strides by 2**(k-2) + 3k + 7 at six columns each (``_check_fits``).
    leaf = _large_leaf_height(k)
    prefix_x, bank_y = leaf - 16, 8 * k + 8
    dimensions = {0: (leaf, leaf)}
    for remaining in range(2, p + 1, 2):
        width, height = dimensions[remaining - 2]
        band = 16 * (remaining + k) + 8
        dimensions[remaining] = 2 * width + band, 2 * height + band
    return _PoolGeometry(leaf, prefix_x, bank_y, dimensions)


def _descend(
    sites: dict[int, tuple[int, int]],
    blocks: dict[int, _Block],
    geometry: _PoolGeometry,
    k: int,
    prefix: int,
    r: int,
    block: _Block,
) -> None:
    """Record every prefix site and leaf block under ``block``."""
    if r == 0:
        sites[prefix] = (block.x + geometry.prefix_x, block.y + 8)
        return
    child_width, child_height = geometry.dimensions[r - 2]
    track = 8 * (r + k)
    left, top = block.x + child_width, block.y + child_height
    sites[prefix] = (left + 2 * track + 8, top + track + 8)
    sites[2 * prefix] = (left + track, top + track)
    sites[2 * prefix + 1] = (left + track, top + 2 * track + 8)
    for bits, child in enumerate(block.quadrants(child_width, child_height)):
        blocks[4 * prefix + bits] = child
        _descend(sites, blocks, geometry, k, 4 * prefix + bits, r - 2, child)


class _Serial:
    """Fresh signal numbers above the literal range."""

    def __init__(self, start: int) -> None:
        self._next = start

    def fresh(self) -> int:
        self._next += 1
        return self._next - 1

    def owner(self, mapping: dict[int, int], signal: int) -> int:
        """Return the pool signal for an atom-local ``signal``, minting it once."""
        if signal not in mapping:
            mapping[signal] = self.fresh()
        return mapping[signal]


class _PoolBuild:
    """Pool layout under construction; the methods run in emission order."""

    def __init__(
        self,
        table: str,
        k: int,
        order: list[int],
        ports: int,
        atoms: dict[str, _Layout],
    ) -> None:
        self.table, self.k, self.order, self.ports = table, k, order, ports
        self.atoms = atoms
        self.n = len(table).bit_length() - 1
        self.p = self.n - k
        self.geometry = _pool_geometry(k, self.p)
        width, height = self.geometry.dimensions[self.p]
        self.blocks = {1: _Block(0, 0, width, height)}
        raw: dict[int, tuple[int, int]] = {}
        _descend(raw, self.blocks, self.geometry, k, 1, self.p, self.blocks[1])
        self.margin = 8 * ports + 8
        self.sites = {
            a: (x + self.margin, y + self.margin) for a, (x, y) in raw.items()
        }
        self.levels: list[list[int]] = [[] for _ in range(self.p + 1)]
        for prefix in self.sites:
            self.levels[_depth(prefix)].append(prefix)
        self.signals = {
            prefix: i
            for i, prefix in enumerate(
                prefix for prefix in self.sites if _depth(prefix) >= 2
            )
        }
        literal_start = len(self.signals)
        self.serial = _Serial(literal_start + 2 * self.n)
        self.plan = _FooterPlan(
            self.p,
            self.sites,
            self.signals,
            literal_start,
            {},
            set(),
            0,
            self.levels,
            self.geometry.leaf_height,
        )
        self.layout = _HCellLayout(self.margin + width + 64)
        self.anchors = _h_reserve_terms(self.layout, self.plan)
        self.points: dict[int, tuple[int, int]] = {}
        self.values: dict[int, int | None] = {}
        self.atom_routes: list[
            tuple[tuple[int, int], tuple[int, int], int, _Shape]
        ] = []
        self.feeds: list[tuple[int, int, tuple[int, int]]] = []

    def place_leaves(self) -> None:
        """Place each prefix leaf's constant or atom with its footer gate."""
        p, k = self.p, self.k
        for prefix in self.levels[p]:
            offset = (prefix - (1 << p)) * (1 << k)
            chunk = self.table[offset : offset + (1 << k)]
            if "1" not in chunk:
                self.values[prefix] = None
                continue
            x, y = self.sites[prefix]
            if "0" not in chunk:
                self.values[prefix] = self.signals[prefix]
                self.points[prefix] = (x + 1, y)
                continue
            self._place_atom(prefix, self.atoms[chunk])

    def _check_fits(self, atom: _Layout) -> None:
        h, w = atom.bounds()
        k, leaf = self.k, self.geometry.leaf_height
        # The leaf reserves the atom's proven height and width, plus the
        # suffix bank and footer.
        if w + 8 * k + 48 > leaf or h + 8 * k + 48 > leaf:
            raise AssertionError(f"cofactor pool exceeded its rectangle: {w}x{h}")

    def _place_atom(self, prefix: int, atom: _Layout) -> None:
        p, k, layout, plan = self.p, self.k, self.layout, self.plan
        self._check_fits(atom)
        block = self.blocks[prefix]
        ox = block.x + self.margin + 8
        oy = block.y + self.margin + self.geometry.bank_y
        owners = {i: plan.literal(p + i, "1") for i in range(k)}

        def owner(signal: int) -> int:
            return self.serial.owner(owners, signal)

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
            layout.junction(*target, plan.literal(p + i, "1"))
            self.feeds.append((p + i, prefix, target))
        output_point = (output[0] - 2 + ox, output[1] + oy)
        atom_signal = owner(atom.junctions[output[0] - 2, output[1]])
        self._place_footer(prefix, output_point, atom_signal)

    def _place_footer(
        self, prefix: int, output_point: tuple[int, int], atom_signal: int
    ) -> None:
        layout, signals = self.layout, self.signals
        x, y = self.sites[prefix]
        gx, gy = self.plan.result_anchor(prefix)
        result = self.serial.fresh()
        layout.glyph(gx, gy, "a")
        layout.reserve((gx - 1, gy - 1), signals[prefix])
        layout.reserve((gx - 1, gy + 1), atom_signal)
        layout.reserve((gx + 1, gy), result)
        self.points[prefix] = (gx + 1, gy)
        self.values[prefix] = result
        self.atom_routes.append(((x + 1, y), (gx - 1, gy - 1), signals[prefix], "down"))
        # A footer's lower input must be approached from below: descending
        # along its input column would cross the upper prefix port.
        self.atom_routes.append((output_point, (gx - 1, gy + 1), atom_signal, "under"))

    def merge_results(self) -> set[int]:
        """OR sibling values up the tree; return the prefixes that get a gate."""
        return _merge_results(self.values, self.levels, self.serial.fresh)

    def route_suffix_inputs(self) -> None:
        """Reserve and feed the suffix literal lanes, then park unused ports."""
        p, n, k = self.p, self.n, self.k
        layout, plan, anchors = self.layout, self.plan, self.anchors
        # The leaf offset puts every incoming suffix lane above the atom's
        # y=40 input bank. Without it dense n=8 routes cross another atom's
        # lower gate port at (1008,730); all eight-input controls now execute.
        for depth in range(p, n):
            for prefix, (x, y) in self.sites.items():
                below = 8 * (depth - _depth(prefix))
                point = (
                    x - 6 - below,
                    y - 6 - below + (8 * k if _depth(prefix) == p else 0),
                )
                anchors[depth, "1", prefix] = point
                layout.reserve(point, plan.literal(depth, "1"))
            row = 8 * self.order[depth]
            signal = plan.literal(depth, "1")
            layout.input_port(row, 2, signal)
            layout.route((2, row), anchors[depth, "1", 1], signal, "across")
        for index in range(self.ports):
            if index not in self.order:
                signal = self.serial.fresh()
                layout.input_port(8 * index, 2, signal)

    def route_wires(self) -> None:
        """Route prefix literals, suffix fan-out, atom feeds and footer inputs."""
        p, n = self.p, self.n
        layout, plan, anchors = self.layout, self.plan, self.anchors
        _h_route_literals(
            layout,
            plan,
            {key: point for key, point in anchors.items() if key[0] < p},
            input_order=self.order[:p],
        )
        for depth in range(p, n):
            signal = plan.literal(depth, "1")
            for prefix in self.sites:
                point = anchors[depth, "1", prefix]
                layout.junction(*point, signal)
                if prefix != 1:
                    layout.route(anchors[depth, "1", prefix // 2], point, signal)
        for depth, prefix, target in self.feeds:
            layout.route(anchors[depth, "1", prefix], target, plan.literal(depth, "1"))
        for source, target, signal, shape in self.atom_routes:
            layout.route(source, target, signal, shape)

    def finish(self, result_gates: set[int]) -> _Layout:
        result_signal = self.values[1]
        if result_signal is None:
            raise ValueError("cofactor pools need a selected row")
        plan = replace(
            self.plan,
            results=self.values,
            result_gates=result_gates,
            result_signal=result_signal,
        )
        _h_route_results(self.layout, plan, leaf_points=self.points)
        return self.layout.seal()


def _pool_layout(
    table: str,
    k: int,
    *,
    input_order: list[int] | None,
    port_inputs: int | None,
) -> _Layout:
    from . import _circuit_diagram_model

    n, order, ports = _pool_inputs(table, input_order, port_inputs)
    if n <= k:
        return _circuit_diagram_model(table, None, input_order=order, port_inputs=ports)
    build = _PoolBuild(table, k, order, ports, _pool_atoms(table, k, n - k))
    build.place_leaves()
    result_gates = build.merge_results()
    build.route_suffix_inputs()
    build.route_wires()
    return build.finish(result_gates)
