"""Boolean-function generator for Nopstacle: a decision tree of corridors.

The IP walks blank cells, turns anticlockwise at a ``#`` or the edge,
halts when a local state repeats within one copy of the rectangle, and
runs forever when it keeps crossing into new copies.  Inputs are cells: a
``1`` is a ``#``, a ``0`` a blank.  A node is a vertical corridor ending
at a bit cell: a blank drops the IP into the ``0`` child, a ``#`` U-turns
it along a span row to the ``1`` child.  A ``0`` leaf is a two-cell box
the IP circles once; a ``1`` leaf drops it onto a blank row where a ``#``
beneath turns it right across copies forever.

Levels are three rows each (up-wall, span, bit) under a two-row
turnaround from the origin to the root, with a four-row leaf band.  Level
``i`` reads input ``i`` at ``2**i`` node columns ``2**(n-i)`` leaf pitches
apart, one run per level of the same width either bit.  Width is
``4 * 2**n``, height ``3n + 7``, padded so every instantiation has one
length: ``Theta(n 2**n)``.  An H-tree would be ``O(2**n)`` but spreads a
level over ``2**(i/2)`` rows, and one run fills one line.  The halting
row's step count is at most three widths.
"""

from esolangs.exceptions import TruthTableError
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)

__all__ = ["instantiate_nopstacle", "nopstacle"]

#: Columns per leaf: the halting box is two cells with a wall either side.
_PITCH = 4
#: Rows per tree level: up-wall, span, bit.
_LEVEL = 3
#: Rows above the tree: the turnaround from the origin to the root column.
_HEAD = 2


def _columns(n: int, i: int) -> tuple[int, int]:
    """Return the rightmost node column and the half-width of level ``i``."""
    return (2**n - 1) * _PITCH, 2 ** (n - i - 1) * _PITCH


def nopstacle(truth_table: str) -> str:
    """Build a template specialized by :func:`instantiate_nopstacle`.

    Level ``i``'s bit row is blank up to its leftmost node column, then its
    run, then blank to the edge.  The answer is termination: halt for a
    ``0`` entry, crossing copies forever for a ``1``.
    """
    n = _validate_truth_table(truth_table)
    width = 2**n * _PITCH
    root = width - _PITCH
    height = _HEAD + _LEVEL * n + 5
    grid = [[" "] * width for _ in range(height)]

    def wall(x: int, y: int) -> None:
        if x >= 0:
            grid[y][x] = "#"

    # Turnaround: down column 0, right along row 1, up column root+1, left
    # along row 0, down the root column.
    wall(0, 2)
    wall(root + 2, 1)
    wall(root - 1, 0)

    rows = []
    for i in range(n):
        up, span, bit_row = (_HEAD + _LEVEL * i + k for k in range(3))
        _, half = _columns(n, i)
        for x in range(root, -1, -2 * half):
            wall(x + 1, up)
            wall(x + 2, span)
            wall(x - half - 1, span)
        rows.append(bit_row)

    # Leaf band: boxes for 0 entries, a fall-through onto the blank row for 1.
    box, blank = height - 4, height - 2
    for index, entry in enumerate(truth_table):
        x = root - index * _PITCH
        if entry == "0":
            wall(x + 1, box - 1)
            wall(x - 1, box)
            wall(x + 2, box)
            wall(x, box + 1)
        else:
            wall(x, blank + 1)

    lines = ["".join(row) for row in grid]
    setters = nopstacle_setters("", n)
    for i, y in enumerate(rows):
        first = (2 ** (n - i) - 1) * _PITCH
        run = TEMPLATE_CHAR * len(setters[i][0])
        lines[y] = " " * first + run + " " * (width - root - 1)
    return "\n".join(lines)


def instantiate_nopstacle(template: str, bits: list[int]) -> str:
    """Fill each input's run with its level's bit cells.

    A ``0`` run is blank end to end and exactly as wide as a ``1`` run.
    """
    # The runs' total width grows with the input count, so the count is
    # the one value at which the widths sum to what the template holds.
    total = template.count(TEMPLATE_CHAR)
    n = 1
    while total > sum(len(zero) for zero, _one in nopstacle_setters(template, n)):
        n += 1
    setters = nopstacle_setters(template, n)
    if total != sum(len(zero) for zero, _one in setters):
        raise ValueError("not a Nopstacle Boolean template")
    if len(bits) != n or any(bit not in (0, 1) for bit in bits):
        raise TruthTableError(f"expected {n} Boolean input bits, got {bits!r}")
    return fill_runs(template, TEMPLATE_CHAR, setters, bits)


def nopstacle_setters(_template: str, n: int) -> Setters:
    """Each level's run of bit cells, blank for a zero and ``#`` for a one."""

    def run(i: int, bit: int) -> str:
        cell = "#" if bit else " "
        _, half = _columns(n, i)
        return cell + (" " * (2 * half - 1) + cell) * ((1 << i) - 1)

    return tuple((run(i, 0), run(i, 1)) for i in range(n))
