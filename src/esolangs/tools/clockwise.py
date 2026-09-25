"""Boolean-function generator for Clockwise."""

from esolangs.tools.helpers import _validate_truth_table

# The ring's own columns: 3 descends at the start, 2 climbs into the first
# gadget, 0 climbs home.  Column 1 is the gap that keeps the three apart.
_DESCENT = 3
_CLIMB = 2

# A head is a corner, a gap the descent crosses, seven ``.`` for one input's
# value bit, and the gap the return leg climbs -- the next gadget's corner,
# so the head width is the pitch too.
_READS = 7
_HEAD = 2 + _READS

_TABLE_ROWS = 5

# The six digit bits both answers share: 0110000 and 0110001 differ in the
# last only.  ``S`` opens the run because the descent crosses a read.
_DIGIT = "S;+;;+;;;S"


def clockwise(truth_table: str) -> str:
    """Build a Clockwise program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    program prints ``'0'`` or ``'1'``.

    A flat indexed lookup, not a tree.  The table is one ``!`` per entry in
    a row of ``!``/``-`` pairs: the index sits in the accumulator, the
    pointer loses one per pair, and the ``!`` it reaches zero on turns it
    down that entry's column.  Three rows below hold the answer (``+`` if
    the bit is set, ``;``, ``S``) and a fifth turns every descent back
    along one corridor -- ``!`` under each column, ``+`` between, so the
    turning pointer is zero there and the passing one is not.

    The index is Horner's rule, MSB first.  ``.`` clears the accumulator's
    low bit before storing what it reads, so seven of them over an even
    accumulator add an input's bit; only doubling needs a gadget, two rows
    of three columns a unit -- out losing one a group, down on zero, back
    picking up two.  Gadget widths double upward, so the chain costs what
    its top one does and the program is ``O(T)``.
    """
    n = _validate_truth_table(truth_table)
    size = len(truth_table)
    cells: dict[tuple[int, int], str] = {}

    def place(x: int, y: int, char: str) -> None:
        """Write ``char`` at ``(x, y)``, refusing an occupied cell."""
        if (x, y) in cells:
            raise AssertionError(f"two cells at {(x, y)}: {cells[(x, y)]!r}, {char!r}")
        cells[(x, y)] = char

    def head(x: int, y: int) -> None:
        """Lay a gadget's corner and the seven reads that follow it."""
        place(x, y, "R")
        for i in range(_READS):
            place(x + 2 + i, y, ".")

    # A gadget starts a pitch right of the one below.
    corner = [_HEAD * level + _CLIMB for level in range(n)]

    # Row 0 sends the pointer down; rows 1 to 5 are the table.
    place(_DESCENT, 0, "R")
    start = corner[n - 1] + _HEAD + 1
    head(corner[n - 1], 1)
    for entry in range(size):
        place(start + 2 * entry, 1, "!")
        if entry + 1 < size:
            place(start + 2 * entry + 1, 1, "-")
        if truth_table[entry] == "1":
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
        base = corner[level] + _HEAD + 1
        groups = 1 << (level + 1)
        head(corner[level], row)
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

    height = max(y for _, y in cells) + 1
    span = max(x for x, _ in cells) + 1
    grid = [[" "] * span for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    # The interpreter pads short rows, so trailing filler is never reached.
    return "\n".join("".join(row).rstrip() for row in grid)
