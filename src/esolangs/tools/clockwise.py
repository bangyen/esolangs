"""Boolean-function generator for Clockwise."""

from math import ceil

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import (
    _validate_truth_table,
    essential_inputs,
    grid_width,
    read_at,
)
from esolangs.tools.wrap import balance_score

# The ring's own columns: 3 descends at the start, 2 climbs into the first
# gadget, 0 climbs home.  Column 1 is the gap that keeps the three apart.
_DESCENT = 3
_CLIMB = 2

# A head is a corner, a gap the descent crosses, seven ``.`` for one input's
# value bit (more where ignored inputs precede it), and the gap the return
# leg climbs -- the next gadget's corner, so the head width is the pitch too.
_READS = 7

_TABLE_ROWS = 5

# The six digit bits both answers share: 0110000 and 0110001 differ in the
# last only.  ``S`` opens the run because the descent crosses a read.
_DIGIT = "S;+;;+;;;S"


def clockwise(truth_table: str, width: int | None = None) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program prints ``'0'`` or ``'1'``.  With ``width`` set and exceeded, the
    program rotates counterclockwise (two columns for n <= 2, else
    ``2*n + 5``).

    A flat indexed lookup: one ``!`` per entry in a row of ``!``/``-``
    pairs, a Horner-rule index (MSB first) in the accumulator, and one
    doubling gadget per input (widths double upward, so ``O(T)``).  An
    ignored input's seven reads run just before the next indexed input's,
    which overwrite the bit they leave; inputs past the last essential one
    are read on the return rail after printing.  A
    literal row has no subtrees to fold or share.
    Constants read a full input rotation, clear the accumulator and emit the
    seven answer bits on a closed two-column ring.
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
    reads: list[int] = []
    pending = 0
    for position in range(total):
        pending += _READS
        if position in used:
            reads.append(pending)
            pending = 0
    n = len(reads)
    size = len(indexed)
    cells: dict[tuple[int, int], str] = {}

    def place(x: int, y: int, char: str) -> None:
        """Write ``char`` at ``(x, y)``, refusing an occupied cell."""
        if (x, y) in cells:
            raise AssertionError(f"two cells at {(x, y)}: {cells[(x, y)]!r}, {char!r}")
        cells[(x, y)] = char

    def head(level: int, y: int) -> None:
        """Lay a gadget's corner and the reads that follow it."""
        place(corner[level], y, "R")
        for i in range(reads[level]):
            place(corner[level] + 2 + i, y, ".")

    # A gadget starts a head's width right of the one below.
    corner = [_CLIMB]
    for count in reads[:-1]:
        corner.append(corner[-1] + 2 + count)

    # Row 0 sends the pointer down; rows 1 to 5 are the table.
    place(_DESCENT, 0, "R")
    start = corner[n - 1] + 2 + reads[n - 1] + 1
    head(n - 1, 1)
    for entry in range(size):
        place(start + 2 * entry, 1, "!")
        if entry + 1 < size:
            place(start + 2 * entry + 1, 1, "-")
        if indexed[entry] == "1":
            place(start + 2 * entry, 2, "+")
        place(start + 2 * entry, 3, ";")
        # ``S`` under every entry, so the row's length says nothing.
        place(start + 2 * entry, 4, "S")
        place(start + 2 * entry, _TABLE_ROWS, "!")
        if entry + 1 < size:
            place(start + 2 * entry + 1, _TABLE_ROWS, "+")
    # The corridor turns up the left edge; reaching the origin halts.
    place(0, _TABLE_ROWS, "R")

    for level in range(n - 1):
        # A level's gadget covers every value its partial index can hold.
        row = _TABLE_ROWS + 1 + 2 * (n - 2 - level)
        base = corner[level + 1] + 1
        groups = 1 << (level + 1)
        head(level, row)
        place(base - 1, row + 1, "R")
        for group in range(groups):
            place(base + 3 * group, row, "!")
            place(base + 3 * group, row + 1, "!")
            if group + 1 < groups:
                place(base + 3 * group + 1, row, "-")
                place(base + 3 * group + 1, row + 1, "+")
                place(base + 3 * group + 2, row + 1, "+")

    # The shared digit bits go where nothing else crosses the descent.
    digit = _TABLE_ROWS + 1 + 2 * (n - 1)
    for i, char in enumerate(_DIGIT):
        place(_DESCENT, digit + i, char)
    place(_DESCENT, digit + len(_DIGIT), "R")
    place(_CLIMB, digit + len(_DIGIT), "R")

    # Separate the return reads from the entry descent. Two increments keep
    # the lean rotation's return sentinel nonzero when a read clears its bit.
    return_gap = _READS * trailing - 2 if trailing else 0
    if return_gap:
        cells = {(x, y + return_gap): char for (x, y), char in cells.items()}
        del cells[_DESCENT, return_gap]
        cells[_DESCENT, 0] = "R"
        for y in range(1, return_gap + _TABLE_ROWS):
            cells[0, y] = "." if y <= _READS * trailing else "+"
        digit += return_gap

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    # The interpreter pads short rows, so trailing filler is never reached.
    program = "\n".join("".join(row).rstrip() for row in grid)
    if width is None or width <= 0 or span <= width:
        return program
    if width < height + 2:
        # Emit the common six digit bits on the entry rail, before reading.
        # Only the selected final bit depends on the table. This removes the
        # nine-row digit tail without changing the accumulator at the first read.
        rail_cells = {
            (x + len(_DIGIT) + 1 if x else x, y): char
            for (x, y), char in cells.items()
            if y < digit
        }
        for x, char in enumerate(_DIGIT):
            rail_cells[x, 0] = char
        rail_cells[_DESCENT + len(_DIGIT) + 1, digit] = "R"
        rail_cells[_CLIMB + len(_DIGIT) + 1, digit] = "R"
        rail_height = digit + 1
        rail_span = max(x for x, _ in rail_cells) + 1
    else:
        rail_cells, rail_height, rail_span = cells, height, span
    # Counterclockwise rotation puts the wide lookup down the page.  Most
    # rows end at the five table columns; the interpreter pads the entry rail.
    rotated: dict[int, dict[int, str]] = {}
    for (x, y), char in rail_cells.items():
        rotated.setdefault(rail_span - x, {})[y + 1] = char
    rotated[0] = {rail_height + 1: "R"}
    rotated[rail_span + 1] = {1: "R", rail_height + 1: "R"}
    rotated.setdefault(rail_span, {})[0] = "R"
    legacy = _render(rotated, rail_span + 2)
    legacy_w = max(map(len, legacy.splitlines()))
    if legacy_w <= width:
        return legacy
    lean = _clockwise_lean_rotate(cells, n, digit, span, return_gap)
    lean_w = max(map(len, lean.splitlines()))
    chosen, chosen_w = (lean, lean_w) if lean_w < legacy_w else (legacy, legacy_w)
    # Only n <= 2 has a two-column form (its prefix handles n == 2 alone).
    if total <= 2 and chosen_w > width:
        return _clockwise_two_columns(truth_table)
    return chosen


def _render(rotated: dict[int, dict[int, str]], nrows: int) -> str:
    """Join sparse ``{row: {col: char}}`` cells into text, ``nrows`` lines."""
    return "\n".join(
        "".join(
            rotated.get(row, {}).get(col, " ")
            for col in range(max(rotated.get(row, {}), default=-1) + 1)
        )
        for row in range(nrows)
    )


def _clockwise_lean_rotate(
    cells: dict[tuple[int, int], str],
    n: int,
    digit: int,
    span: int,
    return_gap: int = 0,
) -> str:
    """Share entry and return rails using zero/nonzero gates around the lookup."""
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
        width = max(2, ceil((commands + 7) / 4))
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
    "grid_based.clockwise",
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
