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

**Constant tables need no muxes.**  Both are a single self-fed ``x`` or ``X``
gate, the shape the wiki's own constant-output circuit uses.

**Every wiring is driven exactly once.**  A ``:`` prints in *every*
generation its wire carries a value, and a wiring driven twice takes the
XOR of its drivers, so a second driver would corrupt both the value and the
output length.  Each bus here is written by exactly one gate (or one input
port) and only ever read after that, which is why the tests can assert that
a run prints exactly one character.
"""

from bisect import bisect_left, insort
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, cast

from esolangs.tools.helpers import (
    _validate_truth_table,
    essential_inputs,
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

# Owner of the H-layout's result-anchor holds while the trees are routed;
# no real signal, so every route treats a held cell as foreign.
_HOLD = -1

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

# The three wire shapes; see :meth:`_RoutingLayout.route`.
_Shape = Literal["down", "across", "under"]


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


def _h_blocks(inputs: int) -> dict[str, _Block]:
    """Assign every two-bit prefix a non-overlapping H-layout square."""
    root = _Block(0, 0, _h_size(inputs))
    blocks = {"": root}

    def descend(prefix: str, remaining: int, block: _Block) -> None:
        if remaining < 2:
            return
        child_size = _h_size(remaining - 2)
        for bits, child in zip(
            ("00", "01", "10", "11"), block.quadrants(child_size), strict=True
        ):
            blocks[prefix + bits] = child
            descend(prefix + bits, remaining - 2, child)

    descend("", inputs, root)
    return blocks


def _h_sites(inputs: int) -> dict[str, tuple[int, int]]:
    """Return the centre-cross site of every non-leaf Shannon node."""
    blocks = _h_blocks(inputs)
    sites: dict[str, tuple[int, int]] = {}
    for prefix, block in blocks.items():
        remaining = inputs - len(prefix)
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
        sites[prefix + "0"] = (left + track, top + track)
        sites[prefix + "1"] = (left + track, top + 2 * track + _LATTICE)
    return sites


def _h_minterm_sites(inputs: int) -> dict[str, tuple[int, int]]:
    """Return H-layout sites for every prefix, including minterm leaves."""
    sites = _h_sites(inputs)
    blocks = _h_blocks(inputs)
    if inputs % 2 == 0:
        for prefix, block in blocks.items():
            if len(prefix) == inputs:
                sites[prefix] = (
                    block.x + block.size // 2,
                    block.y + block.size // 2,
                )
    else:
        for prefix, block in blocks.items():
            if len(prefix) != inputs - 1:
                continue
            middle_x = block.x + block.size // 2
            middle_y = block.y + block.size // 2
            sites[prefix + "0"] = (middle_x - 8, middle_y + 8)
            sites[prefix + "1"] = (middle_x + 8, middle_y + 8)
    return sites


def _h_term_layout(table: str) -> "_Layout":
    """Route one truth table's parallel minterm tree through an H-layout.

    Every wire takes a lane fixed by its class (see ``_LATTICE``): the
    input feeders run across then down, and everything else runs down its
    own column then across, except the ``1`` literal's last hop to a gate
    whose sibling sits beside it, which passes under the target.  Nothing
    here searches; the collision check in :meth:`_RoutingLayout.route` is
    a guard on the lattice.
    """
    truth_table = table
    inputs = len(table).bit_length() - 1
    margin = _LATTICE * inputs + _LATTICE  # the root anchors and input feeders
    sites = {
        prefix: (x + margin, y + margin)
        for prefix, (x, y) in _h_minterm_sites(inputs).items()
    }
    layout = _RoutingLayout()
    signals = {
        prefix: index
        for index, prefix in enumerate(prefix for prefix in sites if len(prefix) >= 2)
    }
    literal_start = len(signals)

    def literal(depth: int, bit: str) -> int:
        return literal_start + 2 * depth + int(bit)

    next_signal = literal_start + 2 * inputs
    results: dict[str, int | None] = {
        prefix: signals[prefix] if truth_table[int(prefix, 2)] == "1" else None
        for prefix in sites
        if len(prefix) == inputs
    }
    result_gates: set[str] = set()
    for depth in range(inputs - 1, -1, -1):
        for prefix in (p for p in sites if len(p) == depth):
            zero = results.get(prefix + "0")
            one = results.get(prefix + "1")
            if zero is not None and one is not None:
                results[prefix] = next_signal
                next_signal += 1
                result_gates.add(prefix)
            else:
                results[prefix] = zero if zero is not None else one
    result_signal = results[""]
    if result_signal is None:  # handled by the scalar constant construction
        raise AssertionError("the H layout needs at least one selected minterm")

    for prefix, (x, y) in sites.items():
        if len(prefix) >= 2:
            layout.glyph(x, y, "a")
        if prefix:
            signal = literal(0, prefix[0]) if len(prefix) == 1 else signals[prefix]
            layout.reserve((x + 1, y), signal)
        if len(prefix) >= 2:
            parent = prefix[:-1]
            layout.reserve(
                (x - 1, y - 1),
                (literal(0, parent[0]) if len(parent) == 1 else signals[parent]),
            )
            layout.reserve((x - 1, y + 1), literal(len(prefix) - 1, prefix[-1]))

    def result_anchor(prefix: str) -> tuple[int, int]:
        x, y = sites[prefix]
        return x + _RESULT_TRACK[0], y - _RESULT_TRACK[1]

    # Every result anchor is kept clear whether or not this table uses it,
    # so the literal and selector trees are routed on a canvas that does
    # not depend on the table; the holds are released before the results
    # are routed.  A route may cross a held cell's neighbourhood but may
    # not corner there (see :meth:`_RoutingLayout._route_is_free`).
    for prefix in sites:
        if len(prefix) == inputs:
            continue
        x, y = result_anchor(prefix)
        for cell in ((x, y), (x + 1, y), (x - 1, y - 1), (x - 1, y + 1)):
            layout.reserve(cell, _HOLD)
    literal_anchors: dict[tuple[int, str, str], tuple[int, int]] = {}
    roots: dict[tuple[int, str], tuple[int, int]] = {}
    for depth in range(inputs):
        for bit in "01":
            for prefix in sites:
                if len(prefix) <= depth:
                    x, y = sites[prefix]
                    below = _LATTICE * (depth - len(prefix))
                    point = (
                        x - _LITERAL_TRACK_X[bit] - below,
                        y - _LITERAL_TRACK_Y[bit] - below,
                    )
                    literal_anchors[(depth, bit, prefix)] = point
                    layout.reserve(point, literal(depth, bit))
                    if not prefix:
                        layout.junction(*point, literal(depth, bit))
            roots[(depth, bit)] = literal_anchors[(depth, bit, "")]
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
                roots[(depth, bit)],
                literal(depth, bit),
                "across",
            )
    for (depth, bit, prefix), point in literal_anchors.items():
        if prefix:
            layout.junction(*point, literal(depth, bit))
    for prefix, (x, y) in sites.items():
        if not prefix:
            continue
        signal = literal(0, prefix[0]) if len(prefix) == 1 else signals[prefix]
        source = (x + 1, y)
        layout.junction(*source, signal)
        for bit in "01":
            child = prefix + bit
            if child not in sites:
                continue
            child_x, child_y = sites[child]
            target = (child_x - 1, child_y - 1)
            layout.route(source, target, signal)
    for depth in range(inputs):
        for bit in "01":
            signal = literal(depth, bit)
            frontier = [""]
            for level in range(depth + 1):
                following = []
                for prefix in frontier:
                    branches = bit if level == depth else "01"
                    source = literal_anchors[(depth, bit, prefix)]
                    for branch in branches:
                        child = prefix + branch
                        shape: _Shape = "down"
                        if level == depth:
                            child_x, child_y = sites[child]
                            target = (
                                (child_x + 1, child_y)
                                if len(child) == 1
                                else (child_x - 1, child_y + 1)
                            )
                            # Side-by-side siblings put both last-level
                            # targets on one row, and the ``0`` wire corners
                            # on it first; the ``1`` wire passes underneath.
                            side_by_side = (
                                sites[prefix + "0"][0] != sites[prefix + "1"][0]
                            )
                            if side_by_side and bit == "1":
                                shape = "under"
                        else:
                            target = literal_anchors[(depth, bit, child)]
                            following.append(child)
                        layout.route(source, target, signal, shape)
                frontier = following
    layout.release(_HOLD)
    result_points: dict[str, tuple[int, int]] = {}
    for prefix, result_value in results.items():
        if result_value is None:
            continue
        if len(prefix) == inputs:
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
            prefix + bit for bit in "01" if results.get(prefix + bit) is not None
        ]
        for child, target in zip(
            children, ((x - 1, y - 1), (x - 1, y + 1)), strict=True
        ):
            layout.reserve(target, cast(int, results[child]))
    root = result_points[""]
    layout.junction(*root, result_signal)
    layout.glyph(root[0] + 1, root[1], "-")
    layout.glyph(root[0] + 2, root[1], ":")
    for depth in range(inputs):
        for prefix in (p for p in sites if len(p) == depth and results[p] is not None):
            children = [
                prefix + bit for bit in "01" if results.get(prefix + bit) is not None
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
    return layout


class _Layout:
    """Wire segments and glyphs, rendered to characters only at the end.

    Segments are recorded with the signal they carry so the renderer can
    tell a legitimate crossing (two different signals, drawn ``=``) from a
    collision (two segments of different signals running the same way
    through one cell, which would merge them).

    A run is stored as one interval, not cell by cell: taps grow linearly
    with the drawing, so per-cell tables cost quadratic time and memory --
    n=9 held ~20M dict entries and n=10 would not fit.  The collision
    checks compare intervals instead, and the renderer paints them with
    slice assignment.
    """

    def __init__(self) -> None:
        """Start an empty layout."""
        # Runs are half-open interior intervals keyed by the fixed axis:
        # row -> [(x0, x1, signal)] and column -> [(y0, y1, signal)].
        self.horizontal: dict[int, list[tuple[int, int, int]]] = {}
        self.vertical: dict[int, list[tuple[int, int, int]]] = {}
        self.junctions: dict[tuple[int, int], int] = {}
        self.glyphs: dict[tuple[int, int], str] = {}
        # Glyph coordinates indexed both ways, for the run/glyph checks.
        self._glyph_rows: dict[int, list[int]] = {}
        self._glyph_cols: dict[int, list[int]] = {}

    def glyph(self, x: int, y: int, char: str) -> None:
        """Place a literal character (a gate, an input dash, an output)."""
        self._check_free(x, y)
        self.glyphs[(x, y)] = char
        insort(self._glyph_rows.setdefault(y, []), x)
        insort(self._glyph_cols.setdefault(x, []), y)

    def junction(self, x: int, y: int, signal: int) -> None:
        """Place a ``.`` carrying ``signal``."""
        existing = self.junctions.get((x, y))
        if existing is not None and existing != signal:
            raise AssertionError(f"junctions of two signals meet at ({x}, {y})")
        self._check_free(x, y)
        self.junctions[(x, y)] = signal

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        """Record a horizontal run between two junctions, exclusive."""
        lo, hi = min(x0, x1) + 1, max(x0, x1)
        if lo >= hi:
            return
        hit = self._clash(
            self.horizontal.get(y), self._glyph_rows.get(y), lo, hi, signal
        )
        if hit is not None:
            x, wire = hit
            if wire:
                raise AssertionError(f"two signals run horizontal through ({x}, {y})")
            raise AssertionError(f"wire crosses glyph at ({x}, {y})")
        self._record(self.horizontal.setdefault(y, []), (lo, hi, signal))

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        """Record a vertical run between two junctions, exclusive."""
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        if lo >= hi:
            return
        hit = self._clash(self.vertical.get(x), self._glyph_cols.get(x), lo, hi, signal)
        if hit is not None:
            y, wire = hit
            if wire:
                raise AssertionError(f"two signals run vertical through ({x}, {y})")
            raise AssertionError(f"wire crosses glyph at ({x}, {y})")
        self._record(self.vertical.setdefault(x, []), (lo, hi, signal))

    @staticmethod
    def _record(runs: list[tuple[int, int, int]], run: tuple[int, int, int]) -> None:
        """Insert an interval, taking O(1) for the builder's ordered runs."""
        if runs and runs[-1][2] == run[2] and run[0] <= runs[-1][1]:
            a, b, signal = runs[-1]
            runs[-1] = (min(a, run[0]), max(b, run[1]), signal)
            return
        if not runs or runs[-1] <= run:
            runs.append(run)
        else:  # layout-guard tests may deliberately insert out of order
            insort(runs, run)

    @staticmethod
    def _clash(
        runs: list[tuple[int, int, int]] | None,
        glyph_line: list[int] | None,
        lo: int,
        hi: int,
        signal: int,
    ) -> tuple[int, bool] | None:
        """First cell of ``[lo, hi)`` claimed against ``signal``, if any.

        Returns the offending coordinate along the run's axis and whether
        the clash is another signal's wire (``True``) or a glyph.
        """
        hit: tuple[int, bool] | None = None
        ordered = runs or []
        index = max(0, bisect_left(ordered, (lo, -1, -1)) - 1)
        while index < len(ordered):
            a, b, s = ordered[index]
            if a >= hi:
                break
            if s != signal and a < hi and lo < b:
                at = max(lo, a)
                if hit is None or at < hit[0]:
                    hit = (at, True)
            index += 1
        glyphs = glyph_line or []
        index = bisect_left(glyphs, lo)
        while index < len(glyphs):
            g = glyphs[index]
            if g >= hi:
                break
            if lo <= g < hi and (hit is None or g < hit[0]):
                hit = (g, False)
            index += 1
        return hit

    def _check_free(self, x: int, y: int) -> None:
        """Reject placing a glyph or junction over a wire or another glyph."""
        if (x, y) in self.glyphs:
            raise AssertionError(f"two glyphs at ({x}, {y})")
        if self._covered(self.horizontal.get(y), x) or self._covered(
            self.vertical.get(x), y
        ):
            raise AssertionError(f"glyph at ({x}, {y}) lands on a wire")

    @staticmethod
    def _covered(runs: list[tuple[int, int, int]] | None, point: int) -> bool:
        """Whether a sorted interval line covers ``point``."""
        if not runs:
            return False
        index = bisect_left(runs, (point + 1, -1, -1)) - 1
        return index >= 0 and runs[index][0] <= point < runs[index][1]

    def _check_junction_spacing(self) -> None:
        """Reject two signals' junctions resting within one cell.

        A ``.`` connects to all eight of its neighbours, so two junctions
        carrying different signals that end up adjacent -- diagonally
        included -- merge into a single wiring.  Checking it here catches
        the whole class at once, rather than relying on the spacing
        constants to be large enough in every case.
        """
        for (x, y), signal in self.junctions.items():
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    other = self.junctions.get((x + dx, y + dy))
                    if other is not None and other != signal:
                        raise AssertionError(
                            f"junctions of different signals touch at "
                            f"({x}, {y}) and ({x + dx}, {y + dy})",
                        )

    def render(self) -> str:
        """Return the layout as text, deriving each cell from its coverage.

        Cell priority is glyph, then junction ``.``, then the wires: a
        horizontal and a vertical sharing a cell is a crossover ``=`` (the
        spec connects "opposite wires" across it), either alone is ``-`` or
        ``|``.  Rows are painted into byte buffers -- horizontal runs by
        slice, everything else point by point -- and cut at their last
        occupied cell, which is what per-cell ``rstrip`` did: every covered
        cell renders non-space.
        """
        self._check_junction_spacing()

        height = 0
        for y in self.horizontal:
            height = max(height, y + 1)
        for runs in self.vertical.values():
            for _, b, _ in runs:
                height = max(height, b)
        for _, y in self.junctions:
            height = max(height, y + 1)
        for _, y in self.glyphs:
            height = max(height, y + 1)
        if height == 0:
            return ""  # pragma: no cover - every table lays a wire

        # Rightmost occupied cell per row, and the point features by row.
        last = [-1] * height
        verts: dict[int, list[int]] = {}
        for x, runs in self.vertical.items():
            for a, b, _ in runs:
                for y in range(a, b):
                    verts.setdefault(y, []).append(x)
                    if x > last[y]:
                        last[y] = x
        for y, runs in self.horizontal.items():
            edge = max(b for _, b, _ in runs) - 1
            if edge > last[y]:
                last[y] = edge
        dots: dict[int, list[int]] = {}
        for x, y in self.junctions:
            dots.setdefault(y, []).append(x)
            if x > last[y]:
                last[y] = x
        marks: dict[int, list[tuple[int, int]]] = {}
        for (x, y), char in self.glyphs.items():
            marks.setdefault(y, []).append((x, ord(char)))
            if x > last[y]:
                last[y] = x

        dash, pipe, cross, dot = ord("-"), ord("|"), ord("="), ord(".")
        dashes = b"-" * (max(last) + 1)
        spaces = b" " * (max(last) + 1)
        rows = []
        for y in range(height):
            edge = last[y]
            if edge < 0:
                rows.append("")
                continue
            buf = bytearray(spaces[: edge + 1])
            for a, b, _ in self.horizontal.get(y, ()):
                buf[a:b] = dashes[: b - a]
            for x in verts.get(y, ()):
                buf[x] = cross if buf[x] == dash or buf[x] == cross else pipe
            for x in dots.get(y, ()):
                buf[x] = dot
            for x, code in marks.get(y, ()):
                buf[x] = code
            rows.append(buf.decode("ascii"))
        return "\n".join(rows)


class _RoutingLayout(_Layout):
    """Layout whose wires are laid in fixed shapes over indexed cells."""

    def __init__(self) -> None:
        super().__init__()
        self._horizontal_cells: dict[tuple[int, int], int] = {}
        self._vertical_cells: dict[tuple[int, int], int] = {}
        self._reserved: dict[tuple[int, int], int] = {}

    def reserve(self, point: tuple[int, int], signal: int) -> None:
        """Keep a future junction clear for ``signal`` while routing."""
        self._reserved[point] = signal

    def release(self, signal: int) -> None:
        """Drop every reservation held by ``signal``."""
        self._reserved = {
            point: owner for point, owner in self._reserved.items() if owner != signal
        }

    def junction(self, x: int, y: int, signal: int) -> None:
        """Place a junction unless another signal already occupies its cell."""
        existing = self.junctions.get((x, y))
        covering = {
            value
            for value in (
                self._horizontal_cells.get((x, y)),
                self._vertical_cells.get((x, y)),
            )
            if value is not None
        }
        if (
            (existing is not None and existing != signal)
            or (x, y) in self.glyphs
            or bool(covering - {signal})
        ):
            raise AssertionError(f"junction collision at ({x}, {y})")
        self.junctions[(x, y)] = signal

    def run_horizontal(self, x0: int, x1: int, y: int, signal: int) -> None:
        """Record a horizontal run and index its occupied cells."""
        lo, hi = min(x0, x1) + 1, max(x0, x1)
        for x in range(lo, hi):
            other = self._horizontal_cells.get((x, y))
            if (other is not None and other != signal) or (x, y) in self.glyphs:
                raise AssertionError(f"horizontal collision at ({x}, {y})")
        self._record(self.horizontal.setdefault(y, []), (lo, hi, signal))
        for x in range(lo, hi):
            self._horizontal_cells[(x, y)] = signal

    def run_vertical(self, x: int, y0: int, y1: int, signal: int) -> None:
        """Record a vertical run and index its occupied cells."""
        lo, hi = min(y0, y1) + 1, max(y0, y1)
        for y in range(lo, hi):
            other = self._vertical_cells.get((x, y))
            if (other is not None and other != signal) or (x, y) in self.glyphs:
                raise AssertionError(f"vertical collision at ({x}, {y})")
        self._record(self.vertical.setdefault(x, []), (lo, hi, signal))
        for y in range(lo, hi):
            self._vertical_cells[(x, y)] = signal

    def route(
        self,
        source: tuple[int, int],
        target: tuple[int, int],
        signal: int,
        shape: _Shape = "down",
    ) -> None:
        """Lay one wire in the given shape; the caller has chosen its lane.

        ``down`` runs along the source's column and then the target's row,
        ``across`` along the source's row and then the target's column, and
        ``under`` along the source's column to two rows past the target,
        across, and back up into it -- the shape that feeds a gate's lower
        input when a sibling wire already corners on the target's row.  The
        collision check is a guard on the layout's spacing rules, not a
        search: a wire that does not fit is a spacing bug.
        """
        sx, sy = source
        tx, ty = target
        if shape == "down":
            points = [source, (sx, ty), target]
        elif shape == "across":
            points = [source, (tx, sy), target]
        else:
            points = [source, (sx, ty + 2), (tx, ty + 2), target]
        if not self._route_is_free(points, signal):
            raise AssertionError(f"{shape} route from {source} to {target} collides")
        self._add_route(points, signal)

    def _add_route(self, points: list[tuple[int, int]], signal: int) -> None:
        """Add one already checked rectilinear route."""
        for point in points:
            self.junction(*point, signal)
        for (x0, y0), (x1, y1) in pairwise(points):
            if x0 == x1:
                self.run_vertical(x0, y0, y1, signal)
            else:
                self.run_horizontal(x0, x1, y0, signal)

    def _route_is_free(self, points: list[tuple[int, int]], signal: int) -> bool:
        """Whether a wire can be added without merging or overlapping signals."""
        for x, y in points:
            if (
                (x, y) in self.glyphs
                or self._reserved.get((x, y), signal) != signal
                or self._horizontal_cells.get((x, y), signal) != signal
                or self._vertical_cells.get((x, y), signal) != signal
            ):
                return False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    other = self.junctions.get((x + dx, y + dy))
                    if other is not None and other != signal:
                        return False
                    if self._reserved.get((x + dx, y + dy)) == _HOLD:
                        return False
        for (x0, y0), (x1, y1) in pairwise(points):
            if x0 == x1:
                cells = ((x0, y) for y in range(min(y0, y1) + 1, max(y0, y1)))
                occupied = self._vertical_cells
            else:
                cells = ((x, y0) for x in range(min(x0, x1) + 1, max(x0, x1)))
                occupied = self._horizontal_cells
            for cell in cells:
                if (
                    cell in self.glyphs
                    or self._reserved.get(cell, signal) != signal
                    or occupied.get(cell, signal) != signal
                    or self.junctions.get(cell, signal) != signal
                ):
                    return False
        return True


class _Builder:
    """Allocates buses and gate bands, and records their wiring.

    A *bus* is a vertical column carrying one signal, written once and read
    by any number of gates.  A gate occupies a three-row band and leaves its
    result on a fresh bus.
    """

    def __init__(self) -> None:
        """Start an empty build."""
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
            self.next_column += 3 * _COL_STEP
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
        return self.next_column + 3 * _COL_STEP <= self.limit

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
    negated = selectors[1]
    if negated is None:  # pragma: no cover - built before the fold
        raise AssertionError("selector has no complemented rail")
    if zero == "1" and one == "0":
        return negated
    if zero == "0":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", selector, one)
    if one == "0":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("a", negated, zero)
    if zero == "1":
        if not isinstance(one, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", negated, one)
    if one == "1":
        if not isinstance(zero, int):  # pragma: no cover - constants handled above
            raise AssertionError("unexpected constant mux arm")
        return builder.gate("o", selector, zero)
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
    """Return selector levels whose direct mux rule needs ``~selector``."""
    stack: list[tuple[int, int]] = []
    identities: dict[tuple[int, int, int], int] = {}
    needed: set[int] = set()
    next_identity = 2
    for bit in truth_table:
        identity, level = int(bit), 0
        while stack and stack[-1][1] == level:
            zero, _ = stack.pop()
            if zero != identity:
                if (zero, identity) != (0, 1):
                    needed.add(n - 1 - level)
                key = (level, zero, identity)
                if key not in identities:
                    identities[key] = next_identity
                    next_identity += 1
                identity = identities[key]
            level += 1
        stack.append((identity, level))
    return needed


def _circuit_diagram_at(truth_table: str, limit: int | None) -> str:
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
    """
    _validate_truth_table(truth_table)

    builder = _Builder()
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
    return builder.layout.render()


def circuit_diagram(truth_table: str, width: int | None = None) -> str:
    """Build a Circuit Diagram program computing the given truth table.

    See :func:`_circuit_diagram_at` for the construction.  ``width`` asks
    for a column count: the drawing is built once without one, and again
    inside the width if that came out too wide.

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

    The floor is what a band cannot reclaim -- the rails and the complements,
    which their mux levels share and which therefore stay live for the whole
    drawing -- plus the carried signals and one gate group.  That is about
    ``8 * n`` columns, so the floor grows with the inputs rather than with
    the table.
    """
    _validate_truth_table(truth_table)
    inputs = len(truth_table).bit_length() - 1
    if width is None and inputs >= 8 and "1" in truth_table:
        return _h_term_layout(truth_table).render()
    flat = _circuit_diagram_at(truth_table, None)
    if width is None or max(len(line) for line in flat.split("\n")) <= width:
        return flat
    banded = _circuit_diagram_at(truth_table, width)
    if max(len(line) for line in banded.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return banded
    return flat
