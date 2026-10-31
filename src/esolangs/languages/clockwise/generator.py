"""Clockwise Boolean program generator: a flat indexed lookup on a ring.

One ``!`` per entry in a row of ``!``/``-`` pairs, a Horner-rule index (MSB
first) in the accumulator, and one doubling gadget per input (widths double
upward).  An ignored input's seven reads run just before the next indexed
input's, which overwrite the bit they leave; inputs past the last essential
one are read on the return rail after printing.  A literal row has no
subtrees to fold or share.  Constants read a full input rotation, clear the
accumulator and emit the seven answer bits on a closed two-column ring.  A
``width`` exceeded rotates the program counterclockwise (two columns for
n <= 2, else ``2*n + 5``).  ``balance`` may instead split the table into
strips the first inputs select (:func:`_clockwise_banded`): n=6 random
184 -> 106 on a side, n=9 1107 -> 270.  The default is
:func:`_clockwise_flat`, which lays the gadgets in one band
(five rows, ``5T + 8n + 4`` wide): area ``25T + 40n + 20`` where the stack
costs ``(2T + 9n + 2)(2n + 15)`` ([ablations.flat_band]).

Size:
    O(T) cells; n=8 random 1847: 6,223 chars, n=10 random 1847: 23,967 chars,
    n=12 random 1847: 94,703 chars.
"""

from math import ceil
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_area,
    grid_width,
    read_at,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

# The ring's own columns: 3 descends at the start, 2 climbs into the first
# gadget, 0 climbs home.  Column 1 is the gap that keeps the three apart.
_DESCENT = 3
_CLIMB = 2

# A head is a corner, a gap the descent crosses, seven ``.`` for one input's
# value bit (more where ignored inputs precede it), and the gap the return
# leg climbs -- the next gadget's corner, so the head width is the pitch too.
_READS = 7

# The stacked lookup table occupies rows 1 to 5; row 0 is the entry descent.
_TABLE_ROWS = 5

# The six digit bits both answers share: 0110000 and 0110001 differ in the
# last only.  ``S`` opens the run because the descent crosses a read.
_DIGIT = "S;+;;+;;;S"


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program prints ``'0'`` or ``'1'``.
    """
    total = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _constant_ring(total, truth_table[0])
    used = essential_inputs(truth_table, total)
    if len(used) == 1:
        return _coordinate_ring(total, used[0], truth_table[0])
    return _clockwise_program(truth_table, width)


def _constant_ring(inputs: int, bit: str, width: int = 2) -> str:
    """Place constant reads/output on a rectangular ring with three turns."""
    commands = "." * (_READS * inputs) + _DIGIT[:-1] + "+" * int(bit) + ";"
    return _command_ring(commands, width)


def _coordinate_ring(
    inputs: int, position: int, complement: str, width: int = 2
) -> str:
    """Print the selected bit before consuming the remaining input rotation."""
    commands = (
        _DIGIT
        + "." * (_READS * (position + 1))
        + "+" * int(complement)
        + ";"
        + "." * (_READS * (inputs - position - 1))
    )
    return _command_ring(commands, width)


def _command_ring(commands: str, width: int) -> str:
    """Place a straight command sequence on a closed clockwise perimeter."""
    height = max(2, ceil((len(commands) + 7 - 2 * width) / 2))
    grid = [[" "] * width for _ in range(height)]
    for x, y in ((width - 1, 0), (width - 1, height - 1), (0, height - 1)):
        grid[y][x] = "R"
    positions = (
        [(x, 0) for x in range(width - 1)]
        + [(width - 1, y) for y in range(1, height - 1)]
        + [(x, height - 1) for x in range(width - 2, 0, -1)]
        + [(0, y) for y in range(height - 2, 0, -1)]
    )
    if len(positions) < len(commands):
        raise AssertionError("constant ring has too few command cells")
    for (x, y), command in zip(positions, commands, strict=False):
        grid[y][x] = command
    return "\n".join("".join(row).rstrip() for row in grid)


class _Grid:
    """Sparse character grid with collision-checked placement."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], str] = {}

    def place(self, x: int, y: int, char: str) -> None:
        """Write ``char`` at ``(x, y)``, refusing an occupied cell."""
        if (x, y) in self.cells:
            raise AssertionError(
                f"two cells at {(x, y)}: {self.cells[(x, y)]!r}, {char!r}"
            )
        self.cells[(x, y)] = char

    def lay_head(self, corner_x: int, y: int, head_reads: int) -> None:
        """Lay a gadget's corner and the reads that follow it."""
        self.place(corner_x, y, "R")
        for i in range(head_reads):
            self.place(corner_x + 2 + i, y, ".")

    def height(self) -> int:
        """Return the number of rows the placed cells occupy."""
        return max(y for _, y in self.cells) + 1

    def span(self) -> int:
        """Return the number of columns the placed cells occupy."""
        return max(x for x, _ in self.cells) + 1

    def render(self) -> str:
        """Join rows into text, stripping trailing filler.

        The interpreter pads short rows, so trailing filler is never reached.
        """
        grid = [[" "] * self.span() for _ in range(self.height())]
        for (x, y), char in self.cells.items():
            grid[y][x] = char
        return "\n".join("".join(row).rstrip() for row in grid)


class _Layout(NamedTuple):
    """A laid-out lookup: its cells, input counts, digit-tail row and shift."""

    grid: _Grid
    inputs: int
    n: int
    digit: int
    return_gap: int


def _clockwise_flat(truth_table: str) -> str:
    """Lay the gadgets in one two-row band, each east of the last: O(T) area.

    Gadget ``l`` returns west and climbs.  Instead of the next head above it,
    the pointer climbs one row more, runs east over the gadget's top, drops
    past its east end, turns back under it and climbs into the next head on
    the same two rows, so the stack of ``n`` gadget rows becomes one band.
    The digit run opens row 0.  Rows: 0 start and wire, 1-2 gadgets, 3 wire
    dip, 1-4 table.  Trailing inputs are read on the return row west of the
    table, or down a left rail when that stretch is too short.
    """
    total = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, total)
    trailing = total - used[-1] - 1
    indexed = read_at(truth_table, used, total)
    reads = _head_widths(total, used)
    # The table starts east of the digit run, every head and every gadget.
    corner = len(_DIGIT) - 1
    start = corner + sum(r + 1 + 3 * 2 ** (i + 1) for i, r in enumerate(reads[:-1]))
    start += reads[-1] + 3
    on_return = _READS * trailing < start
    top = 1 if on_return or not trailing else _READS * trailing - 1
    grid = _Grid()
    for i, char in enumerate(_DIGIT):
        grid.place(i, 0, char)
    grid.place(corner + 1, 0, "R")
    # The descent is column corner + 1; the U-turn closes under the first head.
    grid.place(corner + 1, top + 2, "R")
    grid.place(corner, top + 2, "R")

    for level, count in enumerate(reads[:-1]):
        grid.lay_head(corner, top, count)
        base = corner + count + 3
        groups = 1 << (level + 1)
        grid.place(base - 1, top + 1, "R")
        for group in range(groups):
            grid.place(base + 3 * group, top, "!")
            grid.place(base + 3 * group, top + 1, "!")
            if group + 1 < groups:
                grid.place(base + 3 * group + 1, top, "-")
                grid.place(base + 3 * group + 1, top + 1, "+")
                grid.place(base + 3 * group + 2, top + 1, "+")
        east = base + 3 * (groups - 1)
        for x, y in ((base - 1, top - 1), (east + 2, top - 1)):
            grid.place(x, y, "R")
        grid.place(east + 2, top + 2, "R")
        grid.place(east + 1, top + 2, "R")
        corner = east + 1

    grid.lay_head(corner, top, reads[-1])
    for entry, bit in enumerate(indexed):
        x = start + 2 * entry
        grid.place(x, top, "!")
        if bit == "1":
            grid.place(x, top + 1, "+")
        grid.place(x, top + 2, ";")
        # A one turns on ``?`` (acc 1), a zero on ``!`` (acc 0).
        grid.place(x, top + 3, "?" if bit == "1" else "!")
        if entry + 1 < len(indexed):
            grid.place(x + 1, top, "-")
        if entry:
            # The return row's gap west of the turn: ``S`` lets the previous
            # entry's ``?`` pass, ``+`` keeps its ``!`` passing.
            grid.place(x - 1, top + 3, "S" if indexed[entry - 1] == "1" else "+")
    grid.place(0, top + 3, "R")
    if on_return:
        for x in range(1, _READS * trailing + 1):
            grid.place(x, top + 3, ".")
    else:
        for y in range(1, top + 3):
            grid.place(0, y, "." if y <= _READS * trailing else "+")
    return grid.render()


def _clockwise_program(truth_table: str, width: int | None = None) -> str:
    """Build the flat band, or under a width the narrower of it and the lookup."""
    flat = _clockwise_flat(truth_table)
    if width is None:
        # Area 25T + 40n + 20 against the stack's (2T + 9n + 2)(2n + 15) >= 34T:
        # the band wins at every n ([ablations.flat_band]).
        return flat
    total = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, total)
    trailing = total - used[-1] - 1
    indexed = read_at(truth_table, used, total)
    reads = _head_widths(total, used)
    grid = _Grid()
    digit = _layout_lookup(grid, reads, indexed)
    return_gap = _shift_return_rail(grid, trailing)
    layout = _Layout(grid, total, len(reads), digit + return_gap, return_gap)
    stacked = _fit_width(truth_table, layout, grid.render(), width)
    if grid_width(flat) > width:
        return stacked
    return min(stacked, flat, key=lambda p: (grid_area(p), len(p)))


def _clockwise_banded(truth_table: str, split: int) -> str:
    """Select one of ``2**split`` strips by the first inputs, then look up.

    The top is the lookup for the first ``split`` indexed inputs with its
    table cut to the countdown: entry ``h`` drops a column, east of every
    strip, to a ``!`` that turns west into strip ``h`` with the accumulator
    zero, as the digit tail leaves it.  Each strip is the lookup for the
    remaining inputs over its slice of the table, climbed into from below.
    Every strip leaves west along its table's return row onto one rail up
    column 0: an ``S`` lets its ``!`` turn north, and the ``+`` above makes
    the accumulator nonzero, so lower strips' rails pass the ``!`` straight.
    Inputs after the last indexed one are read on the rail above the strips.
    """
    total = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, total)
    trailing = total - used[-1] - 1
    indexed = read_at(truth_table, used, total)
    reads = _head_widths(total, used)
    strips, width = 1 << split, 1 << (len(used) - split)

    strip_cells = [
        _banded_lookup(reads[split:], indexed[h * width : (h + 1) * width])
        for h in range(strips)
    ]
    climb = _TABLE_ROWS + 1 + 2 * (len(reads) - split - 1)
    span = _prune_strips(strip_cells, climb)
    top, start = _merge_top(reads, split, strips, span)
    first = _rail_top(top, trailing)

    cells = dict(top)
    for h, strip in enumerate(strip_cells):
        offset = first + h * climb - 1
        for (x, y), char in strip.items():
            cells[x, y + offset] = char
        cells[start + 2 * h, climb + offset] = "!"
    grid = _Grid()
    grid.cells = cells
    return grid.render()


def _banded_lookup(head_reads: list[int], table: str) -> dict[tuple[int, int], str]:
    """Lay one lookup (the top or one strip) on a scratch grid; return its cells."""
    grid = _Grid()
    _layout_lookup(grid, head_reads, table)
    return grid.cells


def _prune_strips(strip_cells: list[dict[tuple[int, int], str]], climb: int) -> int:
    """Strip-pruning phase: cut each strip to its body and give it its lane.

    A strip keeps its heads, gadgets and table; its own entry descent,
    digit tail and exit turn give way to the shared ones.  The lane sits
    on row ``climb``.  Returns the strips' span: two columns clear of
    their eastmost cell, where the top's drop columns must stay east of.
    """
    for cells in strip_cells:
        for x, y in list(cells):
            if y == 0 or y >= climb or (x, y) == (0, _TABLE_ROWS):
                del cells[x, y]
        cells[_CLIMB, climb] = "R"
        # The lane runs west, so the digit is spelt backwards.
        for i, char in enumerate(reversed(_DIGIT)):
            cells[_DESCENT + i, climb] = char
        cells[1, _TABLE_ROWS] = "S"
        cells[0, _TABLE_ROWS] = "!"
        cells[0, _TABLE_ROWS - 1] = "+"
    return max(x for cells in strip_cells for x, _ in cells) + 2


def _merge_top(
    reads: list[int], split: int, strips: int, span: int
) -> tuple[dict[tuple[int, int], str], int]:
    """Top-merge phase: cut the selector lookup down to the countdown row.

    The top keeps its heads and gadgets.  Its table body and digit tail
    go (each strip's lane prints the digit), and so do the four rows the
    body held: nothing else crosses them but the descent and the climb.
    Returns the top's cells and the first drop column: entry ``h`` drops
    at ``start + 2 * h``, east of every strip.
    """
    raw = _banded_lookup(reads[:split], "0" * strips)
    start = min(x for (x, y), char in raw.items() if y == 1 and char == "!")
    digit = _TABLE_ROWS + 1 + 2 * (split - 1)
    top = {
        (x, y if y <= 1 else y - _TABLE_ROWS + 1): char
        for (x, y), char in raw.items()
        if not (1 <= y <= _TABLE_ROWS and x >= start)
        and (x, y) != (0, _TABLE_ROWS)
        and y < digit
    }
    top[_DESCENT, digit - _TABLE_ROWS + 1] = "R"
    top[_CLIMB, digit - _TABLE_ROWS + 1] = "R"
    # The columns drop past the top's own gadgets, which from eight strips
    # reach east of its table.
    start = max(start, span, max(x for x, _ in top) + 2)
    for h in range(strips):
        top[start + 2 * h, 1] = "!"
        if h + 1 < strips:
            top[start + 2 * h + 1, 1] = "-"
    return top, start


def _rail_top(top: dict[tuple[int, int], str], trailing: int) -> int:
    """Rail phase: read the trailing inputs down the top's west edge.

    The rail reads trailing inputs where no strip's ``!`` follows.
    Returns the first row below the top, where the strips stack.
    """
    first = max(max(y for _, y in top) + 1, _READS * trailing + 2)
    for y in range(1, _READS * trailing + 1):
        top[0, y] = "."
    return first


def _head_widths(total: int, used: list[int]) -> list[int]:
    """Read-run width of each head: seven reads per input.

    An ignored input's seven reads run just before the next indexed input's,
    which overwrite the bit they leave; the widths accumulate accordingly.
    """
    widths: list[int] = []
    pending = 0
    for position in range(total):
        pending += _READS
        if position in used:
            widths.append(pending)
            pending = 0
    return widths


def _layout_lookup(grid: _Grid, reads: list[int], indexed: str) -> int:
    """Lay the indexed-lookup grid; return the digit-tail start row.

    Row 0 sends the pointer down; rows 1 to 5 hold the table; below that,
    one gadget per level covers every value its partial index can hold.
    The shared digit bits go on the descent column where nothing else
    crosses it.
    """
    n = len(reads)
    size = len(indexed)
    # A gadget starts a head's width right of the one below.
    corner = [_CLIMB]
    for count in reads[:-1]:
        corner.append(corner[-1] + 2 + count)

    grid.place(_DESCENT, 0, "R")
    start = corner[n - 1] + 2 + reads[n - 1] + 1
    grid.lay_head(corner[n - 1], 1, reads[n - 1])
    for entry in range(size):
        grid.place(start + 2 * entry, 1, "!")
        if entry + 1 < size:
            grid.place(start + 2 * entry + 1, 1, "-")
        if indexed[entry] == "1":
            grid.place(start + 2 * entry, 2, "+")
        grid.place(start + 2 * entry, 3, ";")
        # ``S`` under every entry, so the row's length says nothing.
        grid.place(start + 2 * entry, 4, "S")
        grid.place(start + 2 * entry, _TABLE_ROWS, "!")
        if entry + 1 < size:
            grid.place(start + 2 * entry + 1, _TABLE_ROWS, "+")
    # The corridor turns up the left edge; reaching the origin halts.
    grid.place(0, _TABLE_ROWS, "R")

    for level in range(n - 1):
        # A level's gadget covers every value its partial index can hold.
        row = _TABLE_ROWS + 1 + 2 * (n - 2 - level)
        base = corner[level + 1] + 1
        groups = 1 << (level + 1)
        grid.lay_head(corner[level], row, reads[level])
        grid.place(base - 1, row + 1, "R")
        for group in range(groups):
            grid.place(base + 3 * group, row, "!")
            grid.place(base + 3 * group, row + 1, "!")
            if group + 1 < groups:
                grid.place(base + 3 * group + 1, row, "-")
                grid.place(base + 3 * group + 1, row + 1, "+")
                grid.place(base + 3 * group + 2, row + 1, "+")

    # The shared digit bits go where nothing else crosses the descent.
    digit = _TABLE_ROWS + 1 + 2 * (n - 1)
    for i, char in enumerate(_DIGIT):
        grid.place(_DESCENT, digit + i, char)
    grid.place(_DESCENT, digit + len(_DIGIT), "R")
    grid.place(_CLIMB, digit + len(_DIGIT), "R")
    return digit


def _shift_return_rail(grid: _Grid, trailing: int) -> int:
    """Shift every cell down and rerun the left-rail reads; return the shift.

    Separate the trailing inputs' return reads from the entry descent.  Two
    increments keep the lean rotation's return sentinel nonzero when a read
    clears its bit.  A zero shift leaves the grid untouched.
    """
    if not trailing:
        return 0
    gap = _READS * trailing - 2
    grid.cells = {(x, y + gap): char for (x, y), char in grid.cells.items()}
    del grid.cells[_DESCENT, gap]
    grid.cells[_DESCENT, 0] = "R"
    for y in range(1, gap + _TABLE_ROWS):
        grid.cells[0, y] = "." if y <= _READS * trailing else "+"
    return gap


def _fit_width(
    truth_table: str, layout: _Layout, program: str, width: int | None
) -> str:
    """Return ``program``, or its lean rotation (two columns, n <= 2) past ``width``."""
    if width is None or layout.grid.span() <= width:
        return program
    lean = _lean_rotate(layout)
    # Only n <= 2 has a two-column form (its prefix handles n == 2 alone).
    if layout.inputs <= 2 and grid_width(lean) > width:
        return _clockwise_two_columns(truth_table)
    return lean


def _render(rotated: dict[int, dict[int, str]], nrows: int) -> str:
    """Join sparse ``{row: {col: char}}`` cells into text, ``nrows`` lines."""
    return "\n".join(
        "".join(
            rotated.get(row, {}).get(col, " ")
            for col in range(max(rotated.get(row, {}), default=-1) + 1)
        )
        for row in range(nrows)
    )


def _lean_rotate(layout: _Layout) -> str:
    """Share entry and return rails using zero/nonzero gates around the lookup."""
    cells, n, digit = layout.grid.cells, layout.n, layout.digit
    span, return_gap = layout.grid.span(), layout.return_gap
    tail = digit - 1 if n > 1 else digit
    body = {(x, y): char for (x, y), char in cells.items() if 0 < y < digit}
    # The descent turns alongside the last gadget's return, outside its cells.
    body[_DESCENT, tail] = "R"
    body[_CLIMB, tail] = "R"
    body[1, _TABLE_ROWS + return_gap] = "+"
    rotated: dict[int, dict[int, str]] = {}
    for (x, y), char in body.items():
        rotated.setdefault(span - x, {})[y] = char
    prefix = _DIGIT[1:-1]  # Initial acc is already zero; clear after the entry turn.
    rail = max(tail + 1, len(prefix))
    rotated[0] = dict(enumerate(prefix)) | {rail: "R"}
    rotated.setdefault(1, {})[rail] = "S"
    rotated[span + 1] = {0: "R", rail: "R"}
    rotated.setdefault(span, {})[0] = "?"
    rotated.setdefault(span - _DESCENT, {})[0] = "!"
    return _render(rotated, span + 2)


def _clockwise_two_columns(table: str) -> str:
    """Index two inputs down one rail and accumulate the answer on the return."""
    n = _validate_truth_table(table)
    rows = [" R"]
    read = "." * _READS
    # Adding one to the first bit carries it into the second bit position;
    # the next read clears the low bit and supplies the second input.
    prefix = _DIGIT + read + ("+" + read if n == 2 else "")
    for index, char in enumerate(prefix):
        rows.append((";" if index == 0 else " ") + char)
    previous = 0
    for entry, bit in enumerate(table):
        delta = 2 + (int(bit) ^ previous)
        previous = int(bit)
        # A selected zero turns north; positive accumulated values pass all
        # earlier gates. Even padding preserves the telescoping answer parity.
        for offset in range(delta):
            rows.append("+" + ("-" if entry and offset == 0 else " "))
        rows.append("!!")
    return "\n".join(row.rstrip() for row in rows)


def _balance(table: str, default: str) -> str:
    """Compare the lookup, its rotations, the two-column route and the strips."""
    inputs = len(table).bit_length() - 1
    used = essential_inputs(table, inputs)
    if len(used) <= 1:
        commands = _READS * inputs + len(_DIGIT) + int(table[0]) + bool(used)
        # The ring's 2W+2H-7 free cells fix W+H; W=A*H splits them.
        width = max(2, ceil(CELL_ASPECT * (commands + 7) / (2 * CELL_ASPECT + 2)))
        ring = (
            _coordinate_ring(inputs, used[0], table[0], width)
            if used
            else _constant_ring(inputs, table[0], width)
        )
        return min(default, ring, key=balance_score)
    rotated = clockwise(table, max(1, grid_width(default) - 1))
    lean = clockwise(table, max(1, grid_width(rotated) - 1))
    # Measured on random tables n=3..9: side against split is minimal at
    # k//3 (k essential inputs), k//3+1 guards the rounding.
    k = len(used)
    splits = {min(max(s, 1), k - 1) for s in (k // 3, k // 3 + 1)}
    return min(
        default,
        rotated,
        lean,
        clockwise(table, 1),
        *(_clockwise_banded(table, s) for s in sorted(splits)),
        key=balance_score,
    )


LANGUAGE = Language(
    "Clockwise",
    "clockwise",
    category="grid_based",
    boolean=clockwise,
    # Not a tree: a countdown stops on the entry's own column.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream_cyclic",
        note="Clockwise reads all its input bits in one go, so they go "
        "on one line -- one character per bit, not a line per bit, and "
        "not seven bits packed into a character: that packing is real "
        "but is on the output side. A line per bit, or a packed one, "
        "is read as a different row and answered wrongly",
    ),
    balance=_balance,
    no_wrap="a row is a ring row; the walk's turns sit at fixed cells",
    empty_program="Clockwise program cannot be empty",
    grid=True,
)
