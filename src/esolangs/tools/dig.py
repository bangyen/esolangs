"""Boolean-function generator for Dig."""

from itertools import pairwise
from typing import cast

from esolangs.registry._language import Language
from esolangs.tools.dig_leaf import (
    _dig_adder as _dig_adder,
)
from esolangs.tools.dig_leaf import (
    _dig_flat_leaf as _dig_flat_leaf,
)
from esolangs.tools.dig_leaf import (
    _Reads,
)
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    read_at,
)
from esolangs.tools.wrap import balance_score

# Dig blocks for one level of the decision tree.  ``$`` takes its count
# from the digit beside it and looks up, right, down, left for one, so the
# count sits to the *right* of the ``$`` and the whole block is entered
# from the left: the count digit is itself the first of the commands it
# arms, which is why three covers a read and a store.
_DIG_BRANCH = "$3~;#"  # arm three, read a bit, store it, then turn on it


_DIG_PRINT = "{}:@"  # set the mole to the result and print it


# ``$`` reads its repeat count from the digit beside it, so a run of cells
# under one ``$`` is at most nine long.
_DIG_SPAN = 9


# Columns one level owns.  A block is five cells and its ``#`` is the last,
# so the child's ``>`` sits under that ``#`` -- which is the cell before the
# child's own block, and the stride is what puts it there.
_DIG_STRIDE = len(_DIG_BRANCH)


# A banded level leaves one column spare.  Six is what makes the two bands
# able to share columns at all: see :func:`_dig_columns`.
_DIG_BAND = _DIG_STRIDE + 1


# Offset of a block's ``#``, the cell its children attach under.
_DIG_LAST = _DIG_STRIDE - 1


# Cells a mole walking over them does not obey.  Everything else is
# scenery while the underground counter is at zero -- digits included,
# which is what lets a corridor cross a block's middle.
_DIG_OPAQUE = "^>'<#$@"


# Cells that hold a digit where a neighbouring ``$`` or ``#`` would find
# one.  ``;`` counts: it writes the mole into its own cell, so on the
# executed path it *is* a digit.
_DIG_DIGITS = "0123456789;"


def _render(cells: dict[tuple[int, int], str], *, dense: bool) -> str:
    """Paint ``cells`` into rows of text; ``dense`` keeps empty rows.

    Rows are painted into a rectangle of blanks, but the mole never walks
    past the last command on a row, so the trailing filler is inert and is
    trimmed rather than committed.
    """
    span = max(col for _, col in cells) + 1
    rows = (
        range(max(row for row, _ in cells) + 1)
        if dense
        else sorted({row for row, _ in cells})
    )
    index = {row: i for i, row in enumerate(rows)}
    grid = [[" "] * span for _ in rows]
    for (row, col), char in cells.items():
        grid[index[row]][col] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _dig_leaf(reads: int, value: int, *, aligned: bool) -> str:
    """Build a leaf that consumes ``reads`` inputs, then prints ``value``.

    ``$`` arms the cells after it as commands, up to nine per window; windows
    chain, a spent count arming the next ``$``.  ``aligned`` (banded layout)
    makes windows exactly ``_DIG_BAND`` long and pads the value to an odd
    offset from the ``$``, where the other band's ``$`` and ``#`` never look.
    """
    out = ""
    if not aligned:
        # Three cells of the last window are not reads: its count digit and
        # the two of ``_DIG_PRINT`` that precede the value.
        while reads > _DIG_SPAN - 3:
            take = min(_DIG_SPAN - 1, reads - (_DIG_SPAN - 3))
            out += f"${take + 1}" + "~" * take
            reads -= take
        return out + f"${reads + 3}" + "~" * reads + _DIG_PRINT.format(value)
    while reads > _DIG_BAND - 1:
        take = _DIG_BAND - 2
        out += f"${take + 1}" + "~" * take
        reads -= take
    pad = 1 - reads % 2
    tail = "~" * reads + " " * pad + _DIG_PRINT.format(value)
    return out + f"${reads + pad + 3}" + tail


def _dig_columns(strides: list[int], split: int | None) -> list[int]:
    """Return the ``$`` column of every level, the leaf's last, from the strides.

    A banded tree turns round once and the west band runs over the east
    band's columns, mirrored.  A ``$`` or ``#`` sits at block offset 0 or 4
    and confusable digits at 1 and 3, so with stride six a collision needs
    the bands' column difference ``d`` to be 0, 1, 2, 3 or 5 mod six; four is
    not, so ``d = 4 mod six`` clears all of them.  A second turn would put two
    bands the same way, differing by 0 mod six -- the case ``d`` must avoid.
    The west band is anchored at the leaf, whose ``$`` sits at column seven:
    one stride further back from the east band's last ``#`` makes ``d`` four.
    A level's skipped reads lengthen its stride, so only the one-band tree
    has any.
    """
    east = [1]
    for stride in strides:
        east.append(east[-1] + stride)
    if split is None:
        return east
    west = [7]
    for stride in reversed(strides[split:]):
        west.append(west[-1] + stride)
    return east[:split] + west[::-1]


def _dig_levels(essential: list[int], n: int) -> list[int]:
    """Return the inputs a tree branches on.

    The essential ones, and an ignored one only where a block's count digit
    cannot hold more skips.
    """
    if not essential:
        return list(range(n))
    levels: list[int] = []
    pending = 0
    for i in range(essential[-1] + 1):
        if i in essential or pending == _DIG_SPAN - 3:
            levels.append(i)
            pending = 0
        else:
            pending += 1
    return levels


def _dig_grid(
    truth_table: str, n: int, split: int | None, *, reduce: bool = True
) -> str:
    """Lay the decision tree out, in one band east or two that turn round.

    The one-band tree branches only on the essential inputs; an ignored one
    is read by the next block (``$5~~;#`` after one skipped read), or by the
    leaf.  The banded tree branches on every input: with a skip or a long
    leaf it left blocks the clearance check does not see (mole deaths at
    n=5, essential inputs (0, 2, 3, 4) and (0, 1, 2)).  ``reduce=False``
    branches on every input in either.
    """
    levels = list(range(n))
    if reduce and split is None:
        levels = _dig_levels(essential_inputs(truth_table, n), n)
    return _dig_lay(truth_table, n, split, levels)


def _dig_lay(truth_table: str, n: int, split: int | None, used: list[int]) -> str:
    """Lay the tree out branching on the inputs ``used``, reading the rest."""
    truth_table = read_at(truth_table, used, n)
    m = len(used)
    # Inputs read before level ``l``'s own block, its skips being the gap.
    consumed = [0, *(i + 1 for i in used)]
    skips = [used[level] - consumed[level] for level in range(m)]
    columns = _dig_columns(
        [(_DIG_STRIDE if split is None else _DIG_BAND) + skip for skip in skips],
        split,
    )
    total = 2 ** (m + 1) - 1
    constant = constant_span_test(truth_table)
    cells: dict[tuple[int, int], str] = {}
    corridors: list[tuple[int, int, int]] = []

    def leftward(level: int) -> bool:
        """Whether this level's block is entered facing west."""
        return split is not None and level >= split

    def dollar(level: int) -> int:
        """Return the column of this level's ``$``, the cell the mole meets first."""
        return columns[level]

    def place(row: int, col: int, text: str) -> None:
        """Write ``text`` along ``row`` from ``col``, refusing an occupied cell.

        An overwrite is one of the two ways a bad layout fails; :func:`_dig_clear`
        checks the other.
        """
        for i, char in enumerate(text):
            if col + i < 0:
                raise AssertionError(f"cell off the left edge at row {row}")
            if (row, col + i) in cells:
                raise AssertionError(f"two cells at {(row, col + i)}")
            cells[row, col + i] = char

    def block(row: int, level: int, text: str) -> None:
        """Write a block so the mole meets its first cell first."""
        col = dollar(level)
        if leftward(level):
            place(row, col - len(text) + 1, text[::-1])
        else:
            place(row, col, text)

    def walk(row: int, level: int, lo: int, hi: int) -> None:
        """Lay the subtree for ``truth_table[lo:hi]`` at ``row``."""
        if level == m or constant(lo, hi):
            # A constant slice cannot be told apart by more branching, so
            # this is a leaf and every row below it goes unwritten.  It
            # still reads what it did not branch on: a program whose input
            # count depended on its table would desync a caller feeding
            # several programs from one stream.
            reads = n - consumed[level]
            block(
                row,
                level,
                _dig_leaf(reads, int(truth_table[lo]), aligned=split is not None),
            )
            return
        skip = skips[level]
        block(row, level, f"${3 + skip}{'~' * skip}~;#")
        col = dollar(level)
        last = _DIG_LAST + skip
        hop = col - last if leftward(level) else col + last
        step = 2 ** (m - level - 1)
        half = (hi - lo) // 2
        # ``#`` rotates one way on a 0 and the other on a 1, so which child
        # is up and which is down follows the mole's heading: a bit that
        # sends an eastbound mole down sends a westbound one up.
        one, zero = (
            (row - step, row + step) if leftward(level) else (row + step, row - step)
        )
        for child, bounds in (
            (one, (lo + half, hi)),
            (zero, (lo, lo + half)),
        ):
            # the mole arrives here vertically from the parent's "#", which
            # is the cell right before the child's own block -- so the turn
            # goes in that column, pointing the way the child is entered
            place(child, hop, "<" if leftward(level + 1) else ">")
            corridors.append((hop, row, child))
            walk(child, level + 1, *bounds)

    # The mole starts at (0, 0) facing right, so the ``'`` below turns it
    # down column 0 and this is the cell that turns it back out of it.
    place(total // 2, columns[0] - 1, ">")
    walk(total // 2, 0, 0, 2**m)
    _dig_clear(cells, corridors)

    if (0, 0) in cells:
        raise AssertionError("the start marker's cell is taken")
    cells[0, 0] = "'"
    return _render(cells, dense=False)


def _dig_clear(
    cells: dict[tuple[int, int], str],
    corridors: list[tuple[int, int, int]],
) -> None:
    """Refuse a grid whose moles would be stopped on their way.

    A mole falling from ``#`` to its child meets every row between (only
    :data:`_DIG_OPAQUE` is scenery), and a ``$`` or ``#`` takes the first
    digit of up, right, down, left.  Checked against the grid, since the
    column rule is what places the cells.
    """
    for col, start, end in corridors:
        low, high = sorted((start, end))
        for row in range(low + 1, high):
            char = cells.get((row, col))
            if char is not None and char in _DIG_OPAQUE:
                raise AssertionError(
                    f"mole from row {start} meets {char!r} at {(row, col)}"
                )
    for (row, col), char in cells.items():
        if char not in "$#":
            continue
        for step in (-1, 1):
            above = cells.get((row + step, col))
            if above is not None and above in _DIG_DIGITS:
                raise AssertionError(f"{char!r} at {(row, col)} reads {above!r} first")


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
    truth_table: str, n: int, *, sharing: bool = False, parallel: bool = False
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
        return _dig_leaf(n - consumed[level], int(truth_table[lo]), aligned=False)

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
            key = (truth_table[lo:hi], heading, point[lane_axis])
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
        counts: dict[tuple[str, int, int], int] = {}
        starts: dict[tuple[str, int, int], int] = {}
        for point, key in entries.items():
            counts[key] = counts.get(key, 0) + 1
            starts[key] = min(starts.get(key, point[travel_axis]), point[travel_axis])
        by_end: dict[int, list[tuple[str, int, int]]] = {}
        for key, count in counts.items():
            if count > 1:
                by_end.setdefault(owners[key][travel_axis], []).append(key)
        shared = set()
        rails: dict[tuple[str, int, int], int] = {}
        occupied: dict[int, list[int | None]] = {}
        # Earliest-ending classes reuse either free lane. Two lanes need
        # one gutter cell; further overlapping classes stay unshared.
        for lane_end in sorted(by_end):
            for key in by_end[lane_end]:
                lane_coordinate = key[2] - _DIG_DIRECTIONS[key[1]][lane_axis]
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
        for point, key in entries.items():
            if key not in owners:
                continue
            heading = key[1]
            lane = step(point, heading, -1 - rails[key])
            if cells.get(lane, " ") != " ":
                return None
            owner = owners[key]
            cells[lane] = (
                "^>'<"[heading]
                if point == owner
                else "^>'<"[1 if travel_axis == 1 else 2]
            )
            lanes[point] = lane
        shortened = []
        for start, heading, distance in corridors:
            child = step(start, heading, distance)
            if child in lanes:
                distance -= 1 + rails[entries[child]]
            shortened.append((start, heading, distance))
        corridors = shortened
        by_position: dict[int, list[tuple[int, int]]] = {}
        for point in lanes:
            by_position.setdefault(point[travel_axis], []).append(point)
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


def _dig_alternating(truth_table: str, n: int) -> str:
    """Return the total unshared alternating layout."""
    return cast("str", _dig_layout(truth_table, n))


def _dig_lane_shared(truth_table: str, n: int) -> str | None:
    """Join aligned repeated leaves along spare rows or columns.

    Reject crossings and paths above the execution ledger. A six-bit leaf's
    worst walk is the sum of its adder, painter, selector and output legs.
    """
    return _dig_layout(truth_table, n, sharing=True) if n > 6 else None


def _dig_parallel_shared(truth_table: str, n: int) -> str | None:
    """Join interleaved leaf classes on two lanes separated by a gutter.

    Stretch branch counters around gutters, preserve rigid leaf stamps,
    and reject collisions or paths past the existing execution ledger.
    """
    return _dig_layout(truth_table, n, sharing=True, parallel=True) if n > 6 else None


def _dig_shared_pair(truth_table: str, n: int) -> str | None:
    """Share two distinct 64-entry leaves behind an eight-input prefix.

    The two 24-row leaves overlap one empty corner row. East and west
    prefix branches select the same leaves in opposite orders; their rays
    merge before either entry. Worst path: 60 prefix + 158 leaf commands.
    """
    if n != 8:
        return None
    blocks = [truth_table[i : i + 64] for i in range(0, 256, 64)]
    upper, lower = blocks[:2], blocks[2:]
    if upper[0] != upper[1]:
        a, b = upper
    elif lower[0] != lower[1]:
        b, a = lower
    else:
        return None  # only the first prefix bit matters
    if any(block not in (a, b) for block in blocks):
        return None
    if upper == lower:
        return None  # only the second prefix bit matters
    cells: dict[tuple[int, int], str] = {}
    reads: _Reads = []
    corridors: list[tuple[tuple[int, int], int, int]] = []

    def place(point: tuple[int, int], char: str) -> None:
        if point in cells:
            raise AssertionError(f"two cells at {point}")
        cells[point] = char

    for row, table in ((11, a), (34, b)):
        chars, spins, wants, _exit, _box = _dig_flat_leaf(table, [4, 2, 1], [4, 2, 1])

        def onto(point: tuple[int, int], row: int = row) -> tuple[int, int]:
            return point[0] + row, point[1] + 11

        for point, char in chars.items():
            place(onto(point), char)
        for point, heading in spins.items():
            place(onto(point), ">'<^"[heading])
        reads.extend(
            (onto(point), onto(want), frozenset(onto(p) for p in pending))
            for point, want, pending in wants
        )
    rays: list[tuple[tuple[int, int], int, int]] = []
    junctions: set[tuple[int, int]] = set()
    for row, col, heading, words in (
        (17, 1, 1, None),
        (14, 5, 1, upper),
        (24, 9, 3, lower),
    ):
        constant = words is not None and words[0] == words[1]
        code = "$~" if constant else _DIG_ALT_BRANCH
        d_col = _DIG_DIRECTIONS[heading][1]
        for offset, char in enumerate(code):
            place((row, col + d_col * offset), char)
        place((row - 1, col), "1" if constant else "2")
        reads.append(((row, col), (row - 1, col), frozenset()))
        if not constant:
            reads.append(((row, col + 3 * d_col), (row, col + 2 * d_col), frozenset()))
        if words is None:
            continue
        ray_col = col + len(code) * d_col if constant else col + 3 * d_col
        targets = (11 if words[0] == a else 34,) if constant else (11, 34)
        if constant:
            place((row, ray_col), "^" if targets[0] < row else "'")
        for target in targets:
            rays.append(((row, ray_col), 0 if target < row else 2, abs(target - row)))
            junctions.add((target, ray_col))
    # The lower branch enters from the east: its zero steers south to B.
    for point, char in (
        ((0, 0), "'"),
        ((17, 0), ">"),
        ((14, 4), ">"),
        ((26, 4), ">"),
        ((26, 10), "^"),
        ((24, 10), "<"),
    ):
        place(point, char)
    for point in junctions:
        place(point, ">")
    for row in (11, 34):
        cols = [*sorted(col for y, col in junctions if y == row), 11]
        corridors.extend(
            ((row, left), 1, right - left) for left, right in pairwise(cols)
        )
    corridors.extend(rays)
    corridors.extend(
        (
            ((0, 0), 2, 17),
            ((17, 0), 1, 1),
            ((17, 4), 0, 3),
            ((17, 4), 2, 9),
            ((14, 4), 1, 1),
            ((26, 4), 1, 6),
            ((26, 10), 0, 2),
            ((24, 10), 3, 1),
        )
    )
    _dig_alt_clear(cells, reads, corridors)
    return _render(cells, dense=True)


def _dig_quarter_turn(program: str) -> str:
    """Turn a grid clockwise with an external entry above its original origin."""
    rows = program.splitlines()
    height = len(rows)
    span = max(map(len, rows))
    arrows = str.maketrans("^>'<", ">'<^")
    grid = [[" "] * (height + 1) for _ in range(span + 1)]
    grid[0][height] = "'"
    for row, line in enumerate(rows):
        for col, char in enumerate(line):
            grid[col + 1][height - row] = char.translate(arrows)
    return "\n".join("".join(row).rstrip() for row in grid)


def _dig_xor_pair() -> str:
    """Compute a+b-2ab in four operand-sharing passes, with two input reads."""
    # Down the first column: read/store a and b. Up the second: copy b
    # into three cells, add a, store their sum. Down the third: copy the
    # sum twice, subtract b, multiply by b, and store ab three times.
    # The final climb starts with ab, subtracts its three stored copies,
    # adds the saved sum, and prints. Separating stores from readers
    # prevents the up/right/down/left operand priority selecting a copy.
    columns = (
        "'$~;  ~;   >",
        ">9;+ ;;;  $^",
        "'$;; -*;;;8>",
        "@8:+   ---$^",
    )
    return "\n".join(
        "".join(column[row] for column in columns).rstrip() for row in range(12)
    )


def _dig_discards(count: int, tail: str = "0") -> str:
    """Return a column reading and dropping ``count`` inputs, then ``tail``.

    Its ``'`` on the start cell turns the mole down it, and windows of eight
    reads chain below; the last window also arms ``tail``.  The default, an
    armed ``0``, clears the mole: the program below then meets it on its
    ``'`` facing down, carrying 0, nothing armed -- the state it has one
    step into a run of its own.
    """
    cells = "'"
    while count > _DIG_SPAN - 1 - len(tail):
        take = min(_DIG_SPAN - 1, count)
        cells += f"${take + 1}" + "~" * take
        count -= take
    cells += f"${count + 1 + len(tail)}" + "~" * count + tail
    return "\n".join(cells)


def dig(truth_table: str, width: int | None = None, *, share: bool = True) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Past
    four inputs the default stops branching six inputs short and gives each
    leaf their whole table as one rectangle of digits, indexed by two ``$``
    counts (:func:`_dig_flat_leaf`), keeping the area O(T).  ``width`` admits
    the unshared alternating layout when it fits, alongside the one- or
    two-band layouts (:func:`_dig_columns`); widths below the floor return
    the narrowest candidate; two-input XOR below width eight uses a
    four-column polynomial stencil.

    A constant span at any level is a row of reads and a print, its box sized
    alone (seeded n=7/8/9 area, one half constant: -14.7% / -20.0% / -25.4%;
    constant 64-entry blocks -12.3% / -34.2% / -24.3%; random unchanged).
    Aligned repeated leaves join along spare rows or columns, retaining the
    last copy and compacting unused external space. Paths must fit the execution
    ledger (n=8 A B B A: 1,155 cells, 208 commands). Narrow width paths can
    use the fixed two-leaf stencil (26 columns, at most 218 commands).
    Two parallel lanes admit interleaved classes (n=10: 5,175 cells,
    292 commands), stretching branch counters around their gutter.
    Groups whose corridors collide or exceed the bound remain unshared.
    """
    n = _validate_truth_table(truth_table)
    built = _dig_build(truth_table, n, width, share=share)
    essential = essential_inputs(truth_table, n)
    if width is None and not essential:
        # A constant reads every input down one column and prints.
        column = _dig_discards(n, truth_table[0] + ":") + "\n@"
        return min(built, column, key=len)
    if width is None and essential and 0 < essential[0] == n - len(essential):
        # Inputs before the first essential one can be read and dropped above
        # the smaller table's program, when that is shorter.
        inner = dig(read_at(truth_table, essential, n), share=share)
        return min(built, _dig_discards(essential[0]) + "\n" + inner, key=len)
    return built


def _dig_build(
    truth_table: str, n: int, width: int | None, *, share: bool = True
) -> str:
    """Return :func:`dig`'s layout for every table, ignored inputs included."""
    if width is not None and 0 < width < 8 and truth_table == "0110":
        return _dig_xor_pair()
    pair = _dig_shared_pair(truth_table, n) if share else None
    lane = _dig_lane_shared(truth_table, n) if share else None
    parallel = _dig_parallel_shared(truth_table, n) if share else None
    if width is None and n > 4:
        return min(
            filter(None, (pair, lane, parallel, _dig_alternating(truth_table, n))),
            key=len,
        )
    flat = _dig_grid(truth_table, n, None)
    if n < 2:
        return flat
    # The turn has to leave the westbound band room to finish left of where
    # the eastbound one starts its last block, which is what fixes the
    # split rather than any search: the halves are as even as that allows.
    banded = _dig_grid(truth_table, n, -(-(n + 2) // 2))
    if width is None:
        return min((flat, banded), key=len)
    if n <= 4:
        if grid_width(flat) <= width:
            return flat
        if grid_width(banded) <= width:
            return banded
    candidates = tuple(filter(None, (flat, banded, pair, lane, parallel)))
    fitting = [p for p in candidates if grid_width(p) <= width]
    if n > 4:
        # Width 40 used 11,250 banded cells on the n=8 repeated-leaf case;
        # the 35-column unshared layout needs 1,925.
        alternating = _dig_alternating(truth_table, n)
        if grid_width(alternating) <= width:
            fitting.append(alternating)
    if fitting:
        return min(fitting, key=len)
    # A bounded flat width keeps the rotated entry padding O(T).
    if n <= 4:
        candidates += (_dig_quarter_turn(flat),)
    # Equal-width narrow fallbacks still prefer the shorter route: the n=9
    # parity prefix otherwise kept 27,036 banded cells over 2,556 shared cells.
    return min(candidates, key=lambda program: (grid_width(program), len(program)))


def _balance(table: str, default: str) -> str:
    """Compare alternating, flat, banded and reachable narrow/affine routes."""
    n = _validate_truth_table(table)
    flat = _dig_grid(table, n, None)
    # The full tree stays: a reduced one can be less square.
    candidates = [
        default,
        dig(table, share=False),
        flat,
        _dig_grid(table, n, None, reduce=False),
        dig(table, 1),
        dig(table, 8),
    ]
    if n >= 2:
        banded = _dig_grid(table, n, (n + 3) // 2)
        if grid_width(banded) < grid_width(flat):
            candidates.append(banded)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Dig",
    "grid_based.dig",
    boolean=dig,
    split=True,
    balance=_balance,
    empty_program="Dig program cannot be empty",
)
