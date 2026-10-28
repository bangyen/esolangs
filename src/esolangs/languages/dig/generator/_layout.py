"""Alternating tree layouts and bounded sharing routes for Dig."""

from collections.abc import Callable
from typing import NamedTuple

from esolangs.generation.helpers import constant_span_test, essential_inputs, read_at
from esolangs.languages.dig.generator._leaf import (
    _DIG_DIGITS,
    _DIG_OPAQUE,
    _DIG_SPAN,
    _DIG_TURNS,
    _Box,
    _dig_adder_fits,
    _dig_constant_leaf,
    _dig_flat_leaf,
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
    an ignored one, though the second may end on trailing ignored ones.
    Fewer than four essential inputs, or a forward leg past the digit, keeps
    every leaf input.

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
        return _dig_adder_fits(weigh(group), 2 * bonus)

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

    if len(leaf) >= 4:
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


def _compaction_lines(
    cells: dict[_Point, str],
    reads: list[tuple[_Point, _Point, frozenset[_Point]]],
    travel_axis: int,
) -> list[int]:
    """Return the travel-axis lines compaction keeps, sorted.

    A line is dropped when it holds no cell, which moves the next stamp one
    step from the line before.  Only an adjacency along the travel axis can
    change, so a reader gains a new neighbour only across a dropped run.  An
    empty line is kept beside a reader when that neighbour would be a digit
    (``;`` included unless the read holds it pending), so no compaction
    puts a digit beside a reader that was not already.  The kept line leaves
    the pair two apart, as any dropped run of two or more did.
    """
    held = {point[travel_axis] for point in cells}
    kept = set(held)
    ordered = sorted(held)
    for at, _, pending in reads:
        line = at[travel_axis]
        for sign in (-1, 1):
            if line + sign in held:
                continue
            ahead = [o for o in ordered if (o - line) * sign > 0]
            if not ahead:
                continue
            far = min(ahead, key=lambda o: abs(o - line))
            across = _Point(far, at.col) if travel_axis == 0 else _Point(at.row, far)
            if across in pending:
                continue
            if cells.get(across, " ") in _DIG_DIGITS:
                kept.add(line + sign)
    return sorted(kept)


def _merged_box(
    left: _Box,
    right: _Box,
    end: int,
) -> _Box:
    """Merge two child bounds into the parent's, anchored at the block end."""
    return _Box(
        min(0, end + left.min_y, end - right.max_y),
        max(end, end + left.max_y, end - right.min_y),
        min(-1, -(2 - left.min_x + left.max_x)),
        max(1, 2 - right.min_x + right.max_x),
    )


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


def _sharing_lane_groups(
    entries: dict[_Point, _LeafKey],
    owners: dict[_LeafKey, _Point],
    travel_axis: int,
) -> tuple[dict[int, list[_LeafKey]], dict[_LeafKey, int]]:
    """Group repeated leaf classes by travel-axis span end; return each start.

    A class is repeated when more than one entry maps to its key.
    """
    counts: dict[_LeafKey, int] = {}
    starts: dict[_LeafKey, int] = {}
    for point, key in entries.items():
        counts[key] = counts.get(key, 0) + 1
        starts[key] = min(starts.get(key, point[travel_axis]), point[travel_axis])
    by_end: dict[int, list[_LeafKey]] = {}
    for key, count in counts.items():
        if count > 1:
            by_end.setdefault(owners[key][travel_axis], []).append(key)
    return by_end, starts


def _assign_shared_lanes(
    by_end: dict[int, list[_LeafKey]],
    starts: dict[_LeafKey, int],
    *,
    lane_axis: int,
) -> set[_LeafKey]:
    """Share lanes among earliest-ending classes, reusing a free lane.

    A lane carries one class at a time; overlapping classes stay
    unshared.
    """
    shared: set[_LeafKey] = set()
    occupied: dict[int, int] = {}
    for lane_end in sorted(by_end):
        for key in by_end[lane_end]:
            lane_coordinate = key.lane - _DIG_DIRECTIONS[key.heading][lane_axis]
            last = occupied.get(lane_coordinate)
            if last is None or starts[key] > last:
                shared.add(key)
                occupied[lane_coordinate] = lane_end
    return shared


def _plan_shared_lanes(
    entries: dict[_Point, _LeafKey],
    owners: dict[_LeafKey, _Point],
    *,
    lane_axis: int,
    travel_axis: int,
) -> dict[_LeafKey, _Point] | None:
    """Plan shared lanes for a dry-run tree; None when nothing can share."""
    by_end, starts = _sharing_lane_groups(entries, owners, travel_axis)
    shared = _assign_shared_lanes(by_end, starts, lane_axis=lane_axis)
    if not shared:
        return None
    # Leave unmatched copies painted, even if their contents coincide.
    return {key: owner for key, owner in owners.items() if key in shared}


class _AlternatingTree:
    """One alternating Dig tree being painted onto a grid.

    Holds the layout's configuration, derived once from the truth table,
    and every accumulator the painting phases share: the cells, the reads
    and corridors the clearance check verifies, and the sharing
    bookkeeping.  Each phase is a method so it can be read and tested on
    its own; :func:`_dig_layout` only orders them.
    """

    def __init__(
        self,
        truth_table: str,
        n: int,
        *,
        sharing: bool = False,
    ) -> None:
        self.n = n
        self.sharing = sharing
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
        ).box
        # Bounds of a subtree, inclusive and local to its first ``$``:
        # (min_x, max_x, min_y, max_y), x along the heading.  A branch block
        # is four cells long and carries its operand one cell off to a side
        # the heading picks, so it reaches one row past its own line.  A
        # level's skipped reads lengthen its block by one cell each.  A
        # constant span is a row of reads, and the children differ, so each
        # is bounded on its own: the one turned left lies on the -y side,
        # the one turned right on the +y side.
        self.boxes: dict[tuple[int, int], _Box] = {}
        self.cells: dict[_Point, str] = {}
        # Each reader against the cell it must read and the stores still
        # pending there, and the blank runs a mole falls along to a child.
        self.reads: list[tuple[_Point, _Point, frozenset[_Point]]] = []
        self.corridors: list[tuple[_Point, int, int]] = []
        self.entries: dict[_Point, _LeafKey] = {}
        self.owners: dict[_LeafKey, _Point] = {}

    def short_leaf(self, level: int, lo: int) -> str:
        """Return the constant span's read row for ``truth_table[lo]``."""
        return _dig_constant_leaf(
            self.n - self.consumed[level], int(self.truth_table[lo])
        )

    def box(self, level: int, lo: int, hi: int) -> _Box:
        """Return the memoized bounds of the ``[lo, hi)`` subtree."""
        key = (level, lo)
        if key not in self.boxes:
            if self.constant(lo, hi):
                self.boxes[key] = _Box(0, len(self.short_leaf(level, lo)) - 1, 0, 0)
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

    def text(self, point: _Point, heading: int, code: str) -> None:
        """Paint ``code`` from ``point`` along ``heading``."""
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
            self._place_child(level, end, heading, child_bit, child_bounds, paint=paint)

    def _paint_branch_block(
        self, point: _Point, heading: int, skip: int, end: _Point
    ) -> None:
        """Paint one ``$~;#`` block with its operand digit beside the ``$``.

        The operand digit sits one cell off the block.  Which side is
        forced -- a reader takes the first digit of up, right, down, left,
        so the operand goes on the lower-numbered of the two sides and a
        stray digit opposite it can never be read first.
        """
        side = _operand_side(heading)
        count = point.step(side)
        self.place(count, str(_DIG_COUNT + skip))
        self.reads.append((point, count, frozenset()))
        self.text(point, heading, _DIG_ALT_BRANCH[0] + "~" * skip + _DIG_ALT_BRANCH[1:])
        self.reads.append((end, end.step(heading, -1), frozenset()))

    def _place_child(
        self,
        level: int,
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
        distance = 2 - self.box(level + 1, *child_bounds).min_x
        child = end.step(child_heading, distance)
        if paint:
            self.corridors.append((end, child_heading, distance))
        self.node(level + 1, child, child_heading, *child_bounds, paint=paint)

    def paint(self) -> None:
        """Paint the whole tree with the root heading east."""
        self.node(0, _Point(0, 0), 1, 0, len(self.truth_table))

    def plan_sharing(self) -> bool:
        """Dry-run the tree and assign shared leaf lanes; False aborts."""
        self.node(0, _Point(0, 0), 1, 0, len(self.truth_table), paint=False)
        plan = _plan_shared_lanes(
            self.entries,
            self.owners,
            lane_axis=self.lane_axis,
            travel_axis=self.travel_axis,
        )
        if plan is None:
            return False
        self.owners = plan
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
        lane = owner.step(heading, -1)
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
                distance -= 1
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

    def compact_sharing(self) -> None:
        """Compact unused travel-axis rows/columns.

        Keep every internal blank in a leaf box; compact only the unused
        rows or columns between stamps, where the mole is overground.
        """
        coordinates = {
            at: i
            for i, at in enumerate(
                _compaction_lines(self.cells, self.reads, self.travel_axis)
            )
        }
        root = coordinates[0]

        def compact(point: _Point) -> _Point:
            return _compact_point(point, self.travel_axis, coordinates, root)

        self.cells = {compact(point): char for point, char in self.cells.items()}
        compact_reads = _remap_reads(self.reads, compact)
        compact_corridors = _remap_corridors(self.corridors, compact)
        # `_compaction_lines` guarantees this passes: no digit becomes a
        # reader's neighbour, and corridors and lane arrows cannot change.
        _dig_alt_clear(self.cells, compact_reads, compact_corridors)

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
) -> str | None:
    """Lay a Dig tree whose leaves are flat tables, branch axis rotating.

    The last six inputs are not branched on at all: a leaf holds their whole
    table as one rectangle of digits and indexes it with two counts (see
    :func:`_dig_flat_leaf`).  Children enter on the local y-axis, placed just
    beyond the parent's most-backward cell; width and height swap and one
    doubles per level, so the rectangle stays O(2**n).  An ignored input
    above the leaf is no level: its read rides the next block, ``$~~;#``.
    """
    tree = _AlternatingTree(truth_table, n, sharing=sharing)
    # Build locally with the root heading east.  Its ray from the west is
    # empty by the same bounds recurrence, so an external L-shaped entry can
    # reach it without crossing the tree.
    if sharing and not tree.plan_sharing():
        return None
    tree.paint()
    if sharing and not tree.bridge_entries():
        return None
    try:
        _dig_alt_clear(tree.cells, tree.reads, tree.corridors)
    except AssertionError:
        if sharing:
            return None
        raise
    if sharing:
        tree.compact_sharing()
    return tree.render()
