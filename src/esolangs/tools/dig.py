"""Boolean-function generator for Dig."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    narrowest_grid,
    read_at,
)

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


#: Local headings inside a stamp, as offsets into the block's own frame:
#: forward, sideways, back, and back the other way.  A stamp is laid in this
#: frame and rotated once, at placement, so the same cells serve all four
#: headings -- which works only because every operand below is the *one*
#: digit beside its operator, leaving the up-right-down-left order unused.
_DIG_FORWARD, _DIG_SIDE, _DIG_BACK, _DIG_RETRACE = 0, 1, 2, 3


#: Each reader's own cell, the operand it must reach, and the stores that
#: are still literal semicolons when it runs.
type _Reads = list[tuple[tuple[int, int], tuple[int, int], frozenset[tuple[int, int]]]]


#: A block laid in its own frame: cells, turns as local headings, the reads,
#: where the mole leaves, and the box as ``(min_x, max_x, min_y, max_y)``.
type _Stamp = tuple[
    dict[tuple[int, int], str],
    dict[tuple[int, int], int],
    _Reads,
    tuple[int, int],
    tuple[int, int, int, int],
]


def _dig_adder(weights: list[int], bonus: int) -> _Stamp:
    """Read one input per weight and leave their weighted sum plus ``bonus``.

    One ``$`` arms the whole forward leg: ``~ * ;`` per leading bit, then a
    bare ``~`` for the last, whose weight is one.  An ignored input weighs 0
    and is a bare ``~`` the next read overwrites, so it may not be last; at
    least one leading weight is nonzero.  The partial products stay
    in the grid where ``;`` wrote them, and the return leg one cell to the
    side adds them back -- a ``+`` under a ``;`` is the only placement that
    puts a stored operand where the mole can reach it, since a work command
    reads its neighbours and never the cell it stands on.

    ``bonus`` rides the forward leg instead, added straight onto the first
    product: the return leg's own operands come from the row above it, and
    that row is the forward leg, so a constant there would be armed.  The
    two leaves' counts index from different offsets -- a row count clears
    the ``$`` that arms it and the blank under it, a column count nothing --
    which is the whole reason this is a parameter.

    Returns the cells, the turns as local headings, the operand each reader
    must find, where the mole leaves heading back, and the bounding box.
    """
    chars: dict[tuple[int, int], str] = {}
    reads: _Reads = []
    stores: list[int] = []
    spot = 1
    for weight in weights[:-1]:
        chars[0, spot] = "~"
        spot += 1
        if not weight:
            continue
        chars[0, spot], chars[-1, spot] = "*", str(weight)
        reads.append(((0, spot), (-1, spot), frozenset({(0, spot + 1)})))
        spot += 1
        if bonus and not stores:
            chars[0, spot], chars[-1, spot] = "+", str(bonus)
            reads.append(((0, spot), (-1, spot), frozenset({(0, spot + 1)})))
            spot += 1
        chars[0, spot] = ";"
        stores.append(spot)
        spot += 1
    chars[0, spot] = "~"  # the last bit, whose weight is one
    chars[-1, 0], chars[0, 0] = str(spot), "$"
    reads.insert(0, ((0, 0), (-1, 0), frozenset[tuple[int, int]]()))
    # The return leg's count sits one past the armed run, so the mole walks
    # over it with the counter spent and it stays a plain digit.
    hold, first = spot + 1, stores[0]
    chars[0, hold], chars[1, hold] = str(hold - first), "$"
    reads.append(((1, hold), (0, hold), frozenset()))
    for store in stores:
        chars[1, store] = "+"
        reads.append(((1, store), (0, store), frozenset()))
    turns = {(0, hold + 1): _DIG_SIDE, (1, hold + 1): _DIG_BACK}
    return chars, turns, reads, (1, first - 1), (0, hold + 1, -1, 1)


def _dig_flat_leaf(table: str, high: list[int], low: list[int]) -> _Stamp:
    """Index ``table`` by two adders instead of branching on its bits.

    The first ``high`` inputs become a row count, painted across a whole row
    so that whichever column the mole ends on finds it; the next ``low``
    become a column count, which steps the mole over that many ``'`` cells
    before one turns it into the table.  A ``$`` arming a run of digits
    leaves the *last* digit it walked in the mole, so the armed run down a
    column ends on the wanted entry and nothing else has to fetch it.

    The mole crosses the table twice -- painting on the first pass, reading
    on the second -- so the two adders sit on opposite sides of it and three
    corridor columns carry the mole between them: one in, one down to the
    paint row, one back up to the selector.
    """
    rows, cols = sum(high) + 1, sum(low) + 1
    painter, stepper = _dig_adder(high, 2), _dig_adder(low, 0)
    chars: dict[tuple[int, int], str] = {}
    turns: dict[tuple[int, int], int] = {}
    # Rows the leaf spends, counted from the entry: three for each adder,
    # the table's own band, and the corridors that join them.  The entry
    # sits at the middle so the box the tree reserves is not lopsided.
    top = 1 - (rows + 14) // 2
    sel = top + 3
    bot = sel + rows + 9
    back = bot + 2
    last = sel + rows
    reads: _Reads = []

    def stamp(row: int, col: int, block: _Stamp) -> tuple[int, int]:
        cells, spins, wants, exit_at, _box = block
        chars.update({(row + y, col + x): c for (y, x), c in cells.items()})
        turns.update({(row + y, col + x): d for (y, x), d in spins.items()})
        reads.extend(
            (
                (row + point[0], col + point[1]),
                (row + want[0], col + want[1]),
                frozenset((row + y, col + x) for y, x in hold),
            )
            for point, want, hold in wants
        )
        return row + exit_at[0], col + exit_at[1]

    turns[0, 0] = _DIG_RETRACE  # climb to the first adder
    turns[top, 0] = _DIG_FORWARD
    turns[stamp(top, 3, painter)[0], 2] = _DIG_SIDE
    turns[sel + 1, 2] = _DIG_FORWARD  # into the paint row
    chars[sel + 1, 4], chars[sel + 1, 5] = str(cols), "$"
    reads.append(((sel + 1, 5), (sel + 1, 4), frozenset({(sel + 1, 6)})))
    # The selector: store the column count, then step over that many turns.
    turns[sel, 1] = _DIG_FORWARD
    chars[sel - 1, 3], chars[sel, 3] = "1", "$"
    chars[sel, 4], chars[sel, 5] = ";", "$"
    reads.append(((sel, 3), (sel - 1, 3), frozenset({(sel, 4)})))
    reads.append(((sel, 5), (sel, 4), frozenset()))
    for col in range(cols):
        turns[sel, 6 + col] = _DIG_SIDE
        chars[sel + 1, 6 + col] = ";"
        chars[sel + 2, 6 + col] = "$"
        reads.append(((sel + 2, 6 + col), (sel + 1, 6 + col), frozenset()))
        for row in range(rows):
            chars[sel + 4 + row, 6 + col] = table[row * cols + col]
        turns[last + 4, 6 + col] = _DIG_BACK
    turns[last + 4, 5] = _DIG_SIDE
    chars[last + 5, 5], chars[last + 5, 6] = "$", "1"
    chars[last + 6, 5], chars[last + 7, 5] = ":", "@"
    reads.append(((last + 5, 5), (last + 5, 6), frozenset()))
    # Down the far side, back along the bottom, and up into the second
    # adder; then up the near side into the selector.
    # The far corridor clears the second adder's exit turns: a narrow
    # table would put them on it.
    far = max(6 + cols, 4 + stepper[4][1])
    turns[sel + 1, far] = _DIG_SIDE
    turns[back, far] = _DIG_BACK
    turns[back, 2] = _DIG_RETRACE
    turns[bot, 2] = _DIG_FORWARD
    turns[stamp(bot, 3, stepper)[0], 1] = _DIG_RETRACE
    width = max(far, 3 + painter[4][1])
    return chars, turns, reads, (0, 0), (0, width, top - 1, back)


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


def _dig_alternating(truth_table: str, n: int) -> str:
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

    def text(point: tuple[int, int], heading: int, code: str) -> None:
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
        for row in range(min_y, max_y + 1):
            for col in range(min_x, max_x + 1):
                spot = onto((row, col))
                place(spot, painted.get(spot, " "))
        reads.extend(
            (onto(at), onto(want), frozenset(onto(c) for c in hold))
            for at, want, hold in wants
        )

    def node(
        level: int,
        point: tuple[int, int],
        heading: int,
        lo: int,
        hi: int,
    ) -> None:
        if constant(lo, hi):
            code = short_leaf(level, lo)
            text(point, heading, code)
            reads.extend(
                (step(point, heading, i), step(point, heading, i + 1), frozenset())
                for i, char in enumerate(code)
                if char == "$"
            )
            return
        if level == depth:
            leaf(point, heading, truth_table[lo:hi])
            return
        # The operand digit sits one cell off the block.  Which side is
        # forced -- a reader takes the first digit of up, right, down, left,
        # so the operand goes on the lower-numbered of the two sides and a
        # stray digit opposite it can never be read first.
        side = min((heading + 1) % 4, (heading - 1) % 4)
        count = step(point, side)
        skip = skips[level]
        place(count, str(_DIG_COUNT + skip))
        reads.append((point, count, frozenset()))
        text(point, heading, _DIG_ALT_BRANCH[0] + "~" * skip + _DIG_ALT_BRANCH[1:])
        end = step(point, heading, _DIG_END + skip)
        reads.append((end, step(end, heading, -1), frozenset()))
        half = (lo + hi) // 2
        # Two cells off, not one: a leaf reaches far enough sideways that
        # its box, turned a quarter, would otherwise land on this block's
        # own operand.  The spare cell is corridor the mole falls through.
        for child_bit, child_bounds in ((0, (lo, half)), (1, (half, hi))):
            child_heading = (heading + (1 if child_bit else -1)) % 4
            distance = 2 - box(level + 1, *child_bounds)[0]
            corridors.append((end, child_heading, distance))
            child = step(end, child_heading, distance)
            node(level + 1, child, child_heading, *child_bounds)

    # Build locally with the root heading east.  Its ray from the west is
    # empty by the same bounds recurrence, so an external L-shaped entry can
    # reach it without crossing the tree.
    node(0, (0, 0), 1, 0, len(truth_table))
    _dig_alt_clear(cells, reads, corridors)
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


def _area(program: str) -> int:
    """Rows times the longest row, the cost a grid is judged by."""
    return (program.count("\n") + 1) * grid_width(program)


def dig(truth_table: str, width: int | None = None) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Past
    four inputs the default stops branching six inputs short and gives each
    leaf their whole table as one rectangle of digits, indexed by two ``$``
    counts (:func:`_dig_flat_leaf`), keeping the area O(T).  ``width`` keeps
    the one- or two-band layouts (:func:`_dig_columns`), the narrower
    returned when under the floor; two-input XOR below width eight uses a
    four-column polynomial stencil.

    A constant span at any level is a row of reads and a print, its box sized
    alone (seeded n=7/8/9 area, one half constant: -14.7% / -20.0% / -25.4%;
    constant 64-entry blocks -12.3% / -34.2% / -24.3%; random unchanged).
    Repeated flat leaves are not shared: open.
    """
    n = _validate_truth_table(truth_table)
    built = _dig_build(truth_table, n, width)
    essential = essential_inputs(truth_table, n)
    if width is None and not essential:
        # A constant reads every input down one column and prints.
        column = _dig_discards(n, truth_table[0] + ":") + "\n@"
        return min(built, column, key=_area)
    if width is None and essential and 0 < essential[0] == n - len(essential):
        # Inputs before the first essential one can be read and dropped above
        # the smaller table's program, when that is shorter.
        inner = dig(read_at(truth_table, essential, n))
        return min(built, _dig_discards(essential[0]) + "\n" + inner, key=len)
    return built


def _dig_build(truth_table: str, n: int, width: int | None) -> str:
    """Return :func:`dig`'s layout for every table, ignored inputs included."""
    if width is not None and 0 < width < 8 and truth_table == "0110":
        return _dig_xor_pair()
    if width is None and n > 4:
        return _dig_alternating(truth_table, n)
    flat = _dig_grid(truth_table, n, None)
    if n < 2:
        return flat
    # The turn has to leave the westbound band room to finish left of where
    # the eastbound one starts its last block, which is what fixes the
    # split rather than any search: the halves are as even as that allows.
    banded = _dig_grid(truth_table, n, -(-(n + 2) // 2))
    if width is None:
        return min((flat, banded), key=len)
    if grid_width(flat) <= width:
        return flat
    if grid_width(banded) <= width:
        return banded
    candidates: tuple[str, ...] = (flat, banded)
    # A bounded flat width keeps the rotated entry padding O(T).
    if n <= 4:
        candidates += (_dig_quarter_turn(flat),)
    return narrowest_grid(*candidates)
