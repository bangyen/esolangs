"""Shared input planning and drawing primitives for Flowchart layouts."""

from collections.abc import Callable
from itertools import pairwise

from esolangs.generation.projection import essential_inputs, read_at

# Prints the register, then bits 1..7 of 0x30 low bit first, and halts.
_ANSWER = (
    "\\ \\",
    "{ ]",
    "\\ \\",
    "\\ \\",
    "\\ \\",
    "[ }",
    "\\ \\",
    "\\ \\",
    "{ ]",
    "\\ \\",
    "\\ \\",
    "(( ))",
)


def _set(bit: str) -> str:
    """Return the node that sets the register to ``bit``."""
    return "[ }" if bit == "1" else "{ ]"


def _paint(cells: dict[tuple[int, int], str], x: int, y: int, text: str) -> None:
    """Write ``text`` into ``cells`` along row ``y`` from column ``x``."""
    for i, char in enumerate(text):
        cells[(x + i, y)] = char


def _reads(level: int) -> int:
    """Return the ``/ /`` count that selects input ``level``'s value bit."""
    return 1 if level == 0 else 8


type _InputPlan = tuple[str, tuple[int, ...], int]


def _plan(
    truth_table: str, *, used: list[int] | tuple[int, ...] | None = None
) -> _InputPlan:
    """Return the essential-input table, the ``/ /`` count per switch, the tail.

    The tail is the ``/ /`` count owed after the last switch.  An ignored
    input is read, not branched on: its eight ``/ /`` join the next level's,
    or the tail.  A constant table keeps every level, folded.
    """
    n = len(truth_table).bit_length() - 1
    if used is None:
        used = essential_inputs(truth_table, n)
    if not used:
        return truth_table, tuple(_reads(level) for level in range(n)), 0
    costs = (8 * used[0] + 1, *(8 * (b - a) for a, b in pairwise(used)))
    return read_at(truth_table, used, n), costs, 8 * (n - 1 - used[-1])


def _answer_column(cells: dict[tuple[int, int], str], middle: int, y: int) -> None:
    """Paint :data:`_ANSWER` down column ``middle`` from row ``y``."""
    for text in _ANSWER:
        _paint(cells, middle - len(text) // 2, y, text)
        cells[(middle, y + 1)] = "│"
        y += 2
    del cells[(middle, y - 1)]


def _folded_walk[C, R](
    rows: int,
    constant: Callable[[int, int], bool],
    leaf: Callable[[int, int, C], R],
    branch: Callable[[int, int, int, C, Callable[[int, int, int, C], R]], R],
    cursor: C,
) -> R:
    """Walk the folded decision tree, painting it through callbacks.

    ``leaf(lo, depth, cursor)`` paints a constant span; ``branch(lo, hi,
    depth, cursor, descend)`` paints a switch and calls ``descend(lo, hi,
    depth, cursor)`` for each half it draws, in whichever order its layout
    needs.  The traversal -- constant test, halving, recursion -- is shared;
    the painters differ only in cell placement.  The cursor is opaque to the
    walk: the stacked painter threads its row and lock flag through it, the
    others pass ``None``.  Returns whatever the root call returns.
    """

    def descend(lo: int, hi: int, depth: int, cursor: C) -> R:
        if constant(lo, hi):
            return leaf(lo, depth, cursor)
        return branch(lo, hi, depth, cursor, descend)

    return descend(0, rows, 0, cursor)
