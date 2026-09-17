"""Boolean-function generator for Nopstacle: a decision tree of corridors.

Nopstacle's IP walks blank cells and turns anticlockwise in place when a
``#`` or the outer edge blocks it; it halts when a local state repeats
without leaving the current copy of the rectangle and runs forever when it
keeps crossing into new copies.  There is no input, so the inputs are cells:
a ``1`` is a ``#`` and a ``0`` is a blank.  The program is a binary decision
tree drawn downwards.  A node is a vertical corridor ending at a bit cell:
a blank lets the IP fall straight through into the ``0`` child; a ``#``
deflects it into a U-turn that carries it left along a span row to the
``1`` child's corridor.  The leaves along the bottom are the table: a ``0``
entry is a two-cell box the IP circles once, repeating a local state; a
``1`` entry drops the IP onto an all-blank row where a ``#`` beneath turns
it right and it crosses copies forever.

One level, node column ``x``, subtree half-width ``a`` (``.`` marks a cell
the IP visits, ``b`` the bit)::

    up-wall row     .#            the IP arrived down column x
    span row   #.....#            1: right, up (blocked), left to x-a, down
    bit row     .   b             0: through b, down column x

Rows are grouped three per level under a two-row turnaround that carries
the IP from the origin to the root at the right edge, and a leaf band of
four rows under the last level.  Level ``i`` reads input ``i`` at ``2**i``
node columns spaced ``2**(n-i)`` leaf pitches apart, so ``{Xi}`` is one
run per level: a bit cell at each node column and blanks between, the same
width for either bit.  Width is ``4 * 2**n`` cells, height ``3n + 7`` rows.
The rectangle is padded, so every instantiation of a template has one
length.

Size is ``Theta(n 2**n)``: the last level alone is ``2**n`` leaf pitches
wide, the rectangle is padded to it, and each input owns three rows.  An
H-tree would be ``O(2**n)``, but its level-``i`` cells fall on ``2**(i/2)``
different rows, and one ``{Xi}`` placeholder fills one line.  Execution is a
single pass: the halting row's step count is at most three widths.
"""

import re

from esolangs.exceptions import TruthTableError
from esolangs.tools.helpers import (
    Setters,
    _validate_truth_table,
    instantiate,
    slot_count,
)

__all__ = ["instantiate_nopstacle", "nopstacle"]

#: Columns per leaf: the halting box is two cells with a wall either side.
_PITCH = 4
#: Rows per tree level: up-wall, span, bit.
_LEVEL = 3
#: Rows above the tree: the turnaround from the origin to the root column.
_HEAD = 2
_SLOT = re.compile(r"\{X(\d+)\}")


def _columns(n: int, i: int) -> tuple[int, int]:
    """Return the rightmost node column and the half-width of level ``i``."""
    return (2**n - 1) * _PITCH, 2 ** (n - i - 1) * _PITCH


def nopstacle(truth_table: str) -> str:
    """Build a template specialized by :func:`instantiate_nopstacle`.

    Level ``i``'s bit row is blank up to its leftmost node column, then
    ``{Xi}``, then blank to the rectangle's edge; everything else is drawn
    here.  The answer is termination: the IP halts for a ``0`` entry and
    crosses copies forever for a ``1``.
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
    for i, y in enumerate(rows):
        first = (2 ** (n - i) - 1) * _PITCH
        lines[y] = " " * first + f"{{X{i}}}" + " " * (width - root - 1)
    return "\n".join(lines)


def instantiate_nopstacle(template: str, bits: list[int]) -> str:
    """Fill each ``{Xi}`` with its level's run of bit cells.

    The run spans the level's node columns, ``2**(n-i)`` leaf pitches
    apart, with the bit at each and blanks between; a ``0`` run is blank
    end to end and exactly as wide as a ``1`` run.
    """
    slots = [int(s) for s in _SLOT.findall(template)]
    n = len(slots)
    if slots != list(range(n)) or n == 0:
        raise ValueError("not a Nopstacle Boolean template")
    if len(bits) != n or any(bit not in (0, 1) for bit in bits):
        raise TruthTableError(f"expected {n} Boolean input bits, got {bits!r}")

    return instantiate(
        template, bits, nopstacle_setters(template, slot_count(template))
    )


def nopstacle_setters(_template: str, n: int) -> Setters:
    """Each level's run of bit cells, blank for a zero and ``#`` for a one."""

    def run(i: int, bit: int) -> str:
        cell = "#" if bit else " "
        _, half = _columns(n, i)
        return cell + (" " * (2 * half - 1) + cell) * (2**i - 1)

    return tuple((run(i, 0), run(i, 1)) for i in range(n))
