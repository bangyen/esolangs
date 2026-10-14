"""Alternating tree layouts and bounded sharing routes for Dig."""

from collections.abc import Callable
from typing import NamedTuple

from esolangs.generation.helpers import constant_span_test, essential_inputs, read_at
from esolangs.languages.dig.generator._leaf import (
    _DIG_DIGITS,
    _DIG_OPAQUE,
    _DIG_SPAN,
    _DIG_TURNS,
    _dig_constant_leaf,
    _dig_flat_leaf,
    _dig_flat_walk,
    _render,
)

_DIG_DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))


# The alternating layout's branch: arm, read a bit, store it, turn on it.
# Its count is not in the block at all -- ``$`` takes the first digit of up,
# right, down, left, so a digit beside the ``$`` serves, and the cell the
# count would have occupied is a whole cell off every node.
_DIG_ALT_BRANCH = "$~;#"


# Two work commands is what a branch block arms: read and store.  The
# command after them runs with the counter back at zero, which is what
# ``#`` needs.
_DIG_COUNT = 2


# The block's last cell, the one children attach to.
_DIG_END = len(_DIG_ALT_BRANCH) - 1


#: Inputs one flat leaf answers without branching.  Three per axis is the
#: ceiling: each axis becomes a ``$`` count, and a count is read from a
#: single digit cell, so it cannot exceed nine.
_DIG_LEAF_BITS = 6


class _Point(NamedTuple):
    """A grid cell: ``row`` grows downward, ``col`` grows rightward."""

    row: int
    col: int

    def step(self, heading: int, count: int = 1) -> "_Point":
        """Return the point ``count`` cells from here along ``heading``."""
        d_row, d_col = _DIG_DIRECTIONS[heading]
        return _Point(self.row + d_row * count, self.col + d_col * count)


def _walk_bound(n: int) -> int:
    """Return the command cost a sharing walk may take at ``n`` inputs."""
    bound: int = 128 + (
        46 * 2 ** ((n - 6) // 2) if n % 2 == 0 else 64 * 2 ** ((n - 7) // 2)
    )
    return bound


def _operand_side(heading: int) -> int:
    """Return the lower-numbered side of ``heading``, where an operand sits."""
    return min((heading + 1) % 4, (heading - 1) % 4)


def _remap_reads[P: tuple[int, int]](
    reads: list[tuple[P, P, frozenset[P]]], move: Callable[[P], P]
) -> list[tuple[P, P, frozenset[P]]]:
    """Map every point of each ``(at, want, pending)`` read through ``move``."""
    return [
        (move(at), move(want), frozenset(map(move, held))) for at, want, held in reads
    ]


def _remap_corridors(
    corridors: list[tuple[_Point, int, int]], move: Callable[[_Point], _Point]
) -> list[tuple[_Point, int, int]]:
    """Map each ``(start, heading, distance)`` corridor through ``move``."""
    remapped = []
    for start, heading, distance in corridors:
        begin, finish = move(start), move(start.step(heading, distance))
        span = abs(begin.row - finish.row) + abs(begin.col - finish.col)
        remapped.append((begin, heading, span))
    return remapped


def _dig_alt_clear(
    cells: dict[_Point, str],
    reads: list[tuple[_Point, _Point, frozenset[_Point]]],
    corridors: list[tuple[_Point, int, int]],
) -> None:
    """Refuse an alternating grid whose operands or corridors are crossed.

    Operands sit beside their operator rather than in the block, so which
    digit a reader reaches first is not local to one block; and the bounds
    are a rectangle, so they do not by themselves say a mole's fall is
    clear.  Both are checked against the finished grid rather than argued.

    A ``;`` counts as a digit except where it is named as still pending:
    a store the mole has not reached yet holds the literal semicolon, which
    no reader sees as a digit.
    """
    for point, wanted, pending in reads:
        for offset in _DIG_DIRECTIONS:
            beside = _Point(point.row + offset[0], point.col + offset[1])
            char = cells.get(beside)
            if beside not in pending and char is not None and char in _DIG_DIGITS:
                if beside != wanted:
                    raise AssertionError(
                        f"{cells[point]!r} at {point} reads {beside} before {wanted}"
                    )
                break
        else:
            raise AssertionError(f"{cells[point]!r} at {point} has no operand")
    for start, heading, distance in corridors:
        for count in range(1, distance):
            char = cells.get(start.step(heading, count))
            if char is not None and char in _DIG_OPAQUE:
                raise AssertionError(f"a mole from {start} meets {char!r} on its way")


def _dig_leaf_inputs(
    truth_table: str, n: int
) -> tuple[list[int], list[int], list[int], str]:
    """Return the leaf's two adders' weights, each tree level's skips, the table.

    The leaf takes the last six essential inputs, the ignored ones among
    them, and those just before them while the first adder's digit reaches.
    An ignored input weighs 0, a bare ``~`` rather than a tree level; the
    table is read at the tree's inputs and the leaf's essential ones.  The
    adders split after the first's last essential input, so neither ends on
    an ignored one.  Fewer than four essential inputs, a trailing ignored
    one, or a forward leg past the digit keeps every leaf input.

    Above the leaf, an ignored input is a bare ``~`` in the next level's
    block (:func:`_dig_alternating`), so a level's skips count the ignored
    inputs just before it; those after the last essential tree input have no
    next level and stay levels.
    """
    essential = essential_inputs(truth_table, n)
    leaf = essential[-_DIG_LEAF_BITS:]

    def weigh(group: range) -> list[int]:
        return [
            1 << sum(j in leaf for j in group if j > i) if i in leaf else 0
            for i in group
        ]

    def fits(group: range, bonus: int) -> bool:
        # ``~ * ;`` per leading essential input, ``~`` per ignored one, the
        # bonus and the last ``~``: the run one digit arms.
        leading = weigh(group)[:-1]
        return sum(3 if w else 1 for w in leading) + bonus + 1 <= _DIG_SPAN

    def levels(depth: int) -> tuple[list[int], list[int]]:
        last = max((i for i in essential if i < depth), default=-1)
        kept: list[int] = []
        skips: list[int] = []
        pending = 0
        for i in range(depth):
            # The skips share the level's one-digit count with its own read.
            if i in essential or i > last or pending == _DIG_SPAN - 2:
                kept.append(i)
                skips.append(pending)
                pending = 0
            else:
                pending += 1
        return kept, skips

    if len(leaf) >= 4 and leaf[-1] == n - 1:
        split = leaf[len(leaf) - len(leaf) // 2 - 1] + 1
        depth = leaf[0]
        while depth and depth - 1 not in essential and fits(range(depth - 1, split), 1):
            depth -= 1
        high, low = range(depth, split), range(split, n)
        if fits(high, 1) and fits(low, 0):
            kept, skips = levels(depth)
            table = read_at(truth_table, [*kept, *leaf], n)
            return weigh(high), weigh(low), skips, table
    bits = min(_DIG_LEAF_BITS, n)
    low_bits = bits // 2
    kept, skips = levels(n - bits)
    return (
        [1 << k for k in reversed(range(bits - low_bits))],
        [1 << k for k in reversed(range(low_bits))],
        skips,
        read_at(truth_table, [*kept, *range(n - bits, n)], n),
    )


def _onto(point: _Point, heading: int, cell: tuple[int, int]) -> _Point:
    """Rotate a leaf-local ``(row, col)`` cell onto the grid at ``point``."""
    row, col = cell
    forward = _DIG_DIRECTIONS[heading]
    sideways = _DIG_DIRECTIONS[(heading + 1) % 4]
    return _Point(
        point.row + col * forward[0] + row * sideways[0],
        point.col + col * forward[1] + row * sideways[1],
    )


def _compact_point(
    point: _Point, travel_axis: int, coordinates: dict[int, int], root: int
) -> _Point:
    """Map ``point`` through travel-axis compaction onto ``root``."""
    if travel_axis == 0:
        return _Point(coordinates[point.row] - root, point.col)
    return _Point(point.row, coordinates[point.col] - root)


def _merged_box(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
    end: int,
) -> tuple[int, int, int, int]:
    """Merge two child bounds into the parent's, anchored at the block end."""
    return (
        min(0, end + left[2], end - right[3]),
        max(end, end + left[3], end - right[2]),
        min(-1, -(2 - left[0] + left[1])),
        max(1, 2 - right[0] + right[1]),
    )


def _expand_point(point: _Point, lane_axis: int, coordinates: dict[int, int]) -> _Point:
    """Stretch ``point`` along the lane axis through gutter coordinates."""
    if lane_axis == 0:
        return _Point(coordinates[point.row], point.col)
    return _Point(point.row, coordinates[point.col])


def _travel_heading(travel_axis: int, *, increasing: bool) -> int:
    """Return the travel-axis heading toward (or away from) growth.

    The travel axis runs east/west when the lane axis is vertical and
    south/north when the lane axis is horizontal.
    """
    if travel_axis == 1:
        return 1 if increasing else 3
    return 2 if increasing else 0


class _LeafKey(NamedTuple):
    """A flat leaf's class: its table slice, entry heading and lane coordinate."""

    span: str
    heading: int
    lane: int


class _AlternatingTree:
    """One alternating Dig tree being painted onto a grid.

    Holds the layout's configuration, derived once from the truth table,
    and every accumulator the painting phases share: the cells, the reads
    and corridors the clearance check verifies, and the sharing and
    parallel bookkeeping.  Each phase is a method so it can be read and
    tested on its own; :func:`_dig_layout` only orders them.
    """

    def __init__(
        self,
        truth_table: str,
        n: int,
        *,
        sharing: bool = False,
        parallel: bool = False,
    ) -> None:
        self.n = n
        self.sharing = sharing
        self.parallel = parallel
        self.high, self.low, self.skips, self.truth_table = _dig_leaf_inputs(
            truth_table, n
        )
        self.depth = len(self.skips)
        self.lane_axis = 0 if self.depth % 2 else 1
        self.travel_axis = 1 - self.lane_axis
        self.constant: Callable[[int, int], bool] = constant_span_test(self.truth_table)
        # Inputs read before each level's block; a constant span reads the rest.
        self.consumed = [0]
        for skip in self.skips:
            self.consumed.append(self.consumed[-1] + 1 + skip)
        self.flat_box = _dig_flat_leaf(
            "0" * (len(self.truth_table) >> self.depth), self.high, self.low
        )[4]
        # Bounds of a subtree, inclusive and local to its first ``$``:
        # (min_x, max_x, min_y, max_y), x along the heading.  A branch block
        # is four cells long and carries its operand one cell off to a side
        # the heading picks, so it reaches one row past its own line.  A
        # level's skipped reads lengthen its block by one cell each.  A
        # constant span is a row of reads, and the children differ, so each
        # is bounded on its own: the one turned left lies on the -y side,
        # the one turned right on the +y side.
        self.boxes: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        self.cells: dict[_Point, str] = {}
        self.protected: list[tuple[int, int]] = []
        self.branches: list[tuple[_Point, int, int, _Point]] = []
        # Each reader against the cell it must read and the stores still
        # pending there, and the blank runs a mole falls along to a child.
        self.reads: list[tuple[_Point, _Point, frozenset[_Point]]] = []
        self.corridors: list[tuple[_Point, int, int]] = []
        self.entries: dict[_Point, _LeafKey] = {}
        self.owners: dict[_LeafKey, _Point] = {}
        self.links: list[tuple[_Point, _Point, _Point]] = []
        self.tails: dict[_Point, int] = {}
        self.rails: dict[_LeafKey, int] = {}
        self.cuts: list[int] = []

    def short_leaf(self, level: int, lo: int) -> str:
        """Return the constant span's read row for ``truth_table[lo]``."""
        return _dig_constant_leaf(
            self.n - self.consumed[level], int(self.truth_table[lo])
        )

    def box(self, level: int, lo: int, hi: int) -> tuple[int, int, int, int]:
        """Return the memoized bounds of the ``[lo, hi)`` subtree."""
        key = (level, lo)
        if key not in self.boxes:
            if self.constant(lo, hi):
                self.boxes[key] = (0, len(self.short_leaf(level, lo)) - 1, 0, 0)
            elif level == self.depth:
                self.boxes[key] = self.flat_box
            else:
                half = (lo + hi) // 2
                left = self.box(level + 1, lo, half)
                right = self.box(level + 1, half, hi)
                self.boxes[key] = _merged_box(left, right, _DIG_END + self.skips[level])
        return self.boxes[key]

    def place(self, point: _Point, char: str) -> None:
        """Paint one cell; a collision is a layout bug, not an overwrite."""
        if point in self.cells:
            raise AssertionError(
                f"two cells at {point}: {self.cells[point]!r} and {char!r}"
            )
        self.cells[point] = char

    def text(
        self, point: _Point, heading: int, code: str, *, rigid: bool = True
    ) -> None:
        """Paint ``code`` from ``point`` along ``heading``."""
        if self.parallel and rigid:
            self.protected.append(
                (
                    point[self.lane_axis],
                    point.step(heading, len(code) - 1)[self.lane_axis],
                )
            )
        for index, char in enumerate(code):
            self.place(point.step(heading, index), char)

    def leaf(self, point: _Point, heading: int, table: str) -> None:
        """Rotate one flat leaf onto the grid, blanks and all.

        The blanks are placed rather than left out: they are the corridors
        the leaf walks, and placing them makes any stray tree cell inside
        the reserved box a collision instead of a silent detour.
        """
        chars, spins, wants, _exit, bounds = _dig_flat_leaf(table, self.high, self.low)
        painted = {_onto(point, heading, cell): char for cell, char in chars.items()}
        painted |= {
            _onto(point, heading, cell): _DIG_TURNS[(heading + d) % 4]
            for cell, d in spins.items()
        }
        min_x, max_x, min_y, max_y = bounds
        if self.parallel:
            self.protected.append(
                (
                    _onto(point, heading, (min_y, min_x))[self.lane_axis],
                    _onto(point, heading, (max_y, max_x))[self.lane_axis],
                )
            )
        for row in range(min_y, max_y + 1):
            for col in range(min_x, max_x + 1):
                spot = _onto(point, heading, (row, col))
                self.place(spot, painted.get(spot, " "))
        self.reads.extend(
            (
                _onto(point, heading, at),
                _onto(point, heading, want),
                frozenset(_onto(point, heading, c) for c in hold),
            )
            for at, want, hold in wants
        )

    def node(
        self,
        level: int,
        point: _Point,
        heading: int,
        lo: int,
        hi: int,
        *,
        paint: bool = True,
    ) -> None:
        """Paint the ``[lo, hi)`` subtree, or with ``paint=False`` just map it.

        The dry run records each leaf's entry point and its key so sharing
        can assign lanes before anything is painted.
        """
        if self.constant(lo, hi):
            self._constant_span(level, point, heading, lo, paint=paint)
        elif level == self.depth:
            self._leaf_slot(point, heading, lo, hi, paint=paint)
        else:
            self._branch_node(level, point, heading, lo, hi, paint=paint)

    def _constant_span(
        self, level: int, point: _Point, heading: int, lo: int, *, paint: bool
    ) -> None:
        """Paint one constant read row, or with ``paint=False`` skip it."""
        if not paint:
            return
        code = self.short_leaf(level, lo)
        if self.sharing:
            self.tails[point] = len(code)
        self.text(point, heading, code)
        self.reads.extend(
            (point.step(heading, i), point.step(heading, i + 1), frozenset())
            for i, char in enumerate(code)
            if char == "$"
        )

    def _leaf_slot(
        self, point: _Point, heading: int, lo: int, hi: int, *, paint: bool
    ) -> None:
        """Map one flat leaf's entry and key, or paint it when shared."""
        key = _LeafKey(self.truth_table[lo:hi], heading, point[self.lane_axis])
        if not paint:
            self.entries[point] = key
            if (
                key not in self.owners
                or point[self.travel_axis] > self.owners[key][self.travel_axis]
            ):
                self.owners[key] = point
        elif not self.sharing or key not in self.owners or point == self.owners[key]:
            self.leaf(point, heading, self.truth_table[lo:hi])

    def _branch_node(
        self,
        level: int,
        point: _Point,
        heading: int,
        lo: int,
        hi: int,
        *,
        paint: bool,
    ) -> None:
        """Paint one branch block and map or paint its two children."""
        skip = self.skips[level]
        end = point.step(heading, _DIG_END + skip)
        if paint:
            self._paint_branch_block(point, heading, skip, end)
        half = (lo + hi) // 2
        for child_bit, child_bounds in ((0, (lo, half)), (1, (half, hi))):
            self._place_child(
                level, point, end, heading, child_bit, child_bounds, paint=paint
            )

    def _paint_branch_block(
        self, point: _Point, heading: int, skip: int, end: _Point
    ) -> None:
        """Paint one ``$~;#`` block with its operand digit beside the ``$``.

        The operand digit sits one cell off the block.  Which side is
        forced -- a reader takes the first digit of up, right, down, left,
        so the operand goes on the lower-numbered of the two sides and a
        stray digit opposite it can never be read first.
        """
        if self.parallel:
            self.branches.append((point, heading, skip, end))
        side = _operand_side(heading)
        count = point.step(side)
        self.place(count, str(_DIG_COUNT + skip))
        self.reads.append((point, count, frozenset()))
        self.text(
            point,
            heading,
            _DIG_ALT_BRANCH[0] + "~" * skip + _DIG_ALT_BRANCH[1:],
            rigid=False,
        )
        self.reads.append((end, end.step(heading, -1), frozenset()))

    def _place_child(
        self,
        level: int,
        point: _Point,
        end: _Point,
        heading: int,
        child_bit: int,
        child_bounds: tuple[int, int],
        *,
        paint: bool,
    ) -> None:
        """Place one child past the parent's bounds and map or paint it.

        Two cells off, not one: a leaf reaches far enough sideways that
        its box, turned a quarter, would otherwise land on this block's
        own operand.  The spare cell is corridor the mole falls through.
        """
        child_heading = (heading + (1 if child_bit else -1)) % 4
        distance = 2 - self.box(level + 1, *child_bounds)[0]
        child = end.step(child_heading, distance)
        if paint:
            self.corridors.append((end, child_heading, distance))
            if self.sharing:
                self.links.append((point, end, child))
        self.node(level + 1, child, child_heading, *child_bounds, paint=paint)

    def paint(self) -> None:
        """Paint the whole tree with the root heading east."""
        self.node(0, _Point(0, 0), 1, 0, len(self.truth_table))

    def plan_sharing(self) -> bool:
        """Dry-run the tree and assign shared leaf lanes; False aborts."""
        self.node(0, _Point(0, 0), 1, 0, len(self.truth_table), paint=False)
        by_end, starts = self._sharing_lane_groups()
        shared, rails = self._assign_shared_lanes(by_end, starts)
        if not shared:
            return False
        # Leave unmatched copies painted, even if their contents coincide.
        self.owners = {
            key: owner for key, owner in self.owners.items() if key in shared
        }
        self.rails = rails
        if self.parallel:
            self.cuts = self._parallel_lane_cuts(rails)
            if not self.cuts:
                return False
        return True

    def _sharing_lane_groups(
        self,
    ) -> tuple[dict[int, list[_LeafKey]], dict[_LeafKey, int]]:
        """Group repeated leaf classes by travel-axis span end; return each start.

        A class is repeated when more than one entry maps to its key.
        """
        counts: dict[_LeafKey, int] = {}
        starts: dict[_LeafKey, int] = {}
        for point, key in self.entries.items():
            counts[key] = counts.get(key, 0) + 1
            starts[key] = min(
                starts.get(key, point[self.travel_axis]), point[self.travel_axis]
            )
        by_end: dict[int, list[_LeafKey]] = {}
        for key, count in counts.items():
            if count > 1:
                by_end.setdefault(self.owners[key][self.travel_axis], []).append(key)
        return by_end, starts

    def _assign_shared_lanes(
        self,
        by_end: dict[int, list[_LeafKey]],
        starts: dict[_LeafKey, int],
    ) -> tuple[set[_LeafKey], dict[_LeafKey, int]]:
        """Share lanes among earliest-ending classes, reusing a free rail.

        Two lanes need one gutter cell; further overlapping classes stay
        unshared.
        """
        shared: set[_LeafKey] = set()
        rails: dict[_LeafKey, int] = {}
        occupied: dict[int, list[int | None]] = {}
        for lane_end in sorted(by_end):
            for key in by_end[lane_end]:
                lane_coordinate = (
                    key.lane - _DIG_DIRECTIONS[key.heading][self.lane_axis]
                )
                busy = occupied.setdefault(
                    lane_coordinate, [None] * (2 if self.parallel else 1)
                )
                for rail, last in enumerate(busy):
                    if last is None or starts[key] > last:
                        shared.add(key)
                        rails[key] = rail
                        busy[rail] = lane_end
                        break
        return shared, rails

    def _parallel_lane_cuts(self, rails: dict[_LeafKey, int]) -> list[int]:
        """Return the gutter cuts separating the second rail's lanes."""
        return sorted(
            {
                key.lane + int(_DIG_DIRECTIONS[key.heading][self.lane_axis] < 0)
                for key, rail in rails.items()
                if rail
            }
        )

    def expand_parallel(self) -> bool:
        """Stretch the grid with gutters for parallel lanes; False aborts."""
        coordinates = self._gutter_coordinates()

        # A blank inside an armed leaf or constant read run would spend
        # its counter. Gutters may cross only the resizable branch blocks.
        if any(
            abs(coordinates[a] - coordinates[b]) != abs(a - b)
            for a, b in self.protected
        ):
            return False

        def expand(point: _Point) -> _Point:
            return _expand_point(point, self.lane_axis, coordinates)

        branch_readers: set[_Point] = set()
        for point, heading, skip, end in self.branches:
            branch_readers |= self._clear_branch(point, heading, skip, end)
        self.cells = {expand(point): char for point, char in self.cells.items()}
        self.reads = _remap_reads(
            [read for read in self.reads if read[0] not in branch_readers], expand
        )
        for point, heading, skip, end in self.branches:
            if not self._repaint_branch(point, heading, skip, end, expand):
                return False
        self.corridors = _remap_corridors(self.corridors, expand)
        self.entries = {expand(point): key for point, key in self.entries.items()}
        self.owners = {key: expand(point) for key, point in self.owners.items()}
        self.links = [
            (expand(parent), expand(end), expand(child))
            for parent, end, child in self.links
        ]
        self.tails = {expand(point): cost for point, cost in self.tails.items()}
        return True

    def _gutter_coordinates(self) -> dict[int, int]:
        """Map lane-axis positions to coordinates with a gutter at each cut."""
        low_axis = min(point[self.lane_axis] for point in self.cells)
        high_axis = max(point[self.lane_axis] for point in self.cells)
        root_offset = sum(cut <= 0 for cut in self.cuts)
        coordinates = {}
        shift = 0
        for position in range(low_axis, high_axis + 1):
            while shift < len(self.cuts) and self.cuts[shift] <= position:
                shift += 1
            coordinates[position] = position + shift - root_offset
        return coordinates

    def _clear_branch(
        self, point: _Point, heading: int, skip: int, end: _Point
    ) -> set[_Point]:
        """Erase a branch block and its operand; return the readers to drop."""
        side = _operand_side(heading)
        del self.cells[point.step(side)]
        for i in range(_DIG_END + skip + 1):
            del self.cells[point.step(heading, i)]
        return {point, end}

    def _repaint_branch(
        self,
        point: _Point,
        heading: int,
        skip: int,
        end: _Point,
        expand: Callable[[_Point], _Point],
    ) -> bool:
        """Repaint a stretched branch with its reads first and its store beside #.

        The counter includes the intervening blank cells.
        """
        first, stop = expand(point), expand(end)
        distance = abs(first.row - stop.row) + abs(first.col - stop.col)
        if not _DIG_COUNT + skip <= distance - 1 <= _DIG_SPAN:
            return False
        side = _operand_side(heading)
        count_point = first.step(side)
        if count_point in self.cells:
            return False
        self.cells[count_point] = str(distance - 1)
        code = "$" + "~" * (skip + 1) + " " * (distance - skip - 3) + ";#"
        for i, char in enumerate(code):
            target = first.step(heading, i)
            if target in self.cells:
                return False
            self.cells[target] = char
        self.reads.append((first, count_point, frozenset()))
        self.reads.append((stop, stop.step(heading, -1), frozenset()))
        return True

    def bridge_entries(self) -> bool:
        """Route shared leaf entries to their owners' lanes; False aborts."""
        lanes: dict[_Point, _Point] = {}
        for point, key in self.entries.items():
            if key in self.owners and not self._route_entry(point, key, lanes):
                return False
        self.corridors = self._shorten_corridors(lanes)
        self._chain_lanes(lanes)
        return True

    def _route_entry(
        self,
        point: _Point,
        key: _LeafKey,
        lanes: dict[_Point, _Point],
    ) -> bool:
        """Route one shared entry onto its owner's lane; False on collision."""
        heading = key.heading
        owner = self.owners[key]
        lane = owner.step(heading, -1 - self.rails[key])
        lane = (
            _Point(point.row, lane.col)
            if self.lane_axis == 1
            else _Point(lane.row, point.col)
        )
        travel_heading = _travel_heading(
            self.travel_axis,
            increasing=point[self.travel_axis] <= owner[self.travel_axis],
        )
        if lane in self.cells:
            return False
        self.cells[lane] = (
            _DIG_TURNS[heading] if point == owner else _DIG_TURNS[travel_heading]
        )
        lanes[point] = lane
        return True

    def _shorten_corridors(
        self, lanes: dict[_Point, _Point]
    ) -> list[tuple[_Point, int, int]]:
        """Shorten each corridor to stop where its child's lane cell now sits."""
        shortened = []
        for start, heading, distance in self.corridors:
            child = start.step(heading, distance)
            if child in lanes:
                distance -= 1 + self.rails[self.entries[child]]
            shortened.append((start, heading, distance))
        return shortened

    def _chain_lanes(self, lanes: dict[_Point, _Point]) -> None:
        """Link same-class lanes along the travel axis in position order."""
        by_position: dict[int, list[_Point]] = {}
        for point in lanes:
            by_position.setdefault(lanes[point][self.travel_axis], []).append(point)
        previous: dict[_LeafKey, _Point] = {}
        for position in sorted(by_position):
            for point in by_position[position]:
                key, lane = self.entries[point], lanes[point]
                if key in previous:
                    start = previous[key]
                    self.corridors.append(
                        (
                            start,
                            _travel_heading(self.travel_axis, increasing=True),
                            lane[self.travel_axis] - start[self.travel_axis],
                        )
                    )
                previous[key] = lane

    def compact_sharing(self) -> bool:
        """Compact unused travel-axis rows/columns; False aborts.

        Keep every internal blank in a leaf box; compact only the unused
        rows or columns between stamps, where the mole is overground.
        """
        coordinates = {
            at: i
            for i, at in enumerate(sorted({p[self.travel_axis] for p in self.cells}))
        }
        root = coordinates[0]

        def compact(point: _Point) -> _Point:
            return _compact_point(point, self.travel_axis, coordinates, root)

        self.cells = {compact(point): char for point, char in self.cells.items()}
        compact_reads = _remap_reads(self.reads, compact)
        compact_corridors = _remap_corridors(self.corridors, compact)
        # Compaction can make a previously distant digit a reader's neighbour.
        try:
            _dig_alt_clear(self.cells, compact_reads, compact_corridors)
        except AssertionError:
            return False
        return self._sharing_walk_cost(compact) <= _walk_bound(self.n)

    def _sharing_walk_cost(self, compact: Callable[[_Point], _Point]) -> int:
        """Return the entry ray plus the worst walk of any shared entry."""
        costs = {_Point(0, 0): 0}
        for parent, end, child in self.links:
            p, e, c = compact(parent), compact(end), compact(child)
            costs[child] = (
                costs[parent]
                + abs(p.row - e.row)
                + abs(p.col - e.col)
                + abs(e.row - c.row)
                + abs(e.col - c.col)
            )
        leaf_cost = _dig_flat_walk(self.high, self.low)
        worst = max((costs[p] + cost for p, cost in self.tails.items()), default=0)
        for point, key in self.entries.items():
            travel = 0
            if key in self.owners:
                travel = abs(
                    compact(point)[self.travel_axis]
                    - compact(self.owners[key])[self.travel_axis]
                )
            worst = max(worst, costs[point] + travel + leaf_cost)
        entry_cost = (
            4 - min(row for row, _ in self.cells) - min(col for _, col in self.cells)
        )
        return entry_cost + worst

    def render(self) -> str:
        """Shift the grid to a blank entry ray and render it."""
        min_row = min(point.row for point in self.cells)
        min_col = min(point.col for point in self.cells)
        row_shift, col_shift = 2 - min_row, 2 - min_col
        normalized: dict[tuple[int, int], str] = {
            (point.row + row_shift, point.col + col_shift): char
            for point, char in self.cells.items()
        }
        root_row, root_col = row_shift, col_shift
        if any(normalized.get((root_row, col), " ") != " " for col in range(root_col)):
            raise AssertionError("the alternating Dig tree blocked its entry ray")
        for row in range(root_row):
            normalized[(row, 0)] = " "
        for col in range(root_col):
            normalized[(root_row, col)] = " "
        normalized[(0, 0)] = "'"
        normalized[(root_row, 0)] = ">"
        return _render(normalized, dense=True)


def _dig_layout(
    truth_table: str,
    n: int,
    *,
    sharing: bool = False,
    parallel: bool = False,
) -> str | None:
    """Lay a Dig tree whose leaves are flat tables, branch axis rotating.

    The last six inputs are not branched on at all: a leaf holds their whole
    table as one rectangle of digits and indexes it with two counts (see
    :func:`_dig_flat_leaf`).  Children enter on the local y-axis, placed just
    beyond the parent's most-backward cell; width and height swap and one
    doubles per level, so the rectangle stays O(2**n).  An ignored input
    above the leaf is no level: its read rides the next block, ``$~~;#``.
    """
    tree = _AlternatingTree(truth_table, n, sharing=sharing, parallel=parallel)
    # Build locally with the root heading east.  Its ray from the west is
    # empty by the same bounds recurrence, so an external L-shaped entry can
    # reach it without crossing the tree.
    if sharing and not tree.plan_sharing():
        return None
    tree.paint()
    if parallel and not tree.expand_parallel():
        return None
    if sharing and not tree.bridge_entries():
        return None
    try:
        _dig_alt_clear(tree.cells, tree.reads, tree.corridors)
    except AssertionError:
        if sharing:
            return None
        raise
    if sharing and not tree.compact_sharing():
        return None
    return tree.render()
