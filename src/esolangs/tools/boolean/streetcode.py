"""Boolean-function generator for Streetcode.

Streetcode is a grid language whose programs are laid out as hallways, so
the generator builds a decision tree from hallway strips
(:func:`_streetcode_hallway`, :func:`_streetcode_strip`) and joins the
per-level blocks side by side.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["streetcode"]


def _streetcode_combine(arrs: list[list[str]]) -> list[str]:
    """Lay ``arrs`` side by side, padding each to the tallest one's height."""
    top = max(len(arr) for arr in arrs)
    padded = [arr + [" " * len(arr[0])] * (top - len(arr)) for arr in arrs]
    return ["".join(arr[row] for arr in padded) for row in range(top)]


def _streetcode_hallway(c: str) -> list[str]:
    """Build a wall-hugging loop of exactly 48 ``c`` cells, one per row-pair.

    Driving into the loop and back out crosses 48 ``c`` cells total (two
    per row), so it always adjusts a cell by 48 -- enough to walk an ASCII
    digit (``'0'`` = 48, ``'1'`` = 49) down to a bare 0/1, or a fresh 0 cell
    up to ASCII ``'0'``.
    """
    top = ["----", "    ", "    ", "+  +", "|  |"]
    row = f"|{c * 2}|"
    return [*top, *([row] * 24), "+--+"]


def _streetcode_strip(before: str, c: str) -> list[str]:
    """Build a labeled loop room: ``before`` runs as instructions, then the loop.

    ``before`` is both the label text drawn above the room and the actual
    instructions the car drives over to reach it, so callers thread cell/CP
    bookkeeping through the label itself (see ``_streetcode_collect`` and
    the ``strip`` call in ``streetcode``).
    """
    width = len(before)
    wall = "-" * width
    first = [wall, " " * width, before, wall]
    return _streetcode_combine([first, _streetcode_hallway(c)])


def _streetcode_collect() -> list[str]:
    """One input-reading loop: read a bit, then decrement it down to 0/1.

    ``~=I^`` leads into the loop: ``~`` consumes the +1 the previous
    loop's own trailing ``^`` left on the cell behind, ``=`` advances CP
    onto a fresh cell, ``I`` reads the next bit (ASCII ``'0'``/``'1'``),
    and the trailing ``^`` forces the cell nonzero *before* the loop's
    junction is tested, so the ambiguous-turn rule (leftmost when the CPth
    cell is 0, otherwise second-leftmost) reliably turns into the loop
    rather than driving straight past it.
    """
    return _streetcode_strip("~=I^", "~")


def _streetcode_leaf(bit: int) -> list[str]:
    """Build a leaf that prints ``bit``, reusing the loader loop's cell.

    The car arrives with CP already on the cell ``_streetcode_populate``'s
    closing loop ramped to ASCII ``'0'`` + 1 (one more than 48, from that
    loop's own forced-nonzero trailing ``^``); ``~`` corrects it back down
    to plain ``'0'`` for a 0 leaf, or a no-op leaves it at ``'1'`` for a 1
    leaf, and ``O`` prints whichever digit results.
    """
    op = " " if bit else "~"
    return ["---+", "   |", f"{op}O;|", "---+"]


def _streetcode_tree(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit.

    Recurses on halves of ``table``, joining the two subtrees with a hall
    that advances CP by one ``=`` and forks the car left/right onto the
    matching subtree -- the same leftmost/second-leftmost ambiguous-turn
    rule the loops use, now keyed on the bit ``_streetcode_collect`` left
    behind instead of a byte fresh off ``I``.
    """
    size = len(table)
    if size == 1:
        return _streetcode_leaf(int(table[0]))

    half = size // 2
    top = _streetcode_tree(table[:half])
    bot = _streetcode_tree(table[half:])
    height = len(top)

    hall = []
    for k in range(height * 2):
        if k == 0:
            row = "----"
        elif k == 1:
            row = "    "
        elif k == 2:
            row = "   ="
        elif k == 3:
            row = "+  +"
        elif k == 4:
            row = "|  +" if size == 2 else "|  |"
        elif k < height:
            row = "|  |"
        elif k == height:
            row = "|  +"
        elif k < height + 2:
            row = "|   "
        elif k == height + 2:
            row = "|  ="
        elif k == height + 3:
            row = "+---"
        else:
            row = "    "
        hall.append(row)

    return _streetcode_combine([hall, [*top, *bot]])


def _streetcode_populate(n: int) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader loop (``strip('~=^', '^')``) is structurally identical to
    an input-reading loop but has no ``I`` of its own: its label's trailing
    ``^`` supplies the forced-nonzero bump instead, so it always turns in
    and ramps a fresh cell up to ASCII ``'0'`` + 1 for the tree's leaves to
    print from (see ``_streetcode_leaf``).
    """
    start = ["+--", "|  ", "|C^", "+--"]
    col = _streetcode_collect()
    return _streetcode_combine(
        [
            start,
            *([col] * n),
            _streetcode_strip("~=^", "^"),
            ["-" * n, " " * n, "_" * n, "-" * n],
        ],
    )


def streetcode(truth_table: str) -> str:
    """Build a Streetcode program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The car reads each input bit through a wall-hugging loop that walks
    its ASCII value down to a bare 0/1 (:func:`_streetcode_collect`), then
    drives into a binary decision tree (:func:`_streetcode_tree`) whose
    T-junctions apply Streetcode's ambiguous-turn rule -- leftmost when the
    CPth cell is 0, otherwise second-leftmost -- to fork on each bit in
    turn.  A final loader loop (folded into :func:`_streetcode_populate`)
    ramps a fresh cell up to ASCII ``'0'`` before the tree, so every leaf
    can print the table's digit directly rather than building its own
    ramp.
    """
    n = _validate_truth_table(truth_table)
    populated = _streetcode_populate(n)
    tree = _streetcode_tree(truth_table)
    return "\n".join(_streetcode_combine([populated, tree]))
