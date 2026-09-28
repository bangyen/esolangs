"""Boolean-function generator for ArrowQueue, and the tree it draws.

``*`` turns clockwise, ``~`` pushes the direction, ``+`` pops and points
(halting on an empty pop); no I/O, so parameterized runs plus the
termination convention (halt = 0, loop forever = 1).  Every input is one
cell crossed heading down: ``~`` pushes a down heading, ``.`` nothing.
Tree (``n <= 4``): a right push follows each cell and ``+`` branches pop
the front.  Cascade (``n >= 5``): each stage doubles the queued markers
then crosses the cell (Horner), and one ``+`` per row turns right at the
indexed row.  A ``0`` leaf is empty; a ``1`` leaf is a self-sustaining ring.
Both routes fold constant rows: the tree a constant subtree, the cascade
its constant tail.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    permute_truth_table,
)

#: Each input's cell, both routes: ``~`` pushes a down heading, ``.`` nothing.
PAIR = (".", "~")

_TREE_1 = ["+~+", "~ ~", "+~+"]  # the ``1`` leaf: a self-sustaining ring


_TREE_0 = ["   ", "   ", "   "]  # the ``0`` leaf: empty, runs off-grid to halt


_TREE_BRANCH_0 = [" + ", "   ", "   "]  # pops a bit; 0 goes right, 1 goes down


_TREE_BRANCH_1 = [" + ", "   ", "   "]  # pops a one's trailing R: down-route goes right


# Loop components: entered heading down at column 3, queues R, D, L, U
# (so the tree sees ``[bits..., R, D, L, U]``) and routes down column 1.
_MIDDLE = ["*~* ", "*  *", "*  *", "~ ~ ", "*~* ", "**  ", "*  *"]


# One cascade stage: a popped down marker laps the loop (two ``~`` double
# it); the popped right heading exits through the input cell and the tail
# pushes the next stage's stop heading.
_STAGE = ["  *+*", "   ~" + TEMPLATE_CHAR, "   ~", "  **", " *~*", " *  *"]

#: The cascade's row per table entry: a ring right of the ``+``, or none.
_ROWS = {"0": [" +", "", ""], "1": [" + +~+", "   ~ ~", "   +~+"]}

#: A folded tail of ``1`` rows: one reusable drain.  A popped marker laps
#: the ``*`` square back into the same ``+``, so every marker left is
#: drained there, and the stop heading enters the ring as on a ``1`` row.
_DRAINED_RING = ["*+ +~+", "** ~ ~", "   +~+"]


def _header(n: int, rotate: int = 0) -> list[str]:
    """Build the tree route's header: ``n`` input cells, a right push each.

    Each cell's hook lands one column left, so the cells sit on a diagonal
    and the last exits heading down at column 3.  With ``rotate`` set,
    input ``rotate - 1``'s hook pushes a second R, the stop heading
    :func:`_rotation` pops; the hook widens into the blank left of it.
    """
    rows = [" " * (n + 3) + "*"]
    for i in range(n):
        x = n + 3 - i  # input ``i``'s column
        pushes = "~~" if i == rotate - 1 else "~"
        left = x - 2 - len(pushes)
        rows.append(" " * left + "*" + pushes + "*" + TEMPLATE_CHAR)
        rows.append(" " * left + "*" + " " * (x - left - 1) + "*")
    return rows


def _rotation(k: int) -> list[str]:
    """Re-enqueue the ``k`` inputs queued first behind the rest.

    One gadget per input, entered on its ``+``: a ``0``'s R re-pushes on
    the right, a ``1``'s D re-pushes going down and its R after the lower
    ``+``, and both exits meet on the next gadget's ``+``, which pops on
    arrival from any heading.  The last ``+`` pops the header's stop
    heading, and the ``*`` beyond it turns into the middle's first corner,
    moved right.  So these rows replace the middle's first two, the first
    shared with the chain's last.
    """
    grid = [[" "] * (5 + 2 * k) for _ in range(2 * k + 2)]
    for g in range(k):
        r, c = 2 * g, 3 + 2 * g
        grid[r][c : c + 3] = "+~*"
        grid[r + 1][c] = "~"
        grid[r + 2][c : c + 2] = "+~"
    grid[2 * k][:3] = _MIDDLE[0][:3]
    grid[2 * k][3 + 2 * k : 5 + 2 * k] = "+*"
    grid[2 * k + 1][0] = grid[2 * k + 1][4 + 2 * k] = "*"
    return ["".join(row).rstrip() for row in grid]


def _connect(t0: list[str], t1: list[str]) -> list[str]:
    """Connect two decision subtrees into one.

    0-branch top-left, ``t0`` at its right exit, 1-branch below ``t0``,
    ``t1`` at its right exit.
    """
    yb = len(t0)  # the 1-branch's top row: one row below ``t0``
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
    gets a ``+`` whose two exits reconverge on one cell (a ``+`` pops on
    arrival from any heading), stepping one row down and one column right.
    """
    # A ``0`` leaf needs no drain (running off the grid halts regardless),
    # and a drain costs ``_compact`` blank columns.
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


def arrowqueue(truth_table: str) -> str:
    """Build an ArrowQueue template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    instantiated program halts iff the entry is ``0``.  Below five inputs a
    tree with 3x3 leaves, constant subtrees folded (:func:`_drained_leaf`);
    from five a cascade of at most ``6n`` + ``3 * 2**n`` rows, linear in the
    table, its constant tail folded (:func:`_cascade`).

    The tree tests the inputs in any rotation of their read order, the
    shortest of the ``n <= 4`` candidates (:func:`_rotated_tree`).
    """
    n = _validate_truth_table(truth_table)
    if len(truth_table) > 16:
        rows = ["  ~*", *(_STAGE * n), *_MIDDLE, *_cascade(truth_table)]
        return "\n".join(row.rstrip() for row in rows)
    # ``min`` keeps the first of equals, so a rotation must strictly win.
    return min((_rotated_tree(truth_table, n, k) for k in range(n)), key=len)


def _rotated_tree(truth_table: str, n: int, k: int) -> str:
    """Build the tree route testing input ``k`` first, read order unchanged.

    The reads still queue inputs ``0 .. n-1``; :func:`_rotation` moves the
    first ``k`` behind the rest, so level ``j`` splits on input
    ``(k + j) % n``.  The gadgets cost 19, 39 and 63 characters at
    ``k = 1, 2, 3``, against what the rotated tree folds.
    """
    order = (*range(k, n), *range(k))
    body = _compact(_MIDDLE + _tree(list(permute_truth_table(truth_table, order))))
    if k:
        # Compaction keeps the middle's four columns, so its rows lead.
        body[:2] = _rotation(k)
    return "\n".join([*_header(n, k), *body])


def _cascade(truth_table: str) -> list[str]:
    """Build the cascade's rows, the table's constant tail folded.

    Only an index inside the tail reaches a row past the tail's first, so
    the tail's answer needs no further count.  A ``0`` tail is dropped:
    the descent runs off the grid, which halts.  A ``1`` tail is one
    :data:`_DRAINED_RING`, which pops the markers the dropped rows would
    have.  The tree's drains cannot loop so: its queue has no stop heading.
    """
    tail = len(truth_table.rstrip(truth_table[-1]))
    rows = [row for bit in truth_table[:tail] for row in _ROWS[bit]]
    return [*rows, *_DRAINED_RING] if truth_table[-1] == "1" else rows


def _compact(rows: list[str]) -> list[str]:
    """Drop the wholly blank rows and columns from the template's body.

    A blank line carries only straight travel.  The header is not
    consulted: its glyphs sit past column 4, which every branch marks.
    """
    width = max((len(row) for row in rows), default=0)
    padded = [row.ljust(width) for row in rows]
    kept = [row for row in padded if row.strip()]
    if not kept:
        return []  # pragma: no cover - every table lays a cell
    columns = [x for x in range(width) if any(row[x] != " " for row in kept)]
    return ["".join(row[x] for x in columns).rstrip() for row in kept]
