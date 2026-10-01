"""Boolean-function generator for ArrowQueue, and the tree it draws.

``*`` turns clockwise, ``~`` pushes the direction, ``+`` pops and points
(halting on an empty pop); no I/O, so parameterized runs plus the
termination convention (halt = 0, loop forever = 1).  Every input is one
cell crossed heading down: ``~`` pushes a down heading, ``.`` nothing.
Tree (``n <= 4``): a right push follows each cell and ``+`` branches pop
the front.  Cascade (``n >= 5``): each stage doubles the queued markers
then crosses the cell (Horner), and one ``+`` per row turns right at the
indexed row.  A ``0`` leaf is empty; a ``1`` leaf is a self-sustaining ring.
Both routes fold constant rows (a subtree; the cascade's tail).
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
)

#: Each input's cell, both routes: ``~`` pushes a down heading, ``.`` nothing.
PAIR = (".", "~")

_TREE_1 = ["+~+", "~ ~", "+~+"]


_TREE_0 = ["   ", "   ", "   "]


_TREE_BRANCH_0 = [" + ", "   ", "   "]


_TREE_BRANCH_1 = [" + ", "   ", "   "]


# Entered heading down at column 3; queues R, D, L, U, then down column 1.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


# One cascade stage: two ``~`` double each popped down marker; the right
# heading exits through the input cell and pushes the next stop heading.
_STAGE = ["  *+*", "   ~" + TEMPLATE_CHAR, "   ~", "  **", " *~*", " *  *"]

#: The cascade's row per table entry: a ring right of the ``+``, or none.
_ROWS = {"0": [" +", "", ""], "1": [" + +~+", "   ~ ~", "   +~+"]}

#: A folded tail of ``1`` rows: every marker left laps the ``*`` square back
#: into one ``+``; the stop heading then enters the ring as on a ``1`` row.
_DRAINED_RING = ["*+ +~+", "** ~ ~", "   +~+"]


def _header(n: int) -> list[str]:
    """Build the tree route's header: ``n`` input cells, a right push each.

    The cells sit on a diagonal; the last exits heading down at column 3.
    """
    rows = [" " * (n + 3) + "*"]
    for i in range(n):
        x = n + 3 - i
        rows.append(" " * (x - 3) + "*~*" + TEMPLATE_CHAR)
        rows.append(" " * (x - 3) + "*  *")
    return rows


def _connect(t0: list[str], t1: list[str]) -> list[str]:
    """Connect two decision subtrees into one.

    0-branch top-left, ``t0`` at its right exit, 1-branch below ``t0``,
    ``t1`` at its right exit.
    """
    yb = len(t0)
    width = max(3 + len(t0[0]), 3 + len(t1[0]))
    height = max(3, yb + 3, yb + len(t1))
    grid = [[" "] * width for _ in range(height)]
    for r, line in enumerate(_TREE_BRANCH_0):
        for c, ch in enumerate(line):
            grid[r][c] = ch
    for r, line in enumerate(_TREE_BRANCH_1):
        for c, ch in enumerate(line):
            grid[yb + r][c] = ch
    for r, line in enumerate(t0):
        for c, ch in enumerate(line):
            grid[r][3 + c] = ch
    for r, line in enumerate(t1):
        for c, ch in enumerate(line):
            grid[yb + r][3 + c] = ch
    return ["".join(row) for row in grid]


def _drained_leaf(value: str, skipped: int) -> list[str]:
    """Build a folded leaf that drains the ``skipped`` bits it never popped.

    A ``1`` leaf's ring must find exactly ``R, D, L, U``, so each skipped bit
    gets a ``+`` whose two exits reconverge one row down, one column right.
    """
    # A ``0`` leaf needs no drain: running off the grid halts regardless.
    if value != "1":
        return list(_TREE_0)
    # 3x3 leaf at (skipped, skipped + 1).
    grid = [[" "] * (skipped + 4) for _ in range(skipped + 3)]
    for i in range(skipped):
        grid[i][i + 1] = "+"
        grid[i][i + 2] = "*"
        grid[i + 1][i + 1] = "+"
    for r, line in enumerate(_TREE_1):
        for c, char in enumerate(line):
            if char != " ":
                grid[skipped + r][skipped + 1 + c] = char
    return ["".join(row) for row in grid]


def _tree(values: list[str]) -> list[str]:
    """Build the decision tree for the ``2**n`` table values.

    A constant subtree folds to a leaf that drains its skipped bits.
    """
    if len(set(values)) == 1:
        skipped = len(values).bit_length() - 1
        return _drained_leaf(values[0], skipped)
    if len(values) == 2:
        return _connect(
            _TREE_1 if values[0] == "1" else _TREE_0,
            _TREE_1 if values[1] == "1" else _TREE_0,
        )
    half = len(values) // 2
    return _connect(_tree(values[:half]), _tree(values[half:]))


def arrowqueue(truth_table: str, width: int | None = None) -> str:
    """Build an ArrowQueue template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    instantiated program halts iff the entry is ``0``.  Below five inputs a
    tree with 3x3 leaves, constant subtrees folded (:func:`_drained_leaf`);
    from five a cascade of at most ``6n`` + ``3 * 2**n`` rows, linear in the
    table, its constant tail folded (:func:`_cascade`).  An over-wide tree
    uses the cascade instead; below five columns an extra down marker
    moves the selector to the left edge while preserving the rings.
    """
    n = _validate_truth_table(truth_table)
    tree = (
        "\n".join([*_header(n), *_compact(_MIDDLE + _tree(list(truth_table)))])
        if n <= 4
        else None
    )
    if tree is None or (
        width is not None and width > 0 and max(map(len, tree.split("\n"))) > width
    ):
        if width is not None and 0 < width < 5:
            return _four_column_cascade(truth_table, n)
        leaves = _cascade(truth_table)
        if width is not None and 0 < width < 6:
            # Entry travels down column1; column2 in every leaf is only blank
            # travel between that selector and its ring, so remove it locally.
            leaves = [row[:2] + row[3:] for row in leaves]
        rows = ["  ~*", *(_STAGE * n), *_MIDDLE, *leaves]
        return "\n".join(row.rstrip() for row in rows)
    return tree


def _four_column_cascade(table: str, n: int) -> str:
    """Prepend one down marker to route the selector along column0."""
    # Shift input stages left. A clockwise detour then lands down at1.
    rows = [" ~*", *(row[1:] for row in _STAGE * n), "**", "* *", " ~"]
    # Append D, rotate the existing D markers until the R sentinel,
    # consume that R and restore it on exit. Queue becomes D^(index+1),R.
    rows.extend(["*+~*", " ~", "**"])
    rows.extend(_MIDDLE)
    # The fixed extra D turns leftward travel down at the left edge;
    # consuming it leaves the original selector/ring queue unchanged.
    rows.append("+*")
    for bit in table:
        # Unfold the constant tail: its old drain loop uses column0.
        rows.extend((row[:2] + row[3:])[1:] for row in _ROWS[bit])
    return "\n".join(row.rstrip() for row in rows)


def _cascade(truth_table: str) -> list[str]:
    """Build the cascade's rows, the table's constant tail folded.

    A ``0`` tail is dropped (running off the grid halts); a ``1`` tail is
    one :data:`_DRAINED_RING`, popping the markers the dropped rows would.
    """
    tail = len(truth_table.rstrip(truth_table[-1]))
    rows = [row for bit in truth_table[:tail] for row in _ROWS[bit]]
    return [*rows, *_DRAINED_RING] if truth_table[-1] == "1" else rows


def _compact(rows: list[str]) -> list[str]:
    """Drop the wholly blank rows and columns from the template's body.

    A blank line carries only straight travel; the header's glyphs sit past
    column 4, which every branch marks.
    """
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:
        return []  # pragma: no cover - every table lays a cell
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return ["".join(row[x] for x in columns).rstrip() for row in kept]
