"""The H-layout: an O(T)-area Circuit Diagram drawing for eight inputs and up.

:func:`circuit_diagram` switches to it from eight inputs when no width is
asked for.  That is a growth choice, not a size one: the flat drawing's
width grows with the depth, so its area is Theta(T log T) -- 2.2x to 2.8x
per added input, measured n=6..11 -- while the H-layout is O(T) with a
constant about twelve times larger (n=8 dense: 145 KB flat, 1.78 MB H).
Eight is where the registry's linearity contract starts measuring, and
lowering it would only cost size.
"""

from dataclasses import dataclass
from typing import cast

from esolangs.tools.circuit_diagram.layout import _HOLD, _Layout, _RoutingLayout, _Shape

# H-layout lattice.  Every site sits on a multiple of eight in both axes, and
# each wire class owns residues no other class uses, so wires of different
# classes only ever cross and their corners never touch:
#
#   columns  0 gate  1 output  7 inputs  | 2, 6 literals | 3..5 results
#   rows     0 gate  7, 1 inputs         | 3, 2 literals | 4..6 results
#
# A literal's anchor at a site is offset by its distance below that site's
# level, so within one level's band the anchors of every literal that
# reaches it are distinct; the band (``16 * remaining + 16`` wide) has
# room for all ``2 * remaining`` of them.
_LATTICE = 8
_LITERAL_TRACK_X = {"0": 2, "1": 6}
_LITERAL_TRACK_Y = {"0": 5, "1": 6}
_RESULT_TRACK = (4, 3)


@dataclass(frozen=True)
class _Block:
    """Square reserved by one recursive H-layout subtree."""

    x: int
    y: int
    size: int

    def quadrants(self, child_size: int) -> tuple["_Block", ...]:
        """Return four corner children around this block's centre cross."""
        far = self.size - child_size
        return (
            _Block(self.x, self.y, child_size),
            _Block(self.x + far, self.y, child_size),
            _Block(self.x, self.y + far, child_size),
            _Block(self.x + far, self.y + far, child_size),
        )


def _h_size(inputs: int) -> int:
    """Return a side length for a two-level-at-a-time H-layout.

    A level's band between its four child blocks is sized from the
    lattice: ``8 * remaining`` cells of literal track to the left of the
    child sites, the same again to the parent's, and a lattice step for the
    parent's own cells.  A leaf block is two lattice steps.
    """
    if inputs <= 1:
        return 2 * _LATTICE
    child = _h_size(inputs - 2)
    return 2 * child + 2 * _LATTICE * inputs + 2 * _LATTICE


def _h_blocks(inputs: int) -> dict[int, _Block]:
    """Assign every two-level heap node a non-overlapping H-layout square."""
    root = _Block(0, 0, _h_size(inputs))
    blocks = {1: root}

    def descend(prefix: int, remaining: int, block: _Block) -> None:
        if remaining < 2:
            return
        child_size = _h_size(remaining - 2)
        for bits, child in zip(range(4), block.quadrants(child_size), strict=True):
            blocks[4 * prefix + bits] = child
            descend(4 * prefix + bits, remaining - 2, child)

    descend(1, inputs, root)
    return blocks


def _h_sites(inputs: int) -> dict[int, tuple[int, int]]:
    """Return the centre-cross site of every non-leaf Shannon node."""
    blocks = _h_blocks(inputs)
    sites: dict[int, tuple[int, int]] = {}
    for prefix, block in blocks.items():
        remaining = inputs - (prefix.bit_length() - 1)
        if remaining == 0:
            continue
        if remaining == 1:
            sites[prefix] = (block.x + block.size // 2, block.y + block.size // 2)
            continue
        child = _h_size(remaining - 2)
        left = block.x + child
        top = block.y + child
        # The two one-bit children stack at the band's left, each with
        # ``8 * remaining`` cells of literal track above and to its left; the
        # parent sits between them with the same track to *its* left.
        track = _LATTICE * remaining
        sites[prefix] = (left + 2 * track + _LATTICE, top + track + _LATTICE)
        sites[2 * prefix] = (left + track, top + track)
        sites[2 * prefix + 1] = (left + track, top + 2 * track + _LATTICE)
    return sites


def _h_minterm_sites(inputs: int) -> dict[int, tuple[int, int]]:
    """Return H-layout sites for every heap node, including minterm leaves."""
    sites = _h_sites(inputs)
    blocks = _h_blocks(inputs)
    if inputs % 2 == 0:
        for prefix, block in blocks.items():
            if (prefix.bit_length() - 1) == inputs:
                sites[prefix] = (
                    block.x + block.size // 2,
                    block.y + block.size // 2,
                )
    else:
        for prefix, block in blocks.items():
            if (prefix.bit_length() - 1) != inputs - 1:
                continue
            middle_x = block.x + block.size // 2
            middle_y = block.y + block.size // 2
            sites[2 * prefix] = (middle_x - 8, middle_y + 8)
            sites[2 * prefix + 1] = (middle_x + 8, middle_y + 8)
    return sites


@dataclass(frozen=True)
class _HTermPlan:
    inputs: int
    sites: dict[int, tuple[int, int]]
    signals: dict[int, int]
    literal_start: int
    results: dict[int, int | None]
    result_gates: set[int]
    result_signal: int
    levels: list[list[int]]

    def literal(self, depth: int, bit: str) -> int:
        return self.literal_start + 2 * depth + int(bit)

    def result_anchor(self, prefix: int) -> tuple[int, int]:
        x, y = self.sites[prefix]
        return x + _RESULT_TRACK[0], y - _RESULT_TRACK[1]


def _h_term_plan(table: str) -> _HTermPlan:
    """Assign minterm and result signals to fixed H-layout sites."""
    truth_table = table
    inputs = len(table).bit_length() - 1
    margin = _LATTICE * inputs + _LATTICE  # the root anchors and input feeders
    sites = {
        prefix: (x + margin, y + margin)
        for prefix, (x, y) in _h_minterm_sites(inputs).items()
    }
    levels: list[list[int]] = [[] for _ in range(inputs + 1)]
    for node in sites:
        levels[node.bit_length() - 1].append(node)
    signals = {
        prefix: index
        for index, prefix in enumerate(
            prefix for prefix in sites if (prefix.bit_length() - 1) >= 2
        )
    }
    literal_start = len(signals)

    next_signal = literal_start + 2 * inputs
    results: dict[int, int | None] = {
        prefix: signals[prefix] if truth_table[prefix - (1 << inputs)] == "1" else None
        for prefix in sites
        if (prefix.bit_length() - 1) == inputs
    }
    result_gates: set[int] = set()
    for depth in range(inputs - 1, -1, -1):
        for prefix in levels[depth]:
            zero = results.get(2 * prefix)
            one = results.get(2 * prefix + 1)
            if zero is not None and one is not None:
                results[prefix] = next_signal
                next_signal += 1
                result_gates.add(prefix)
            else:
                results[prefix] = zero if zero is not None else one
    result_signal = results[1]
    if result_signal is None:  # handled by the scalar constant construction
        raise AssertionError("the H layout needs at least one selected minterm")

    return _HTermPlan(
        inputs,
        sites,
        signals,
        literal_start,
        results,
        result_gates,
        result_signal,
        levels,
    )


def _h_reserve_terms(
    layout: _RoutingLayout, plan: _HTermPlan
) -> dict[tuple[int, str, int], tuple[int, int]]:
    """Reserve gate ports, result holds, and table-independent literal anchors."""
    inputs, sites, signals = plan.inputs, plan.sites, plan.signals
    literal, result_anchor = plan.literal, plan.result_anchor
    for prefix, (x, y) in sites.items():
        if (prefix.bit_length() - 1) >= 2:
            layout.glyph(x, y, "a")
        if prefix != 1:
            signal = (
                literal(0, str(prefix & 1))
                if (prefix.bit_length() - 1) == 1
                else signals[prefix]
            )
            layout.reserve((x + 1, y), signal)
        if (prefix.bit_length() - 1) >= 2:
            parent = prefix // 2
            layout.reserve(
                (x - 1, y - 1),
                (
                    literal(0, str(parent & 1))
                    if (parent.bit_length() - 1) == 1
                    else signals[parent]
                ),
            )
            layout.reserve(
                (x - 1, y + 1), literal((prefix.bit_length() - 1) - 1, str(prefix & 1))
            )

    # Every result anchor is kept clear whether or not this table uses it,
    # so the literal and selector trees are routed on a canvas that does
    # not depend on the table; the holds are released before the results
    # are routed.  A route may cross a held cell's neighbourhood but may
    # not corner there (see :meth:`_RoutingLayout._route_is_free`).
    for prefix in sites:
        if (prefix.bit_length() - 1) == inputs:
            continue
        x, y = result_anchor(prefix)
        for cell in ((x, y), (x + 1, y), (x - 1, y - 1), (x - 1, y + 1)):
            layout.reserve(cell, _HOLD)
    # Depth buckets visit 4*T - 2*inputs - 4 anchors, not all sites per input.
    literal_anchors: dict[tuple[int, str, int], tuple[int, int]] = {}
    for depth in range(inputs):
        for bit in "01":
            for level in range(depth + 1):
                for prefix in plan.levels[level]:
                    x, y = sites[prefix]
                    below = _LATTICE * (depth - (prefix.bit_length() - 1))
                    point = (
                        x - _LITERAL_TRACK_X[bit] - below,
                        y - _LITERAL_TRACK_Y[bit] - below,
                    )
                    literal_anchors[(depth, bit, prefix)] = point
                    layout.reserve(point, literal(depth, bit))
                    if prefix == 1:
                        layout.junction(*point, literal(depth, bit))
    return literal_anchors


def _h_route_literals(
    layout: _RoutingLayout,
    plan: _HTermPlan,
    literal_anchors: dict[tuple[int, str, int], tuple[int, int]],
) -> None:
    """Route input feeders, minterm prefixes, and literal fanout."""
    inputs, sites, signals, literal = (
        plan.inputs,
        plan.sites,
        plan.signals,
        plan.literal,
    )
    input_starts: dict[tuple[int, str], tuple[int, int]] = {}
    for depth in range(inputs):
        row = 8 * depth
        plain = literal(depth, "1")
        negated = literal(depth, "0")
        layout.glyph(0, row, "-")
        layout.junction(2, row, plain)
        layout.run_horizontal(0, 2, row, plain)
        layout.junction(2, row + 2, plain)
        layout.junction(3, row + 2, plain)
        layout.run_vertical(2, row, row + 2, plain)
        layout.run_horizontal(2, 3, row + 2, plain)
        layout.glyph(4, row + 2, "~")
        layout.junction(5, row + 2, negated)
        input_starts[(depth, "1")] = (2, row)
        input_starts[(depth, "0")] = (5, row + 2)
    for depth in range(inputs):
        for bit in "01":
            layout.route(
                input_starts[(depth, bit)],
                literal_anchors[(depth, bit, 1)],
                literal(depth, bit),
                "across",
            )
    for (depth, bit, prefix), point in literal_anchors.items():
        if prefix != 1:
            layout.junction(*point, literal(depth, bit))
    for prefix, (x, y) in sites.items():
        if prefix == 1:
            continue
        signal = (
            literal(0, str(prefix & 1))
            if (prefix.bit_length() - 1) == 1
            else signals[prefix]
        )
        source = (x + 1, y)
        layout.junction(*source, signal)
        for bit in "01":
            child = 2 * prefix + int(bit)
            if child not in sites:
                continue
            child_x, child_y = sites[child]
            target = (child_x - 1, child_y - 1)
            layout.route(source, target, signal)
    for depth in range(inputs):
        for bit in "01":
            signal = literal(depth, bit)
            frontier = [1]
            for level in range(depth + 1):
                following = []
                for prefix in frontier:
                    branches = bit if level == depth else "01"
                    source = literal_anchors[(depth, bit, prefix)]
                    for branch in branches:
                        child = 2 * prefix + int(branch)
                        shape: _Shape = "down"
                        if level == depth:
                            child_x, child_y = sites[child]
                            target = (
                                (child_x + 1, child_y)
                                if (child.bit_length() - 1) == 1
                                else (child_x - 1, child_y + 1)
                            )
                            # Side-by-side siblings put both last-level
                            # targets on one row, and the ``0`` wire corners
                            # on it first; the ``1`` wire passes underneath.
                            side_by_side = (
                                sites[2 * prefix][0] != sites[2 * prefix + 1][0]
                            )
                            if side_by_side and bit == "1":
                                shape = "under"
                        else:
                            target = literal_anchors[(depth, bit, child)]
                            following.append(child)
                        layout.route(source, target, signal, shape)
                frontier = following


def _h_route_results(layout: _RoutingLayout, plan: _HTermPlan) -> None:
    """Release result holds and join the selected minterms at the output."""
    inputs, sites, results = plan.inputs, plan.sites, plan.results
    result_gates, result_signal = plan.result_gates, plan.result_signal
    result_anchor = plan.result_anchor
    layout.release(_HOLD)
    result_points: dict[int, tuple[int, int]] = {}
    for prefix, result_value in results.items():
        if result_value is None:
            continue
        if (prefix.bit_length() - 1) == inputs:
            x, y = sites[prefix]
            result_points[prefix] = (x + 1, y)
        else:
            x, y = result_anchor(prefix)
            if prefix in result_gates:
                layout.glyph(x, y, "o")
                point = (x + 1, y)
            else:
                point = (x, y)
            result_points[prefix] = point
            layout.reserve(point, result_value)
    for prefix in result_gates:
        x, y = result_anchor(prefix)
        children = [
            2 * prefix + int(bit)
            for bit in "01"
            if results.get(2 * prefix + int(bit)) is not None
        ]
        for child, target in zip(
            children, ((x - 1, y - 1), (x - 1, y + 1)), strict=True
        ):
            layout.reserve(target, cast(int, results[child]))
    root = result_points[1]
    layout.junction(*root, result_signal)
    layout.glyph(root[0] + 1, root[1], "-")
    layout.glyph(root[0] + 2, root[1], ":")
    for depth in range(inputs):
        for prefix in plan.levels[depth]:
            if results[prefix] is None:
                continue
            children = [
                2 * prefix + int(bit)
                for bit in "01"
                if results.get(2 * prefix + int(bit)) is not None
            ]
            if prefix in result_gates:
                gate_x, gate_y = result_anchor(prefix)
                targets: tuple[tuple[int, int], ...] = (
                    (gate_x - 1, gate_y - 1),
                    (gate_x - 1, gate_y + 1),
                )
            else:
                targets = (result_points[prefix],)
            for child, target in zip(children, targets, strict=True):
                child_result = results[child]
                if child_result is None:  # pragma: no cover - filtered above
                    raise AssertionError("missing result signal")
                layout.route(result_points[child], target, child_result)


def _h_term_layout(table: str) -> "_Layout":
    """Route one truth table's parallel minterm tree through an H-layout.

    Every wire takes a lane fixed by its class (see ``_LATTICE``): the
    input feeders run across then down, and everything else runs down its
    own column then across, except the ``1`` literal's last hop to a gate
    whose sibling sits beside it, which passes under the target.  Nothing
    here searches; the collision check in :meth:`_RoutingLayout.route` is
    a guard on the lattice.
    """
    plan = _h_term_plan(table)
    layout = _RoutingLayout()
    literal_anchors = _h_reserve_terms(layout, plan)
    _h_route_literals(layout, plan, literal_anchors)
    _h_route_results(layout, plan)
    return layout
