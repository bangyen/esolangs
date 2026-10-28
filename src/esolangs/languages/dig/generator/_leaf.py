"""Flat lookup stamps for the Dig generator."""

from dataclasses import dataclass, field
from typing import NamedTuple

# A reader's count comes from one adjacent digit.
_DIG_SPAN = 9
_DIG_PRINT = "{}:@"
# The turn glyph that sends a mole along each heading, indexed by heading
# (up, right, down, left), and the same glyphs rotated a quarter turn clockwise.
_DIG_TURNS = "^>'<"
_DIG_TURNS_CW = _DIG_TURNS[1:] + _DIG_TURNS[0]
_DIG_OPAQUE = _DIG_TURNS + "#$@"
_DIG_DIGITS = "0123456789;"

#: Local headings rotate with the stamp. Each operator has one adjacent
#: operand, so rotation cannot change which digit it reads.
_DIG_FORWARD, _DIG_SIDE, _DIG_BACK, _DIG_RETRACE = 0, 1, 2, 3


#: Each reader's own cell, the operand it must reach, and the stores that
#: are still literal semicolons when it runs.
type _Reads = list[tuple[tuple[int, int], tuple[int, int], frozenset[tuple[int, int]]]]


class _Box(NamedTuple):
    """Inclusive bounds local to a block's first cell, x along its heading."""

    min_x: int
    max_x: int
    min_y: int
    max_y: int


class _Stamp(NamedTuple):
    """A block laid in its own frame.

    ``spins`` are turns as local headings, ``exit`` is where the mole leaves,
    and ``box`` bounds the block.
    """

    cells: dict[tuple[int, int], str]
    spins: dict[tuple[int, int], int]
    wants: _Reads
    exit: tuple[int, int]
    box: _Box


#: First column of the table band, right of the three corridor columns.
_TABLE_COL = 6


def _hold_column(chars: dict[tuple[int, int], str]) -> int:
    """Return the right-most ``$`` on row 1, where the hold count is stored."""
    return max(c for (r, c), char in chars.items() if r == 1 and char == "$")


def _dig_adder(weights: list[int], bonus: int) -> _Stamp:
    """Read one input per weight and leave their weighted sum plus ``bonus``.

    One ``$`` arms the whole forward leg: ``~ * ;`` per leading bit, then a
    bare ``~`` for the last, whose weight is one.  An ignored input weighs 0
    and is a bare ``~`` the next read overwrites.  Trailing ignored inputs
    store the last bit too (``~ ;``, weight one) and are read on the return
    leg, which has its own count, before a ``*`` beside a ``0`` zeroes the
    mole.  At least one leading weight is nonzero.  The partial products stay
    in the grid where ``;`` wrote them, and the return leg one cell to the side adds
    them back: a ``+`` under a ``;`` is the only placement that puts a stored
    operand where the mole can reach it, since a work command reads its
    neighbours, never its own cell.

    ``bonus`` rides the forward leg, added straight onto the first product:
    the return leg's operands come from the row above it, which is the
    forward leg, so a constant there would be armed.  The two leaves' counts
    index from different offsets (a row count clears the arming ``$`` and the
    blank under it, a column count nothing), hence the parameter.

    Returns the cells, the turns as local headings, the operand each reader
    must find, where the mole leaves heading back, and the bounding box.
    """
    builder = _AdderBuilder(weights, bonus)
    builder.forward_leg()
    return builder.finish(builder.start_return())


@dataclass
class _AdderBuilder:
    """The state one adder stamp accumulates: cells, reads and stores."""

    weights: list[int]
    bonus: int
    chars: dict[tuple[int, int], str] = field(default_factory=dict)
    reads: _Reads = field(default_factory=list)
    stores: list[int] = field(default_factory=list)
    spot: int = 1
    trailing: int = 0

    def forward_leg(self) -> None:
        """Paint the eastbound leg: one read (and store) per leading weight."""
        weights, chars = self.weights, self.chars
        while not weights[-1 - self.trailing]:
            self.trailing += 1
        end = len(weights) - self.trailing if self.trailing else -1
        lead = weights[:end]
        for weight in lead:
            chars[0, self.spot] = "~"
            self.spot += 1
            if not weight:
                continue
            if weight > 1:
                self._operand("*", str(weight))
            if self.bonus and not self.stores:
                self._operand("+", str(self.bonus))
            chars[0, self.spot] = ";"
            self.stores.append(self.spot)
            self.spot += 1

    def _operand(self, operator: str, digit: str) -> None:
        """Paint one operator with its operand digit below, and record the read."""
        spot = self.spot
        self.chars[0, spot], self.chars[-1, spot] = operator, digit
        self.reads.append(((0, spot), (-1, spot), frozenset({(0, spot + 1)})))
        self.spot += 1

    def start_return(self) -> int:
        """Paint the last forward read; return the return leg's ``hold`` column."""
        chars, reads = self.chars, self.reads
        if self.trailing:
            self.spot -= 1
            # The return leg runs west from ``hold``: the ignored reads, then a
            # ``*`` under a ``0`` past the forward leg's armed run.
            zero = self.spot + 1
            hold = zero + self.trailing + 1
            chars[0, zero], chars[1, zero] = "0", "*"
            reads.append(((1, zero), (0, zero), frozenset()))
            for cell in range(zero + 1, hold):
                chars[1, cell] = "~"
            return hold
        chars[0, self.spot] = "~"  # the last bit, whose weight is one
        # The return leg's count sits one past the armed run, so the mole
        # walks over it with the counter spent and it stays a plain digit.
        return self.spot + 1

    def finish(self, hold: int) -> _Stamp:
        """Paint both legs' counts and the return leg's adds over the stores."""
        chars, reads = self.chars, self.reads
        chars[-1, 0], chars[0, 0] = str(self.spot), "$"
        reads.insert(0, ((0, 0), (-1, 0), frozenset[tuple[int, int]]()))
        first = self.stores[0]
        chars[0, hold], chars[1, hold] = str(hold - first), "$"
        reads.append(((1, hold), (0, hold), frozenset()))
        for store in self.stores:
            chars[1, store] = "+"
            reads.append(((1, store), (0, store), frozenset()))
        turns = {(0, hold + 1): _DIG_SIDE, (1, hold + 1): _DIG_BACK}
        return _Stamp(chars, turns, reads, (1, first - 1), _Box(0, hold + 1, -1, 1))


def _dig_adder_fits(weights: list[int], bonus: int) -> bool:
    """Whether both legs' counts are one digit."""
    stamp = _dig_adder(weights, bonus)
    hold = stamp.box.max_x - 1
    return len(stamp.cells[-1, 0]) == 1 and len(stamp.cells[0, hold]) == 1


def _dig_flat_leaf(
    table: str, high: list[int], low: list[int], *, classes: int = 1
) -> _Stamp:
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
    _check_shared_stamp(table, high, low, classes)
    rows, cols = classes * (sum(high) + 1), sum(low) + 1
    builder = _FlatLeafBuilder(
        table,
        classes,
        painter=_dig_adder(high, 2),
        stepper=_dig_adder(low, 0),
        geometry=_FlatGeometry.landmarks(rows, cols, classes),
    )
    return builder.build()


def _check_shared_stamp(
    table: str, high: list[int], low: list[int], classes: int
) -> None:
    """Refuse a shared stamp that is not six-bit classes with digit labels."""
    if classes > 1 and (
        high != [4, 2, 1]
        or low != [4, 2, 1]
        or not 2 <= classes <= 10
        or len(table) != 64 * classes
    ):
        raise AssertionError("shared stamps require six-bit classes and digit labels")


@dataclass(frozen=True)
class _FlatGeometry:
    """The flat leaf's row landmarks, counted from its entry row.

    Three rows for each adder, the table's own band, and the corridors
    that join them.  The entry sits at the middle of a single-class leaf
    so the box the tree reserves is not lopsided.
    """

    rows: int
    cols: int
    top: int
    sel: int
    bot: int
    back: int
    last: int

    @classmethod
    def landmarks(cls, rows: int, cols: int, classes: int) -> "_FlatGeometry":
        """Derive every landmark from the table band's size and class count."""
        top = 0 if classes > 1 else 1 - (rows + 14) // 2
        sel = top + 3 + int(classes > 1)
        return cls(rows, cols, top, sel, sel + rows + 9, sel + rows + 11, sel + rows)


@dataclass
class _FlatLeafBuilder:
    """The state one flat leaf accumulates: cells, turns and reads."""

    table: str
    classes: int
    painter: _Stamp
    stepper: _Stamp
    geometry: _FlatGeometry
    chars: dict[tuple[int, int], str] = field(default_factory=dict)
    turns: dict[tuple[int, int], int] = field(default_factory=dict)
    reads: _Reads = field(default_factory=list)
    width: int = 0

    def build(self) -> _Stamp:
        """Run the painting phases in entry-to-exit order and stamp the leaf."""
        geo = self.geometry
        self._place_painter()
        self._paint_row_reader()
        self._selector_and_table()
        self._output_tail()
        self._corridors_and_stepper()
        if self.classes > 1:
            self._capture_shared_offset()
        box = _Box(0, self.width, geo.top - 1, geo.back)
        return _Stamp(self.chars, self.turns, self.reads, (0, 0), box)

    def stamp(self, row: int, col: int, block: _Stamp) -> tuple[int, int]:
        """Copy one adder stamp in at ``(row, col)``; return its exit point."""
        cells, spins, wants, exit_at, _ = block
        self.chars.update({(row + y, col + x): c for (y, x), c in cells.items()})
        self.turns.update({(row + y, col + x): d for (y, x), d in spins.items()})
        self.reads.extend(
            (
                (row + point[0], col + point[1]),
                (row + want[0], col + want[1]),
                frozenset((row + y, col + x) for y, x in hold),
            )
            for point, want, hold in wants
        )
        return row + exit_at[0], col + exit_at[1]

    def _place_painter(self) -> None:
        """Enter, climb to the painter adder and drop into the paint row."""
        geo, turns = self.geometry, self.turns
        if self.classes == 1:
            turns[0, 0] = _DIG_RETRACE  # climb to the first adder
        turns[geo.top, 0] = _DIG_FORWARD
        turns[self.stamp(geo.top, 3, self.painter)[0], 2] = _DIG_SIDE
        turns[geo.sel + 1, 2] = _DIG_FORWARD  # into the paint row

    def _paint_row_reader(self) -> None:
        """Paint the row count beside the ``$`` that arms the paint row."""
        geo = self.geometry
        self.chars[geo.sel + 1, 4], self.chars[geo.sel + 1, 5] = str(geo.cols), "$"
        self.reads.append(
            ((geo.sel + 1, 5), (geo.sel + 1, 4), frozenset({(geo.sel + 1, _TABLE_COL)}))
        )

    def _selector_and_table(self) -> None:
        """Paint the selector, then the table band column by column."""
        geo, chars, turns = self.geometry, self.chars, self.turns
        # The selector: store the column count, then step over that many turns.
        turns[geo.sel, 1] = _DIG_FORWARD
        chars[geo.sel - 1, 3], chars[geo.sel, 3] = "1", "$"
        chars[geo.sel, 4], chars[geo.sel, 5] = ";", "$"
        self.reads.append(((geo.sel, 3), (geo.sel - 1, 3), frozenset({(geo.sel, 4)})))
        self.reads.append(((geo.sel, 5), (geo.sel, 4), frozenset()))
        for col in range(geo.cols):
            turns[geo.sel, _TABLE_COL + col] = _DIG_SIDE
            chars[geo.sel + 1, _TABLE_COL + col] = ";"
            chars[geo.sel + 2, _TABLE_COL + col] = "$"
            self.reads.append(
                (
                    (geo.sel + 2, _TABLE_COL + col),
                    (geo.sel + 1, _TABLE_COL + col),
                    frozenset(),
                )
            )
            for row in range(geo.rows):
                chars[geo.sel + 4 + row, _TABLE_COL + col] = self.table[
                    row * geo.cols + col
                ]
            turns[geo.last + 4, _TABLE_COL + col] = _DIG_BACK

    def _output_tail(self) -> None:
        """Paint the print-and-halt tail below the table's far corner."""
        geo, chars = self.geometry, self.chars
        self.turns[geo.last + 4, 5] = _DIG_SIDE
        chars[geo.last + 5, 5], chars[geo.last + 5, _TABLE_COL] = "$", "1"
        chars[geo.last + 6, 5], chars[geo.last + 7, 5] = ":", "@"
        self.reads.append(((geo.last + 5, 5), (geo.last + 5, _TABLE_COL), frozenset()))

    def _corridors_and_stepper(self) -> None:
        """Paint the far/bottom corridors and the stepper adder; set the width."""
        geo, turns = self.geometry, self.turns
        # Down the far side, back along the bottom, and up into the second
        # adder; then up the near side into the selector.
        # The far corridor clears the second adder's exit turns: a narrow
        # table would put them on it.
        far = max(_TABLE_COL + geo.cols, 4 + self.stepper.box.max_x)
        turns[geo.sel + 1, far] = _DIG_SIDE
        turns[geo.back, far] = _DIG_BACK
        turns[geo.back, 2] = _DIG_RETRACE
        turns[geo.bot, 2] = _DIG_FORWARD
        turns[self.stamp(geo.bot, 3, self.stepper)[0], 1] = _DIG_RETRACE
        self.width = max(far, 3 + self.painter.box.max_x)

    def _capture_shared_offset(self) -> None:
        """Capture eight rows per class before the final six inputs are read.

        The extra return command adds that stored offset to the row count.
        """
        geo, chars, painter = self.geometry, self.chars, self.painter
        first = painter.exit[1]
        hold = _hold_column(painter.cells)
        chars[geo.top, 3 + hold] = str(hold - first)
        chars[geo.top + 1, 3 + first] = "+"
        self.reads.append(
            ((geo.top + 1, 3 + first), (geo.top + 2, 3 + first), frozenset())
        )
        chars.update({(2, 8): "$", (2, 7): "*", (2, 6): ";", (2, 9): "2", (3, 7): "8"})
        self.turns[2, 1], self.turns[0, 1] = _DIG_RETRACE, _DIG_FORWARD
        pending = frozenset({(2, 6)})
        self.reads.extend((((2, 8), (2, 9), pending), ((2, 7), (3, 7), pending)))


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


def _dig_constant_leaf(reads: int, value: int) -> str:
    """Consume all inputs through single-digit windows, then print value."""
    out = ""
    while reads > _DIG_SPAN - 3:
        take = min(_DIG_SPAN - 1, reads - (_DIG_SPAN - 3))
        out += f"${take + 1}" + "~" * take
        reads -= take
    return out + f"${reads + 3}" + "~" * reads + _DIG_PRINT.format(value)
