"""Boolean-function generator for Dig."""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

# Dig blocks for one level of the decision tree.  ``$`` takes its count
# from the digit beside it and looks up, right, down, left for one, so the
# count sits to the *right* of the ``$`` and the whole block is entered
# from the left: the count digit is itself the first of the commands it
# arms, which is why three covers a read and a store.
_DIG_BRANCH = "$3~;#"  # arm three, read a bit, store it, then turn on it


_DIG_ENTER = ">"  # the root's turn out of the column the mole starts down


_DIG_CONTINUE = ">"  # a child of a branch: keep facing right into its block


_DIG_RETURN = "<"  # the same, for a child the mole reaches facing west


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


# Cells a mole walking over them does not obey.  Everything else is
# scenery while the underground counter is at zero -- digits included,
# which is what lets a corridor cross a block's middle.
_DIG_OPAQUE = "^>'<#$@"


# Cells that hold a digit where a neighbouring ``$`` or ``#`` would find
# one.  ``;`` counts: it writes the mole into its own cell, so on the
# executed path it *is* a digit.
_DIG_DIGITS = "0123456789;"


def _dig_leaf(reads: int, value: int, *, aligned: bool) -> str:
    """Build a leaf that consumes ``reads`` inputs, then prints ``value``.

    ``$`` arms the cells after it as commands, up to nine per window; windows
    chain, a spent count arming the next ``$``.  ``aligned`` (banded layout)
    makes windows exactly ``_DIG_BAND`` long and pads the value to an odd
    offset from the ``$``, where the other band's ``$`` and ``#`` never look.
    """
    out = ""
    if not aligned:
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


def _dig_columns(n: int, split: int | None) -> tuple[int, int]:
    """Where the two bands start, or the one band if ``split`` is ``None``.

    A banded tree turns round once and the west band runs over the east
    band's columns, mirrored.  A ``$`` or ``#`` sits at block offset 0 or 4
    and confusable digits at 1 and 3, so with stride six a collision needs
    the bands' column difference ``d`` to be 0, 1, 2, 3 or 5 mod six; four is
    not, so ``d = 4 mod 6`` clears all of them.  A second turn would put two
    bands the same way, differing by 0 mod six -- the case ``d`` must avoid.
    """
    if split is None:
        return 1, 0
    # The west band ends four columns short of where the east band's last
    # ``#`` stands, which is the cell the mole turns west from; putting it
    # one stride further back is what makes ``d`` four modulo six.
    return 1, _DIG_BAND * (n - split) + 3


def _dig_grid(truth_table: str, n: int, split: int | None) -> str:
    """Lay the decision tree out, in one band east or two that turn round."""
    total = 2 ** (n + 1) - 1
    constant = constant_span_test(truth_table)
    east, west = _dig_columns(n, split)
    cells: dict[tuple[int, int], str] = {}
    corridors: list[tuple[int, int, int]] = []

    def leftward(level: int) -> bool:
        """Whether this level's block is entered facing west."""
        return split is not None and level >= split

    def dollar(level: int) -> int:
        """Return the column of this level's ``$``, the cell the mole meets first."""
        if split is None:
            return east + _DIG_STRIDE * level
        if level < split:
            return east + _DIG_BAND * level
        return west + 4 - _DIG_BAND * (level - split)

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
        if level == n or constant(lo, hi):
            # A constant slice cannot be told apart by more branching, so
            # this is a leaf and every row below it goes unwritten.  It
            # still reads what it did not branch on: a program whose input
            # count depended on its table would desync a caller feeding
            # several programs from one stream.
            reads = n - level
            block(
                row,
                level,
                _dig_leaf(reads, int(truth_table[lo]), aligned=split is not None),
            )
            return
        block(row, level, _DIG_BRANCH)
        col = dollar(level)
        hop = col - 4 if leftward(level) else col + 4
        step = 2 ** (n - level - 1)
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
            place(child, hop, _DIG_RETURN if leftward(level + 1) else _DIG_CONTINUE)
            corridors.append((hop, row, child))
            walk(child, level + 1, *bounds)

    # The mole starts at (0, 0) facing right, so the ``'`` below turns it
    # down column 0 and this is the cell that turns it back out of it.
    place(total // 2, east - 1, _DIG_ENTER)
    walk(total // 2, 0, 0, 2**n)
    _dig_clear(cells, corridors)

    if (0, 0) in cells:
        raise AssertionError("the start marker's cell is taken")
    cells[0, 0] = "'"
    span = max(col for _, col in cells) + 1
    rows = sorted({row for row, _ in cells})
    grid = [[" "] * span for _ in rows]
    row_index = {row: i for i, row in enumerate(rows)}
    for (row, col), char in cells.items():
        grid[row_index[row]][col] = char
    # Rows are painted into a rectangle of blanks, but the mole never walks
    # past the last command on a row, so the trailing filler is inert and is
    # trimmed rather than committed.
    return "\n".join("".join(row).rstrip() for row in grid)


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
_DIG_COUNT = "2"


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


def _dig_adder(bits: int, bonus: int) -> _Stamp:
    """Read ``bits`` inputs and leave their value plus ``bonus`` in the mole.

    One ``$`` arms the whole forward leg: ``~ * ;`` per leading bit, then a
    bare ``~`` for the last, whose weight is one.  The partial products stay
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
    for index in range(bits - 1):
        chars[0, spot] = "~"
        weight = spot + 1
        chars[0, weight] = "*"
        chars[-1, weight] = str(1 << (bits - 1 - index))
        reads.append(((0, weight), (-1, weight), frozenset({(0, weight + 1)})))
        spot = weight + 1
        if bonus and not index:
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


def _dig_flat_leaf(table: str, high: int, low: int) -> _Stamp:
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
    rows, cols = 1 << high, 1 << low
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
    turns[sel + 1, 6 + cols] = _DIG_SIDE
    turns[back, 6 + cols] = _DIG_BACK
    turns[back, 2] = _DIG_RETRACE
    turns[bot, 2] = _DIG_FORWARD
    turns[stamp(bot, 3, stepper)[0], 1] = _DIG_RETRACE
    width = max(6 + cols, 3 + max(painter[4][1], stepper[4][1]))
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


def _dig_alternating(truth_table: str, n: int) -> str:
    """Lay a Dig tree whose leaves are flat tables, branch axis rotating.

    The last six inputs are not branched on at all: a leaf holds their whole
    table as one rectangle of digits and indexes it with two counts (see
    :func:`_dig_flat_leaf`), so the tree above it is a sixty-fourth the size
    the per-entry tree was.  Children enter on the local y-axis, placed just
    beyond the parent's most-backward cell; width and height swap and one
    doubles per level, so the rectangle stays O(2**n).
    """
    leaf_bits = min(_DIG_LEAF_BITS, n)
    low = leaf_bits // 2
    high = leaf_bits - low
    depth = n - leaf_bits
    # Bounds of a complete m-level subtree, inclusive and local to its first
    # ``$``: (min_x, max_x, min_y, max_y), x along the heading.  A branch
    # block is four cells long and carries its operand one cell off to a
    # side the heading picks, so it reaches one row past its own line.
    bounds = [_dig_flat_leaf("0" * (1 << leaf_bits), high, low)[4]]
    for _ in range(depth):
        min_x, max_x, min_y, max_y = bounds[-1]
        distance = 2 - min_x
        bounds.append(
            (
                min(0, _DIG_END + min_y, _DIG_END - max_y),
                max(_DIG_END, _DIG_END + max_y, _DIG_END - min_y),
                min(-1, -(distance + max_x)),
                max(1, distance + max_x),
            )
        )

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
        if level == depth:
            leaf(point, heading, truth_table[lo:hi])
            return
        # The operand digit sits one cell off the block.  Which side is
        # forced -- a reader takes the first digit of up, right, down, left,
        # so the operand goes on the lower-numbered of the two sides and a
        # stray digit opposite it can never be read first.
        side = min((heading + 1) % 4, (heading - 1) % 4)
        count = step(point, side)
        place(count, _DIG_COUNT)
        reads.append((point, count, frozenset()))
        text(point, heading, _DIG_ALT_BRANCH)
        end = step(point, heading, _DIG_END)
        reads.append((end, step(end, heading, -1), frozenset()))
        half = (lo + hi) // 2
        # Two cells off, not one: a leaf reaches far enough sideways that
        # its box, turned a quarter, would otherwise land on this block's
        # own operand.  The spare cell is corridor the mole falls through.
        distance = 2 - bounds[depth - level - 1][0]
        for child_bit, child_bounds in ((0, (lo, half)), (1, (half, hi))):
            child_heading = (heading + (1 if child_bit else -1)) % 4
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

    height = max(row for row, _ in cells) + 1
    width = max(col for _, col in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (row, col), char in cells.items():
        grid[row][col] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def dig(truth_table: str, width: int | None = None) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Past
    four inputs the default stops branching six inputs short and gives each
    leaf their whole table as one rectangle of digits, indexed by two ``$``
    counts (:func:`_dig_flat_leaf`); the tree above it alternates the branch
    axis, so the area stays O(T) at 7.2 characters an entry rather than the
    29.5 a per-entry tree cost.  ``width`` keeps the one- or two-band
    layouts, the narrower returned when under the floor.  The mole starts
    top-left facing down; each branch block reads a bit (``~``), stores it
    (``;``) and ``#`` turns on it, and in the band layouts a constant
    subtree becomes a leaf whose rows are never written.  A level of those
    costs five columns, and under ``5 * n + 6`` the tree turns round once
    (:func:`_dig_columns`).
    """
    n = _validate_truth_table(truth_table)
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
    if max(len(line) for line in flat.split("\n")) <= width:
        return flat
    if max(len(line) for line in banded.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return banded
    return flat
