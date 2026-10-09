"""Alternating tree layouts and bounded sharing routes for Dig."""

from esolangs.tools.dig_leaf import (
    _DIG_DIGITS,
    _DIG_OPAQUE,
    _DIG_SPAN,
    _dig_adder,
    _dig_constant_leaf,
    _dig_flat_leaf,
    _Reads,
    _render,
)
from esolangs.tools.helpers import constant_span_test, essential_inputs, read_at

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


def _dig_alt_clear(
    cells: dict[tuple[int, int], str],
    reads: _Reads,
    corridors: list[tuple[tuple[int, int], int, int]],
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
            beside = (point[0] + offset[0], point[1] + offset[1])
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
            char = cells.get(
                (
                    start[0] + _DIG_DIRECTIONS[heading][0] * count,
                    start[1] + _DIG_DIRECTIONS[heading][1] * count,
                )
            )
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


def _dig_layout(
    truth_table: str,
    n: int,
    *,
    sharing: bool = False,
    parallel: bool = False,
    offset: bool = False,
) -> str | None:
    """Lay a Dig tree whose leaves are flat tables, branch axis rotating.

    The last six inputs are not branched on at all: a leaf holds their whole
    table as one rectangle of digits and indexes it with two counts (see
    :func:`_dig_flat_leaf`).  Children enter on the local y-axis, placed just
    beyond the parent's most-backward cell; width and height swap and one
    doubles per level, so the rectangle stays O(2**n).  An ignored input
    above the leaf is no level: its read rides the next block, ``$~~;#``.
    """
    high, low, skips, truth_table = _dig_leaf_inputs(truth_table, n)
    depth = len(skips)
    lane_axis = 0 if depth % 2 else 1
    travel_axis = 1 - lane_axis
    constant = constant_span_test(truth_table)
    # Inputs read before each level's block; a constant span reads the rest.
    consumed = [0]
    for skip in skips:
        consumed.append(consumed[-1] + 1 + skip)
    flat_box = _dig_flat_leaf("0" * (len(truth_table) >> depth), high, low)[4]

    def short_leaf(level: int, lo: int) -> str:
        return _dig_constant_leaf(n - consumed[level], int(truth_table[lo]))

    # Bounds of a subtree, inclusive and local to its first ``$``: (min_x,
    # max_x, min_y, max_y), x along the heading.  A branch block is four
    # cells long and carries its operand one cell off to a side the heading
    # picks, so it reaches one row past its own line.  A level's skipped
    # reads lengthen its block by one cell each.  A constant span is a row of
    # reads, and the children differ, so each is bounded on its own: the one
    # turned left lies on the -y side, the one turned right on the +y side.
    boxes: dict[tuple[int, int], tuple[int, int, int, int]] = {}

    def box(level: int, lo: int, hi: int) -> tuple[int, int, int, int]:
        if (level, lo) not in boxes:
            if constant(lo, hi):
                boxes[level, lo] = (0, len(short_leaf(level, lo)) - 1, 0, 0)
            elif level == depth:
                boxes[level, lo] = flat_box
            else:
                half = (lo + hi) // 2
                left, right = box(level + 1, lo, half), box(level + 1, half, hi)
                end = _DIG_END + skips[level]
                boxes[level, lo] = (
                    min(0, end + left[2], end - right[3]),
                    max(end, end + left[3], end - right[2]),
                    min(-1, -(2 - left[0] + left[1])),
                    max(1, 2 - right[0] + right[1]),
                )
        return boxes[level, lo]

    cells: dict[tuple[int, int], str] = {}
    protected: list[tuple[int, int]] = []
    branches: list[tuple[tuple[int, int], int, int, tuple[int, int]]] = []
    # Each reader against the cell it must read and the stores still
    # pending there, and the blank runs a mole falls along to a child.
    reads: _Reads = []
    corridors: list[tuple[tuple[int, int], int, int]] = []

    def place(point: tuple[int, int], char: str) -> None:
        if point in cells:
            raise AssertionError(f"two cells at {point}: {cells[point]!r} and {char!r}")
        cells[point] = char

    def step(point: tuple[int, int], heading: int, count: int = 1) -> tuple[int, int]:
        d_row, d_col = _DIG_DIRECTIONS[heading]
        return (point[0] + d_row * count, point[1] + d_col * count)

    def text(
        point: tuple[int, int], heading: int, code: str, *, rigid: bool = True
    ) -> None:
        if parallel and rigid:
            protected.append(
                (point[lane_axis], step(point, heading, len(code) - 1)[lane_axis])
            )
        for offset, char in enumerate(code):
            place(step(point, heading, offset), char)

    def leaf(point: tuple[int, int], heading: int, table: str) -> None:
        """Rotate one flat leaf onto the grid, blanks and all.

        The blanks are placed rather than left out: they are the corridors
        the leaf walks, and placing them makes any stray tree cell inside
        the reserved box a collision instead of a silent detour.
        """
        chars, spins, wants, _exit, box = _dig_flat_leaf(table, high, low)
        forward = _DIG_DIRECTIONS[heading]
        sideways = _DIG_DIRECTIONS[(heading + 1) % 4]

        def onto(cell: tuple[int, int]) -> tuple[int, int]:
            row, col = cell
            return (
                point[0] + col * forward[0] + row * sideways[0],
                point[1] + col * forward[1] + row * sideways[1],
            )

        painted = {onto(cell): char for cell, char in chars.items()}
        painted |= {onto(c): "^>'<"[(heading + d) % 4] for c, d in spins.items()}
        min_x, max_x, min_y, max_y = box
        if parallel:
            protected.append(
                (onto((min_y, min_x))[lane_axis], onto((max_y, max_x))[lane_axis])
            )
        for row in range(min_y, max_y + 1):
            for col in range(min_x, max_x + 1):
                spot = onto((row, col))
                place(spot, painted.get(spot, " "))
        reads.extend(
            (onto(at), onto(want), frozenset(onto(c) for c in hold))
            for at, want, hold in wants
        )

    entries: dict[tuple[int, int], tuple[str, int, int]] = {}
    owners: dict[tuple[str, int, int], tuple[int, int]] = {}
    links: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = []
    tails: dict[tuple[int, int], int] = {}

    def node(
        level: int,
        point: tuple[int, int],
        heading: int,
        lo: int,
        hi: int,
        *,
        paint: bool = True,
    ) -> None:
        if constant(lo, hi):
            if not paint:
                return
            code = short_leaf(level, lo)
            if sharing:
                tails[point] = len(code)
            text(point, heading, code)
            reads.extend(
                (step(point, heading, i), step(point, heading, i + 1), frozenset())
                for i, char in enumerate(code)
                if char == "$"
            )
            return
        if level == depth:
            key = (truth_table[lo:hi], heading, 0 if offset else point[lane_axis])
            if not paint:
                entries[point] = key
                if key not in owners or point[travel_axis] > owners[key][travel_axis]:
                    owners[key] = point
            elif not sharing or key not in owners or point == owners[key]:
                leaf(point, heading, truth_table[lo:hi])
            return
        # The operand digit sits one cell off the block.  Which side is
        # forced -- a reader takes the first digit of up, right, down, left,
        # so the operand goes on the lower-numbered of the two sides and a
        # stray digit opposite it can never be read first.
        skip = skips[level]
        end = step(point, heading, _DIG_END + skip)
        if paint:
            if parallel:
                branches.append((point, heading, skip, end))
            side = min((heading + 1) % 4, (heading - 1) % 4)
            count = step(point, side)
            skip = skips[level]
            place(count, str(_DIG_COUNT + skip))
            reads.append((point, count, frozenset()))
            text(
                point,
                heading,
                _DIG_ALT_BRANCH[0] + "~" * skip + _DIG_ALT_BRANCH[1:],
                rigid=False,
            )
            reads.append((end, step(end, heading, -1), frozenset()))
        half = (lo + hi) // 2
        # Two cells off, not one: a leaf reaches far enough sideways that
        # its box, turned a quarter, would otherwise land on this block's
        # own operand.  The spare cell is corridor the mole falls through.
        for child_bit, child_bounds in ((0, (lo, half)), (1, (half, hi))):
            child_heading = (heading + (1 if child_bit else -1)) % 4
            distance = 2 - box(level + 1, *child_bounds)[0]
            child = step(end, child_heading, distance)
            if paint:
                corridors.append((end, child_heading, distance))
                if sharing:
                    links.append((point, end, child))
            node(level + 1, child, child_heading, *child_bounds, paint=paint)

    # Build locally with the root heading east.  Its ray from the west is
    # empty by the same bounds recurrence, so an external L-shaped entry can
    # reach it without crossing the tree.
    if sharing:
        node(0, (0, 0), 1, 0, len(truth_table), paint=False)
        if offset:
            # Pick the existing entry nearest the callers' bounding-box
            # center, with coordinate ties fixed. This is one geometric
            # rule, not a route search; crossed rays still fail clearance.
            grouped: dict[tuple[str, int, int], list[tuple[int, int]]] = {}
            for point, key in entries.items():
                grouped.setdefault(key, []).append(point)
            for key, points in grouped.items():
                middle = tuple(
                    min(p[i] for p in points) + max(p[i] for p in points)
                    for i in range(2)
                )
                owners[key] = min(
                    points,
                    key=lambda p: (
                        sum(abs(2 * p[i] - middle[i]) for i in range(2)),
                        p[travel_axis],
                        p[lane_axis],
                    ),
                )
        counts: dict[tuple[str, int, int], int] = {}
        starts: dict[tuple[str, int, int], int] = {}
        ends: dict[tuple[str, int, int], int] = {}
        for point, key in entries.items():
            counts[key] = counts.get(key, 0) + 1
            starts[key] = min(starts.get(key, point[travel_axis]), point[travel_axis])
            ends[key] = max(ends.get(key, point[travel_axis]), point[travel_axis])
        by_end: dict[int, list[tuple[str, int, int]]] = {}
        for key, count in counts.items():
            if count > 1:
                by_end.setdefault(
                    ends[key] if offset else owners[key][travel_axis],
                    [],
                ).append(key)
        shared = set()
        rails: dict[tuple[str, int, int], int] = {}
        occupied: dict[int, list[int | None]] = {}
        # Earliest-ending classes reuse either free lane. Two lanes need
        # one gutter cell; further overlapping classes stay unshared.
        for lane_end in sorted(by_end):
            for key in by_end[lane_end]:
                lane_coordinate = (
                    owners[key][lane_axis] if offset else key[2]
                ) - _DIG_DIRECTIONS[key[1]][lane_axis]
                busy = occupied.setdefault(
                    lane_coordinate, [None] * (2 if parallel else 1)
                )
                for rail, last in enumerate(busy):
                    if last is None or starts[key] > last:
                        shared.add(key)
                        rails[key] = rail
                        busy[rail] = lane_end
                        break
        if not shared:
            return None
        if offset and not any(
            point[lane_axis] != owners[key][lane_axis]
            for point, key in entries.items()
            if key in shared
        ):
            return None
        # Leave unmatched copies painted, even if their contents coincide.
        owners = {key: owner for key, owner in owners.items() if key in shared}
        if parallel:
            cuts = sorted(
                {
                    key[2] + int(_DIG_DIRECTIONS[key[1]][lane_axis] < 0)
                    for key, rail in rails.items()
                    if rail
                }
            )
            if not cuts:
                return None
    node(0, (0, 0), 1, 0, len(truth_table))
    if parallel:
        low_axis = min(point[lane_axis] for point in cells)
        high_axis = max(point[lane_axis] for point in cells)
        root_offset = sum(cut <= 0 for cut in cuts)
        coordinates = {}
        shift = 0
        for position in range(low_axis, high_axis + 1):
            while shift < len(cuts) and cuts[shift] <= position:
                shift += 1
            coordinates[position] = position + shift - root_offset
        # A blank inside an armed leaf or constant read run would spend
        # its counter. Gutters may cross only the resizable branch blocks.
        if any(
            abs(coordinates[a] - coordinates[b]) != abs(a - b) for a, b in protected
        ):
            return None

        def expand(point: tuple[int, int]) -> tuple[int, int]:
            return (
                (coordinates[point[0]], point[1])
                if lane_axis == 0
                else (point[0], coordinates[point[1]])
            )

        # Repaint a stretched branch with its reads first and its store
        # beside #. The counter includes the intervening blank cells.
        branch_readers: set[tuple[int, int]] = set()
        for point, heading, skip, end in branches:
            side = min((heading + 1) % 4, (heading - 1) % 4)
            del cells[step(point, side)]
            for i in range(_DIG_END + skip + 1):
                del cells[step(point, heading, i)]
            branch_readers.update((point, end))
        cells = {expand(point): char for point, char in cells.items()}
        reads = [
            (expand(at), expand(want), frozenset(expand(p) for p in hold))
            for at, want, hold in reads
            if at not in branch_readers
        ]
        for point, heading, skip, end in branches:
            first, stop = expand(point), expand(end)
            distance = abs(first[0] - stop[0]) + abs(first[1] - stop[1])
            if not _DIG_COUNT + skip <= distance - 1 <= _DIG_SPAN:
                return None
            side = min((heading + 1) % 4, (heading - 1) % 4)
            count_point = step(first, side)
            if count_point in cells:
                return None
            cells[count_point] = str(distance - 1)
            code = "$" + "~" * (skip + 1) + " " * (distance - skip - 3) + ";#"
            for i, char in enumerate(code):
                target = step(first, heading, i)
                if target in cells:
                    return None
                cells[target] = char
            reads.append((first, count_point, frozenset()))
            reads.append((stop, step(stop, heading, -1), frozenset()))
        expanded_corridors = []
        for start, heading, distance in corridors:
            begin, finish = expand(start), expand(step(start, heading, distance))
            expanded_corridors.append(
                (begin, heading, abs(begin[0] - finish[0]) + abs(begin[1] - finish[1]))
            )
        corridors = expanded_corridors
        entries = {expand(point): key for point, key in entries.items()}
        owners = {key: expand(point) for key, point in owners.items()}
        links = [
            (expand(parent), expand(end), expand(child)) for parent, end, child in links
        ]
        tails = {expand(point): cost for point, cost in tails.items()}
    lanes: dict[tuple[int, int], tuple[int, int]] = {}
    if sharing:
        # Opposing headings bridge on opposite sides of their entry ray.
        # The centered owner can lie behind a caller, so the cross-bank
        # heading follows the displacement rather than the leaf heading.
        bridges: list[tuple[tuple[int, int], int, int]] = []
        for point, key in entries.items():
            if key not in owners:
                continue
            heading = key[1]
            owner = owners[key]
            local = step(point, heading, -1)
            lane = step(owner, heading, -1 - (0 if offset else rails[key]))
            lane = (point[0], lane[1]) if lane_axis == 1 else (lane[0], point[1])
            travel_heading = (
                (1 if travel_axis == 1 else 2)
                if point[travel_axis] <= owner[travel_axis]
                else (3 if travel_axis == 1 else 0)
            )
            if offset and point[lane_axis] != owner[lane_axis]:
                bridge_heading = (
                    (1 if travel_axis == 1 else 2)
                    if heading in (1, 2)
                    else (3 if travel_axis == 1 else 0)
                )
                corner = step(local, bridge_heading)
                lane = (corner[0], lane[1]) if lane_axis == 1 else (lane[0], corner[1])
                cross_heading = (
                    heading
                    if (lane[lane_axis] - corner[lane_axis])
                    * _DIG_DIRECTIONS[heading][lane_axis]
                    > 0
                    else (heading + 2) % 4
                )
                for spot, char in (
                    (local, "^>'<"[bridge_heading]),
                    (corner, "^>'<"[cross_heading]),
                ):
                    if spot in cells:
                        return None
                    cells[spot] = char
                distance = abs(corner[lane_axis] - lane[lane_axis])
                bridges.append((corner, cross_heading, distance))
            if lane in cells:
                return None
            if offset and point[lane_axis] != owner[lane_axis]:
                travel_heading = (
                    (1 if travel_axis == 1 else 2)
                    if lane[travel_axis] <= owner[travel_axis]
                    else (3 if travel_axis == 1 else 0)
                )
            cells[lane] = "^>'<"[heading] if point == owner else "^>'<"[travel_heading]
            lanes[point] = lane
        shortened = []
        for start, heading, distance in corridors:
            child = step(start, heading, distance)
            if child in lanes:
                distance -= 1 if offset else 1 + rails[entries[child]]
            shortened.append((start, heading, distance))
        corridors = shortened + bridges
        by_position: dict[int, list[tuple[int, int]]] = {}
        for point in lanes:
            by_position.setdefault(lanes[point][travel_axis], []).append(point)
        previous: dict[tuple[str, int, int], tuple[int, int]] = {}
        for position in sorted(by_position):
            for point in by_position[position]:
                key, lane = entries[point], lanes[point]
                if key in previous:
                    start = previous[key]
                    corridors.append(
                        (
                            start,
                            1 if travel_axis == 1 else 2,
                            lane[travel_axis] - start[travel_axis],
                        )
                    )
                previous[key] = lane
    try:
        _dig_alt_clear(cells, reads, corridors)
    except AssertionError:
        if sharing:
            return None
        raise
    if sharing:
        # Keep every internal blank in a leaf box; compact only the unused
        # rows or columns between stamps, where the mole is overground.
        coordinates = {
            at: i for i, at in enumerate(sorted({p[travel_axis] for p in cells}))
        }
        root = coordinates[0]

        def compact(point: tuple[int, int]) -> tuple[int, int]:
            return (
                (coordinates[point[0]] - root, point[1])
                if travel_axis == 0
                else (point[0], coordinates[point[1]] - root)
            )

        cells = {compact(point): char for point, char in cells.items()}
        compact_reads = [
            (compact(at), compact(want), frozenset(compact(p) for p in pending))
            for at, want, pending in reads
        ]
        compact_corridors = []
        for start, heading, distance in corridors:
            finish = compact(step(start, heading, distance))
            begin = compact(start)
            distance = abs(finish[0] - begin[0]) + abs(finish[1] - begin[1])
            compact_corridors.append((begin, heading, distance))
        # Compaction can make a previously distant digit a reader's neighbour.
        try:
            _dig_alt_clear(cells, compact_reads, compact_corridors)
        except AssertionError:
            return None
        costs = {(0, 0): 0}
        for parent, end, child in links:
            p, e, c = compact(parent), compact(end), compact(child)
            costs[child] = (
                costs[parent]
                + abs(p[0] - e[0])
                + abs(p[1] - e[1])
                + abs(e[0] - c[0])
                + abs(e[1] - c[1])
            )
        row_count, col_count = sum(high) + 1, sum(low) + 1
        painter = _dig_adder(high, 2)[4][1] - 1
        stepper = _dig_adder(low, 0)[4][1] - 1
        far = max(6 + col_count, 5 + stepper)
        # Sum the flat stamp's walking legs. Only the selected column
        # changes their length; its maximum is col_count - 1. Data digits
        # affect the printed answer, never the route.
        leaf_cost = (
            (row_count + 14) // 2
            - 1
            + 2 * (painter + stepper + far)
            + 3 * row_count
            + 2 * (col_count - 1)
            + 48
        )
        worst = max((costs[p] + cost for p, cost in tails.items()), default=0)
        for point, key in entries.items():
            travel = 0
            if key in owners:
                travel = abs(
                    compact(point)[travel_axis] - compact(owners[key])[travel_axis]
                )
            if offset and key in owners:
                travel += abs(point[lane_axis] - owners[key][lane_axis])
                if point[lane_axis] != owners[key][lane_axis] and (
                    (point[travel_axis] >= owners[key][travel_axis])
                    if key[1] in (1, 2)
                    else (point[travel_axis] <= owners[key][travel_axis])
                ):
                    travel += 2
            worst = max(worst, costs[point] + travel + leaf_cost)
        entry_cost = 4 - min(row for row, _ in cells) - min(col for _, col in cells)
        bound = 128 + (
            46 * 2 ** ((n - 6) // 2) if n % 2 == 0 else 64 * 2 ** ((n - 7) // 2)
        )
        if entry_cost + worst > bound:
            return None
    min_row = min(row for row, _ in cells)
    min_col = min(col for _, col in cells)
    row_shift, col_shift = 2 - min_row, 2 - min_col
    cells = {
        (row + row_shift, col + col_shift): char for (row, col), char in cells.items()
    }
    root_row, root_col = row_shift, col_shift
    if any(cells.get((root_row, col), " ") != " " for col in range(root_col)):
        raise AssertionError("the alternating Dig tree blocked its entry ray")
    for row in range(root_row):
        cells[(row, 0)] = " "
    for col in range(root_col):
        cells[(root_row, col)] = " "
    cells[(0, 0)] = "'"
    cells[(root_row, 0)] = ">"

    return _render(cells, dense=True)
