r"""Boolean-function generator for Circuit Diagram.

Circuit Diagram is a language for drawing boolean circuits, so a truth
table is its native idiom.  The generated ASCII gate network reads one bit
per input wire, folds adjacent cofactors through muxes, and prints through
``:``.

Layout
------

The geometry controls the program -- the language has no statements to
sequence, only cells that have to line up -- so the program is built as a
*model* of wire segments first and rendered to characters afterwards,
rather than painted cell by cell in draw order.

Every signal owns a vertical **bus column**; every gate owns a three-row
**band**.  A gate at ``(c, r)`` reads its two inputs from ``.`` cells at
``(c - 1, r - 1)`` and ``(c - 1, r + 1)`` and drives a ``.`` at
``(c + 1, r)`` -- the spec's own AND sample -- so each gate is fed by two
horizontal segments running from a bus column to its left-hand junctions,
and its result leaves along a fresh bus.

**Crossings are the point, not a hazard.**  Shared selectors make the
network non-planar, so wires must cross.  The spec's crossover figure puts ``-=-``
between two horizontal wires and ``|`` above and below, with "opposite
wires are connected", so one ``=`` carries a horizontal and a vertical wire
past each other independently.  The renderer therefore derives each cell
from what covers it: a horizontal segment alone is ``-``, a vertical
segment alone is ``|``, both together is ``=``, and an endpoint is ``.``.
The wiki's own prime tester is drawn the same way.

What the layout must still guarantee is that nothing *merges* by accident.
A ``.`` connects to all eight of its neighbours, so two junctions belonging
to different signals that come to rest diagonally adjacent silently become
one wiring.  The renderer checks that mechanically -- along with two
segments of different signals sharing a cell in the same direction -- and
raises rather than emitting a circuit that is wrong in a way only the truth
table would reveal.

Construction
------------

``truth_table`` is a binary string of length ``2**n`` indexed by the inputs
most significant first, matching the other generators in this package.

* ``n`` input bits arrive on ``n`` separate lines, each a ``-`` at the start
  of its own line, which is what the spec makes an input port.  Keeping the
  bits on separate lines rather than in one ``-n-`` multi-wire keeps the
  network scalar: the multi-wire path would need a ``<`` splitter tree to
  get back to individual rails, and the splitter's rounding rule makes that
  layout depend on ``n`` in a way this one does not.
* each input and any complement the mux rules need is built once and shared;
* a left-to-right binary-carry fold combines adjacent cofactors.  Equal
  cofactors share one signal, ``0/1`` is the selector itself, and the other
  cases use a fixed one- or three-gate mux rule;
* at most one unfinished signal per input level is live.  The fold performs
  one pass over the table and emits fewer than three gates per entry; it is
  neither a circuit search nor a graph traversal.
* through seven inputs the fold is built for up to four *selector orders*
  and the shortest drawing ships.  The rails keep their rows and read order;
  only which rail each Shannon level selects moves, which is the table's
  inputs renamed (:func:`_selector_orders`).

**Constant tables need no muxes.**  Both are a single self-fed ``x`` or ``X``
gate, the shape the wiki's own constant-output circuit uses.

**Every wiring is driven exactly once.**  A ``:`` prints in *every*
generation its wire carries a value, and a wiring driven twice takes the
XOR of its drivers, so a second driver would corrupt both the value and the
output length.  Each bus here is written by exactly one gate (or one input
port) and only ever read after that, which is why the tests can assert that
a run prints exactly one character.
"""

from dataclasses import dataclass
from typing import Literal, cast

from esolangs.tools.circuit_diagram.layout import _HOLD, _Layout, _RoutingLayout, _Shape
from esolangs.tools.helpers import (
    _greedy_input_order,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    narrowest_grid,
    permute_truth_table,
    read_at,
)

# Gate characters used by muxes and the two self-fed constant forms.
_GateGlyph = Literal["a", "o", "x", "X"]
_ConstGlyph = Literal["x", "X"]

__all__ = ["circuit_diagram"]

# Spacing.  Buses are two columns apart and gate bands two rows apart, so
# that no two junctions of different signals ever land within one cell of
# each other (see the module docstring's note on the eight-way ``.``).
_COL_STEP = 2
_ROW_STEP = 2

# The flat route's widest arity: from eight inputs an unconstrained build is
# the H-layout, which is not reordered.  Selector orders are only chosen up
# to here -- a width-bound build past it keeps the identity -- so their
# scoring is bounded work and the wide route's generation stays O(T).
_REORDER_MAX_ARITY = 7

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


class _Builder:
    """Allocates buses and gate bands, and records their wiring.

    A *bus* is a vertical column carrying one signal, written once and read
    by any number of gates.  A gate occupies a three-row band and leaves its
    result on a fresh bus.
    """

    def __init__(self, *, narrow: bool = False) -> None:
        """Start an empty build."""
        # Input junction, gate, output junction, then one clear column:
        # different signals' junctions must remain two cells apart.
        self.gate_stride = 4 if narrow else 3 * _COL_STEP
        self.layout = _Layout()
        self.next_column = 1
        self.next_row = 0
        self.next_signal = 0
        # signal id -> (column, topmost row the bus has reached)
        self.buses: dict[int, tuple[int, int]] = {}
        # Gate column groups that may be handed out again, and the group each
        # recyclable signal was cut from.  Only a *gate's* output is ever
        # entered here: selector rails are shared, while every mux result is
        # read once by the carry that consumes it and then dies.
        self.free_strides: list[int] = []
        self.stride_of: dict[int, int] = {}
        # Set once a width is asked for: the column a new band starts at,
        # and the width the bands have to stay inside.  ``live`` is every
        # intermediate signal not yet read into the gate that consumes it,
        # in the order they were made -- what a band has to carry.  Rails
        # and complements are not in it: they are read by everything, sit
        # left of ``band_start``, and are never reclaimed.
        self.limit: int | None = None
        self.next_limit: int | None = None
        self.band_start = 0
        self.live: list[int] = []

    def _new_signal(self) -> int:
        """Return a fresh signal id."""
        signal = self.next_signal
        self.next_signal += 1
        return signal

    def _new_column(self) -> int:
        """Return a fresh bus column, right of every bus column in use.

        Input rails only.  A rail is read by every mux level that selects it,
        so it is live for the whole drawing and its column is never given
        back; :func:`_gate_columns` is where the recycling happens.

        A gate is drawn one column left of the bus it drives and reads its
        inputs one column left of *that*, so the columns a gate occupies
        must be clear of every existing bus: a bus running vertically
        through the gate's input junction would carry the gate's own output
        back to its input, making one wiring of both -- which the
        interpreter rejects, since a wiring may not touch both.
        """
        column = self.next_column
        self.next_column += _COL_STEP
        return column

    def _gate_columns(self, after: int = -1) -> tuple[int, int]:
        """Reserve the columns one gate needs: its inputs, glyph, and output.

        Three consecutive columns are taken at once -- the input junctions,
        the gate itself, and the bus it drives -- so no earlier bus can run
        down through any of them.
        """
        # A dead group is reused rather than a fresh one taken.  Two things
        # make that safe.
        #
        # Rows: the drawing only ever moves *down*.  ``_new_band`` hands out
        # increasing rows and ``_tap`` only extends a bus downward, so a
        # recycled group's old wiring ends at the row of the gate that read
        # it last, and everything drawn into it afterwards starts a band
        # below that.
        #
        # Columns: the signal flows left to right, and a gate must sit to the
        # *right* of every bus it reads.  ``_tap`` runs the bus along the
        # gate's row to the input junction one column left of the glyph, so a
        # group recycled to the left of a source would have that run cross
        # the gate's own glyph cell -- which is how this first went wrong,
        # caught by :class:`_Layout` refusing to draw it.  ``after`` is the
        # rightmost bus the gate will read, and only a group past it will do.
        usable = [group for group in self.free_strides if group + _COL_STEP > after]
        if usable:
            first = min(usable)
            self.free_strides.remove(first)
        else:
            first = self.next_column
            self.next_column += self.gate_stride
        return first, first + _COL_STEP

    def _band(self) -> None:
        """Start a fresh band of columns, carrying the live signals back left.

        Gates march right because one has to sit right of every bus it
        reads, so a column group freed behind the drawing can never be
        handed out again -- which is what makes the width grow with the
        network's depth.  A band breaks that: every signal still live is
        *moved* to a column near the left, and the columns behind it all
        become free again.

        Moving a bus needs no new primitive.  :meth:`_tap` already runs a
        bus down to a row and then along it to a column, in either
        direction, and the whole path carries the one signal -- so running
        it leftwards and then continuing the bus from there is the same
        wiring with the same single driver.  What it crosses on the way is
        every rail and complement, which is a crossing and what ``=`` is
        for.

        Each carried signal takes a row of its own.  Two horizontal runs of
        different signals on one row would collide, and :class:`_Layout`
        says so rather than drawing it.

        Resetting the column counter is safe for the reason group reuse is:
        the drawing only ever moves down, so a column re-used in this band
        is entered below everything the last band left in it.
        """
        for offset, signal in enumerate(self.live):
            column = self.band_start + offset * _COL_STEP
            row = self._new_band()
            self._tap(signal, column, row)
            self.buses[signal] = (column, row)
        # A carried signal sits in a column of its own rather than a gate's
        # group, so releasing it gives nothing back.  It stays in ``live``,
        # though: a later band has to carry it again, and forgetting one is
        # how this first went wrong -- the next band handed its column to
        # another signal while its bus was still running down it, which
        # :class:`_Layout` refused to draw.
        self.stride_of.clear()
        self.free_strides.clear()
        self.next_column = self.band_start + len(self.live) * _COL_STEP

    def _room(self, after: int) -> bool:
        """Whether a gate reading up to ``after`` fits without a new band."""
        if self.limit is None:
            return True
        if any(group + _COL_STEP > after for group in self.free_strides):
            return True
        boundary = self.next_column + self.gate_stride
        if boundary > self.limit:
            self.next_limit = (
                boundary if self.next_limit is None else min(self.next_limit, boundary)
            )
            return False
        return True

    def _release(self, signal: int) -> None:
        """Give back ``signal``'s column group, if it owns one to give.

        Called once the signal has been read into the gate that consumes
        it.  A rail or a complement is not in :attr:`stride_of` at all and
        so is never released; a gate output is removed as it is released, so
        a second call cannot hand the same group out twice.
        """
        stride = self.stride_of.pop(signal, None)
        if stride is not None:
            self.free_strides.append(stride)
        if signal in self.live:
            self.live.remove(signal)

    def _new_band(self) -> int:
        """Return the centre row of a fresh three-row gate band."""
        row = self.next_row + 1
        self.next_row += 2 + _ROW_STEP
        return row

    def input_bus(self) -> int:
        """Draw one input line and return the signal its bit arrives on.

        The spec makes a ``-`` at the start of a line an input port, so each
        input owns a row of its own; the rows are taken in order, which is
        the order the interpreter reads the bits in.

        One bus column is enough.  An input port draws only the ``-`` and
        the junction its bus starts from -- there is no gate glyph, nothing
        to its left to read, and no separate output column -- so reserving a
        whole gate's three columns, as this once did, left two empty
        columns per input that every later wire then had to run across.
        """
        signal = self._new_signal()
        column = self._new_column()
        row = self.next_row
        self.next_row += _ROW_STEP

        self.layout.glyph(0, row, "-")
        self.layout.run_horizontal(0, column, row, signal)
        self.layout.junction(column, row, signal)
        self.buses[signal] = (column, row)
        return signal

    def invert(self, source: int) -> int:
        """Return a signal carrying ``~source``, computed once.

        Bands the same way :meth:`gate` does.  The complements are built
        before a limit is set, so this only ever fires for the ``~`` that
        inverts a dense table's result -- which is one gate past the whole
        network and was exactly the one that ran over the width.
        """
        if not self._room(self.buses[source][0]):
            self._band()
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        # ``~`` reads the cell level with it, so the tap has to end on the
        # junction immediately to its left rather than short of it.
        self._tap(source, column - 1, row)
        self.layout.glyph(column, row, "~")

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        return signal

    def gate(self, kind: _GateGlyph, left: int, right: int) -> int:
        """Place a two-input ``kind`` gate and return its output signal.

        The group is taken before the inputs are read and the inputs are
        released after, so a gate can never be handed the very group it is
        about to read out of.

        When a width was asked for and this gate would take the drawing past
        it, :meth:`_band` carries the live signals back to the left first --
        so the check happens here, before the group is chosen, and the
        inputs' columns are re-read afterwards because the band has moved
        them.
        """
        if not self._room(max(self.buses[left][0], self.buses[right][0])):
            self._band()
        first, column = self._gate_columns(
            max(self.buses[left][0], self.buses[right][0])
        )
        row = self._new_band()

        self._feed(left, column - 1, row - 1)
        self._feed(right, column - 1, row + 1)
        self.layout.glyph(column, row, kind)

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        self.stride_of[signal] = first
        if self.limit is not None:
            self.live.append(signal)
        self._release(left)
        self._release(right)
        return signal

    def constant(self, source: int, kind: _ConstGlyph) -> int:
        """Return a constant signal, from one bus fed to both gate inputs.

        ``x`` of a value with itself is always 0 and ``X`` always 1, so a
        constant table needs no muxes.  Both of the gate's inputs come
        from the same bus, which the interpreter accepts because the wiki's
        own constant-output circuit is drawn that way.
        """
        _, column = self._gate_columns(self.buses[source][0])
        row = self._new_band()

        self._tap(source, column - 1, row - 1)
        self.layout.run_vertical(column - 1, row - 1, row + 1, source)
        self.layout.junction(column - 1, row + 1, source)
        self.layout.glyph(column, row, kind)

        signal = self._new_signal()
        self.layout.junction(column + 1, row, signal)
        self.buses[signal] = (column + 1, row)
        return signal

    def output(self, source: int) -> None:
        """Draw the ``:`` that prints ``source``'s value.

        ``:`` reads only a ``-`` directly to its left, so the signal is
        handed one cell along from the junction its bus already ends on.

        No band or gate columns are reserved for it.  ``:`` is two glyphs
        with nothing above, below, or left of them to keep clear, and the
        bus it reads is the last one built -- so its own row is free to the
        right by construction.  Taking a fresh band instead, as this once
        did, put the output three rows below the gate that drives it and ran
        the bus down to meet it, which is most of the staircase a small
        circuit used to end on.
        """
        column, row = self.buses[source]
        self.layout.glyph(column + 1, row, "-")
        self.layout.glyph(column + 2, row, ":")

    def _tap(self, signal: int, x: int, y: int) -> None:
        """Extend ``signal``'s bus down to row ``y`` and end it at ``(x, y)``.

        The bus runs down its own column to the target row, then along that
        row to ``x``.  Both legs carry the same signal as the bus, so the
        whole path is one wiring -- a tap reads the bus, it does not drive
        it.
        """
        column, reached = self.buses[signal]
        # Each leg is skipped when the bus already sits on the tap's row or
        # column, which the layout never produces: rows advance for every
        # gate and a bus column is its own, so a tap is always at least one
        # cell away on both axes.  Both tests stay, since a layout change
        # that did reach a tap head-on would otherwise draw a zero-length
        # run and a junction on top of the bus.
        if y != reached:  # pragma: no branch - a tap is never on the bus row
            self.layout.run_vertical(column, reached, y, signal)
            self.layout.junction(column, y, signal)
            self.buses[signal] = (column, y)
        if x != column:  # pragma: no branch - nor in the bus column
            self.layout.run_horizontal(column, x, y, signal)
            self.layout.junction(x, y, signal)

    def _feed(self, signal: int, x: int, y: int) -> None:
        """Bring ``signal`` to a gate's input junction at ``(x, y)``."""
        self._tap(signal, x, y)


_Value = int | Literal["0", "1"]


def _mux(
    builder: _Builder, selectors: list[int | None], zero: _Value, one: _Value
) -> _Value:
    """Return ``zero`` or ``one`` according to ``selector``.

    ``(~selector AND zero) OR (selector AND one)`` is a three-gate mux.
    The caller shares each selector's complement across its whole level.
    """
    if zero == one:
        return zero
    selector = selectors[0]
    if selector is None:  # pragma: no cover - every selector has a plain rail
        raise AssertionError("selector has no plain rail")
    if zero == "0" and one == "1":
        return selector
    # The plain rail's two rules come first: a level that only ever takes
    # them has no complement to read (see :func:`_complemented_levels`).
    if zero == "0":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", selector, one)
    if one == "1":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", selector, zero)
    negated = selectors[1]
    if negated is None:  # pragma: no cover - built before the fold
        raise AssertionError("selector has no complemented rail")
    if zero == "1" and one == "0":
        return negated
    if one == "0":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", negated, zero)
    if zero == "1":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", negated, one)
    off = builder.gate("a", negated, zero)
    on = builder.gate("a", selector, one)
    return builder.gate("o", off, on)


def _shannon_fold(
    builder: _Builder,
    selectors: list[list[int | None]],
    truth_table: str,
) -> _Value:
    """Fold the table in one pass, keeping one partial signal per level."""
    stack: list[tuple[_Value, int]] = []
    n = len(selectors)
    for bit in truth_table:
        signal: _Value = "1" if bit == "1" else "0"
        level = 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            signal = _mux(builder, selectors[n - 1 - level], zero, signal)
            level += 1
        stack.append((signal, level))
    [(result, level)] = stack
    if level != n:  # pragma: no cover - validation guarantees 2**n entries
        raise AssertionError("incomplete Shannon fold")
    return result


def _complemented_levels(truth_table: str, n: int) -> set[int]:
    """Return selector levels whose direct mux rule needs ``~selector``.

    Identities have to compare the way :func:`_mux`'s signals do.  Only a
    constant or a level's own rail is ever the same signal twice; every gate
    output is fresh, so two cofactors that compute the same function from
    different gates are *unequal* to the fold and take a real mux.  Hashing
    them together, as this once did, skipped the complement that mux reads:
    twenty four-input tables, ``0000111100010001`` first, raised instead of
    drawing.
    """
    stack: list[tuple[int, int]] = []
    rails: dict[tuple[int, int, int], int] = {}
    needed: set[int] = set()
    next_identity = 2
    for bit in truth_table:
        identity, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            if zero != identity:
                # ``0/x`` is ``selector AND x`` and ``x/1`` is ``selector OR
                # x``: only the plain rail is read, as for ``0/1`` itself.
                if zero != 0 and identity != 1:
                    needed.add(n - 1 - level)
                key = (level, zero, identity)
                if key in rails:
                    identity = rails[key]
                else:
                    if (zero, identity) in ((0, 1), (1, 0)):
                        rails[key] = next_identity
                    identity = next_identity
                    next_identity += 1
            level += 1
        stack.append((identity, level))
    return needed


# A fold token that is a gate's output.  Unlike a constant or a rail it is
# never the same signal twice, so two of them always take a real mux.
_GATE = -1


def _mux_cost(zero: int, one: int) -> tuple[int, bool]:
    """Return what :func:`_mux` spends on a pair: gates, and whether ``~``."""
    if zero == one and zero != _GATE:
        return 0, False
    if (zero, one) == (0, 1):
        return 0, False
    if (zero, one) == (1, 0):
        return 0, True
    if zero == 0 or one == 1:
        return 1, False
    if zero == 1 or one == 0:
        return 1, True
    return 3, True


def _cheapest_selector_order(truth_table: str, n: int) -> tuple[int, ...]:
    """Pick each Shannon level's rail bottom-up by what its muxes cost.

    A level's cost is read straight off its pairs with :func:`_mux_cost`,
    one per gate plus one for a complement.  The pairs a level sees do not
    depend on the order *below* it -- a cofactor is a constant, a rail or a
    gate whichever way it was folded -- so the bottom level is chosen first,
    folded, and the next chosen over what is left.  Ties keep the identity's
    rail.  Each level scores every remaining input over the remaining
    table, so the whole choice is ``O(n * 2**n)``.
    """
    tokens = [int(bit) for bit in truth_table]
    remaining = list(range(n))
    bottom_up: list[int] = []
    while len(remaining) > 1:
        best_pos, best_cost = len(remaining) - 1, -1
        for pos in range(len(remaining) - 1, -1, -1):
            stride = 1 << (len(remaining) - 1 - pos)
            cost, complement = 0, False
            for block in range(0, len(tokens), 2 * stride):
                for x in range(block, block + stride):
                    gates, negated = _mux_cost(tokens[x], tokens[x + stride])
                    cost += gates
                    complement = complement or negated
            cost += complement
            if best_cost < 0 or cost < best_cost:
                best_pos, best_cost = pos, cost
        stride = 1 << (len(remaining) - 1 - best_pos)
        rail = remaining.pop(best_pos)
        folded = []
        for block in range(0, len(tokens), 2 * stride):
            for x in range(block, block + stride):
                zero, one = tokens[x], tokens[x + stride]
                if zero == one and zero != _GATE:
                    folded.append(zero)
                elif (zero, one) == (0, 1):
                    folded.append(2 + 2 * rail)
                elif (zero, one) == (1, 0):
                    folded.append(3 + 2 * rail)
                else:
                    folded.append(_GATE)
        tokens = folded
        bottom_up.append(rail)
    return tuple(remaining + bottom_up[::-1])


def _selector_orders(
    truth_table: str, *, compact: bool = False
) -> list[tuple[int, ...] | None]:
    """Return named selector orders, identity first.

    Compact builds keep identity, mux-cost greedy and reverse. Width requests
    also try the constant-cofactor greedy order. Rails remain in input order.
    """
    n = len(truth_table).bit_length() - 1
    if n > _REORDER_MAX_ARITY:
        return [None]
    used = essential_inputs(truth_table, n) or [0]
    table = read_at(truth_table, used, n)
    identity = tuple(range(len(used)))
    orders: list[tuple[int, ...] | None] = [None]
    for order in (
        identity if compact else _greedy_input_order(table, len(used)),
        _cheapest_selector_order(table, len(used)),
        identity[::-1],
    ):
        if order != identity and order not in orders:
            orders.append(order)
    return orders


def _circuit_diagram_at(
    truth_table: str,
    limit: int | None,
    perm: tuple[int, ...] | None = None,
    *,
    _events: list[int] | None = None,
) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The table is folded bottom-up by Shannon expansion.  Each unequal pair
    becomes a fixed three-gate mux, while equal pairs share their signal.
    There are fewer pairs than table entries, so construction uses O(T)
    gates and no tree traversal or circuit search.

    The drawing's *width* is gate column groups, and a group is reused once
    the bus it drives is dead.  What makes so many die is the shape of the
    circuit rather than any analysis: only selector rails are read more than
    once, and each mux result is read once by the carry above it.  A gate
    must still sit right of every bus it reads,
    since the run feeding it travels along its row, so what is reused is the
    leftmost dead group past those buses.  Four inputs: 219 columns to 99.

    ``perm`` renames the essential inputs' levels: level ``k`` selects rail
    ``perm[k]``.  The input rows are drawn first and in input order either
    way.
    """
    _validate_truth_table(truth_table)

    builder = _Builder(narrow=limit is not None)
    n = len(truth_table).bit_length() - 1
    # Every input keeps its own ``-`` row -- the rows are the read order and
    # the interface -- but a table that ignores some of them is a smaller
    # table, and the cost here is entirely in the body.  The fold is built
    # over the essential inputs' rails only, and an
    # ignored rail simply drives nothing, exactly as every rail but the
    # first already does for a constant table.
    used = essential_inputs(truth_table, n) or [0]
    table = truth_table if len(used) == n else read_at(truth_table, used, n)
    rails = [builder.input_bus() for _ in range(n)]
    if len(used) < n:
        rails = [rails[i] for i in used]
        truth_table = table
        n = len(used)
    if perm is not None:
        truth_table = permute_truth_table(truth_table, perm)
        rails = [rails[i] for i in perm]

    complemented = _complemented_levels(truth_table, n)
    selectors: list[list[int | None]] = [
        [rail, builder.invert(rail) if level in complemented else None]
        for level, rail in enumerate(rails)
    ]
    builder.band_start = builder.next_column
    builder.limit = limit

    result = _shannon_fold(builder, selectors, truth_table)
    if result == "0":
        result = builder.constant(rails[0], "x")
    elif result == "1":
        result = builder.constant(rails[0], "X")
    builder.output(result)
    if _events is not None and builder.next_limit is not None:
        _events.append(builder.next_limit)
    return builder.layout.render()


def _affine_circuit(
    table: str, width: int, *, _events: list[int] | None = None
) -> str | None:
    from esolangs.tools.circuit_diagram.balance import affine_circuit

    return affine_circuit(table, width, _events=_events)


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    See :func:`_circuit_diagram_at` for the construction.  ``width`` asks
    for a column count: the drawing is built once without one, and again
    inside the width if that came out too wide.

    Below eight inputs the shortest named selector order is kept. Compact
    builds use three orders; width requests keep all four. Retiring the
    constant-cofactor greedy choice adds 3.29% to the three-input total
    and 1.62% to the seeded five-input sample.

    From eight inputs an unconstrained build uses the H-layout instead
    (:func:`_h_term_layout`).  That is a growth choice, not a size one: the
    flat drawing's width grows with the depth, so its area is Theta(T log
    T) -- 2.2x to 2.8x per added input, measured n=6..11 -- while the
    H-layout is O(T) with a constant about twelve times larger (n=8 dense:
    145 KB flat, 1.78 MB H).  Eight is where the registry's linearity
    contract starts measuring, and lowering it would only cost size.

    What a width buys is *banding*.  Gates march right because one has to
    sit right of every bus it reads, so a column group freed behind the
    drawing can never be handed out again -- and the width grows with the
    network's depth.  A band carries every live signal back to a column near
    the left and frees everything behind it, which :meth:`_Builder._band`
    does with no new primitive: a tap already runs a bus down and then along
    a row in either direction.

    Below that floor, affine tables use native XOR/XNOR chains.
    A mux layout's floor is what a band cannot reclaim -- the rails and complements,
    which their mux levels share and which therefore stay live for the whole
    drawing -- plus the carried signals and one gate group.  That is about
    ``8 * n`` columns, so the floor grows with the inputs rather than with
    the table.
    """
    _validate_truth_table(truth_table)
    inputs = len(truth_table).bit_length() - 1
    if width is None and inputs >= 8 and "1" in truth_table:
        return _h_term_layout(truth_table).render()
    # The shortest drawing over the candidate selector orders; ``min`` keeps
    # the first on a tie, so the identity only ever gives way to a win.
    flat, order = min(
        (
            (_circuit_diagram_at(truth_table, None, order), order)
            for order in _selector_orders(truth_table, compact=width is None)
        ),
        key=lambda built: len(built[0]),
    )
    if width is None or grid_width(flat) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width, order)
    if grid_width(banded) <= width:
        return banded
    # The output dash and colon extend beyond the final gate group.
    banded = _circuit_diagram_at(truth_table, max(1, width - 2), order)
    affine = _affine_circuit(truth_table, width)
    candidates = (flat, banded) if affine is None else (flat, banded, affine)
    return narrowest_grid(*candidates)
