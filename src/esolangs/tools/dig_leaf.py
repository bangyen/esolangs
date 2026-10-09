"""Flat lookup stamps for the Dig generator."""

#: Local headings rotate with the stamp. Each operator has one adjacent
#: operand, so rotation cannot change which digit it reads.
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
