"""Clockwise Boolean program generator: a flat indexed lookup on a ring.

One ``!`` per entry in a row of ``!``/``-`` pairs, a Horner-rule index (MSB
first) in the accumulator, and one doubling gadget per input (widths double
upward).  An ignored input's seven reads run just before the next indexed
input's, which overwrite the bit they leave; inputs past the last essential
one are read on the return rail after printing.  A literal row has no
subtrees to fold or share.  Constants read a full input rotation, clear the
accumulator and emit the seven answer bits on a closed two-column ring.  A
``width`` exceeded rotates the program counterclockwise (two columns for
n <= 2, else ``2*n + 5``).

Size:
    O(T) cells; n=8 random 1847: 5,048 chars, n=10 random 1847: 17,740 chars,
    n=12 random 1847: 67,368 chars.
"""

from math import ceil
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
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

# The lookup table occupies rows 1 to 5; row 0 is the entry descent.
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


def _clockwise_program(
    truth_table: str, width: int | None = None, *, keep_trailing: bool = False
) -> str:
    """Build the indexed lookup, retaining the previous constant layout."""
    total = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, total)
    if keep_trailing or not used:
        used += range(used[-1] + 1 if used else 0, total)
    trailing = total - used[-1] - 1
    indexed = read_at(truth_table, used, total)
    reads = _head_widths(total, used)
    grid = _Grid()
    digit = _layout_lookup(grid, reads, indexed)
    return_gap = _shift_return_rail(grid, trailing)
    layout = _Layout(grid, total, len(reads), digit + return_gap, return_gap)
    return _fit_width(truth_table, layout, grid.render(), width)


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
    if width is None or width <= 0 or layout.grid.span() <= width:
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
    """Compare the lookup, legacy rotation, lean rotation and two-column route."""
    inputs = len(table).bit_length() - 1
    used = essential_inputs(table, inputs)
    if len(used) <= 1:
        commands = _READS * inputs + len(_DIGIT) + int(table[0]) + bool(used)
        # The ring's 2W+2H-7 free cells fix W+H; W=A*H splits them.
        width = max(2, ceil(CELL_ASPECT * (commands + 7) / (2 * CELL_ASPECT + 2)))
        square = (
            _coordinate_ring(inputs, used[0], table[0], width)
            if used
            else _constant_ring(inputs, table[0], width)
        )
        legacy = _clockwise_program(table, keep_trailing=True)
        rotated = _clockwise_program(
            table, max(1, grid_width(legacy) - 1), keep_trailing=True
        )
        lean = _clockwise_program(
            table, max(1, grid_width(rotated) - 1), keep_trailing=True
        )
        return min(
            default,
            square,
            legacy,
            rotated,
            lean,
            _clockwise_program(table, 1, keep_trailing=True),
            key=balance_score,
        )
    rotated = clockwise(table, max(1, grid_width(default) - 1))
    lean = clockwise(table, max(1, grid_width(rotated) - 1))
    return min(default, rotated, lean, clockwise(table, 1), key=balance_score)


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
)
