"""Boolean-function generator for ABCDirection.

ABCDirection is a grid language, so the generator lays out a decision tree
as a walkable diagram: :class:`_Builder` accumulates the grid while
:func:`_build_node` and :func:`_leaf` place each node's staircase and its
leaf, one input consumed per level.
"""

from dataclasses import dataclass

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["abcdirection"]


# --- ABCDirection (grid, merged from booleans/abcdirection.py) ---

_R, _D, _L, _U = 0, 1, 2, 3
_DIR = [(1, 0), (0, 1), (-1, 0), (0, -1)]


@dataclass
class _LeafParams:
    """Layout parameters threaded into the tree/leaf builders."""

    escape_rows: list[int]
    sink_cols: list[int]
    serp_col: int
    sp: int


class _Builder:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.cells: dict[tuple[int, int], str] = {}

    def set(self, x: int, y: int, c: str) -> None:
        if not 0 <= x < self.width:
            raise AssertionError((x, y))
        if not 0 <= y < self.height:
            raise AssertionError((x, y))
        old = self.cells.get((x, y))
        if old is not None and old != c:
            raise AssertionError(("collision", (x, y), old, c))
        self.cells[(x, y)] = c

    def grid(self) -> list[str]:
        g = [["B"] * self.width for _ in range(self.height - 1)]
        for (x, y), c in self.cells.items():
            if y == self.height - 1:
                continue
            g[y][x] = c
        term = ["B"] * self.width
        for (x, y), c in self.cells.items():
            if y == self.height - 1:
                term[x] = c
        term[self.width - 6 : self.width] = ["D"] * 6
        rows = ["".join(r) for r in g]
        rows.append("".join(term))
        return _compact(rows)


def _compact(rows: list[str]) -> list[str]:
    """Drop every dead row, and every dead column that is safe to drop.

    The layout reserves whole rows and columns it never writes to -- the
    tree's node slots are ``sp`` apart but a node occupies a couple of
    dozen columns, and a leaf's band is 52 rows apart but only tens deep.
    Deleting an all-``B`` row or column is behaviour-preserving: ``B`` is a
    no-op, every turn happens at a live cell, and deleting a whole line
    shifts every live cell on one side of it together, so the beam's
    relative geometry -- and the row-0/bottom-row wraps it relies on -- is
    unchanged.  Only ``_travel`` counts cells, and that runs here at
    construction time, not at run time.

    The one hazard is horizontal.  :func:`_parse` ends the program at the
    first ``DDDDDD``, so closing the gap between two ``D`` cells can forge a
    terminator: the node dequeue runs space their ``D``\\ s two apart for
    exactly this reason, and the last EOF sink sits one ``B`` clear of the
    real terminator.  A column is therefore dropped only when no row grows a
    six-``D`` run without it.  Rows need no such test, since the terminator
    is read along a row.
    """
    rows = [row for row in rows if row.count("B") != len(row)]
    width = len(rows[0])
    keep = list(range(width))
    dead = [x for x in range(width) if all(row[x] == "B" for row in rows)]

    for x in dead:
        trial = [c for c in keep if c != x]
        merged = ["".join(row[c] for c in trial) for row in rows]
        # The real terminator is the trailing run on the last row; a run
        # anywhere else would truncate the program when it is parsed back.
        last = len(merged) - 1
        if any(
            "DDDDDD" in (line[:-6] if i == last else line)
            for i, line in enumerate(merged)
        ):
            continue
        keep = trial
    return ["".join(row[c] for c in keep) for row in rows]


def _turn(b: _Builder, x: int, y: int, h: int, target: int) -> tuple[int, int, int]:
    while h != target:
        b.set(x, y, "A")
        h = (h + 1) % 4
        x += _DIR[h][0]
        y += _DIR[h][1]
    return x, y, h


def _here(b: _Builder, x: int, y: int, h: int, cell: str) -> tuple[int, int]:
    b.set(x, y, cell)
    x += _DIR[h][0]
    y += _DIR[h][1]
    return x, y


def _travel(b: _Builder, x: int, y: int, h: int, dist: int) -> tuple[int, int]:
    for _ in range(dist):
        x = (x + _DIR[h][0]) % b.width
        y = (y + _DIR[h][1]) % b.height
    return x, y


def _add_staircase(
    b: _Builder, n: int, right: int = 6, up: int = 3, d: int = 2
) -> tuple[int, int, int]:
    """Read phase: [D-up read, D-right enqueue] x 8n pairs rising rightward."""
    pairs = 8 * n
    b.set(0, 0, "A")
    b.set(5, 0, "A")
    ex, ey = 5, b.height - 1
    a3 = (ex + right - 1, ey - up + d)
    for i in range(pairs):
        if i == 0:
            b.set(5, b.height - 1, "D")
        if i:
            b.set(ex, ey - 1, "D")
        b.set(ex, ey - 1 - up, "A")
        b.set(ex + right // 2, ey - 1 - up, "D")
        b.set(ex + right, ey - 1 - up, "A")
        b.set(ex + right, ey - up + d, "A")
        a3 = (ex + right - 1, ey - up + d)
        b.set(*a3, "A")
        ex += right - 1
        ey -= up - d
    return a3[0], a3[1] - 1, _U


def _build_node(
    b: _Builder,
    n: int,
    table: str,
    depth: int,
    p: int,
    x: int,
    y: int,
    combo: int,
    path: tuple[int, ...],
    leaf_params: _LeafParams,
) -> None:
    """Place a tree node: k D-left's, a turn, a C-up test, then children.

    The D-left's are spaced one cell apart so no six-D run forms (the grid
    reader would mistake it for the terminator).  Entering a node dequeues k
    bits into the tape and the C-up tests the last one, so each node consumes
    the next input bit's slot.
    """
    k = 1 if depth == 0 else 8
    for j in range(k):
        b.set(x - 2 * j, y, "D")
    b.set(x - 2 * k, y, "A")
    b.set(x - 2 * k, y - 1, "C")
    if depth == n - 1:
        _leaf(b, table, x - 2 * k, y - 2, _U, combo, (*path, 0), leaf_params)
        _leaf(
            b,
            table,
            x - 2 * k - 1,
            y - 1,
            _L,
            combo | (1 << (n - 1 - depth)),
            (*path, 1),
            leaf_params,
        )
        return
    sp = leaf_params.sp
    delta = 2 ** (n - depth - 2) * sp
    band = 8
    # zero-child (continue UP from the C-up), at x + delta: travel RIGHT to
    # just past the child, DOWN, then LEFT into it.
    zx, zy, zh = x - 2 * k, y - 2, _U
    zx, zy, zh = _turn(b, zx, zy, zh, _R)
    zx, zy = _travel(b, zx, zy, _R, delta + 2 * k)
    zx, zy, zh = _turn(b, zx, zy, zh, _D)
    zx, zy = _travel(b, zx, zy, _D, band + 1)
    zx, zy, zh = _turn(b, zx, zy, zh, _L)
    _build_node(
        b,
        n,
        table,
        depth + 1,
        2 * p,
        x + delta,
        y + band,
        combo,
        (*path, 0),
        leaf_params,
    )
    # one-child (turn LEFT from the C-up), at x - delta: travel LEFT, turn,
    # DOWN, then LEFT into it.
    ox, oy, oh = x - 2 * k - 1, y - 1, _L
    ox, oy = _travel(b, ox, oy, _L, delta - 2 * k - 1)
    ox, oy, oh = _turn(b, ox, oy, oh, _D)
    ox, oy = _travel(b, ox, oy, _D, band + 1)
    ox, oy, oh = _turn(b, ox, oy, oh, _L)
    _build_node(
        b,
        n,
        table,
        depth + 1,
        2 * p + 1,
        x - delta,
        y + band,
        combo | (1 << (n - 1 - depth)),
        (*path, 1),
        leaf_params,
    )


def _leaf(
    b: _Builder,
    table: str,
    x: int,
    y: int,
    entry_heading: int,
    combo: int,
    path: tuple[int, ...],
    leaf_params: _LeafParams,
    leg: int = 2,
) -> None:
    """Route a branch DOWN to its escape row, then output [f, padding]."""
    f = int(table[combo])
    last = path[-1]
    flip = f != last
    flip_row = leaf_params.escape_rows[combo]
    serp_col = leaf_params.serp_col
    sink_col = leaf_params.sink_cols[combo]
    cx, cy, ch = x, y, entry_heading
    # Route DOWN at a clear column (left of this node's D-left cells) to just
    # below the leaf's flip row; the turn to RIGHT shifts one row up.
    if entry_heading == _U:
        cx, cy, ch = _turn(b, cx, cy, ch, _R)
        cx, cy, ch = _turn(b, cx, cy, _R, _D)
    else:
        cx, cy = _travel(b, cx, cy, _L, 1)
        cx, cy, ch = _turn(b, cx, cy, ch, _D)
    cx, cy = _travel(b, cx, cy, _D, flip_row + 1 - cy)
    cx, cy, ch = _turn(b, cx, cy, _D, _R)
    cx, cy = _travel(b, cx, cy, _R, serp_col - cx)
    # Serpentine entry: heading RIGHT at (serp_col, flip_row).
    if flip:
        cx, cy = _here(b, cx, cy, _R, "C")  # cell -= 1
        cx, cy, ch = _turn(b, cx, cy, _R, _L)
        cx, cy = _here(b, cx, cy, _L, "C")  # cell += 1, flip
        cx, cy = _travel(b, cx, cy, _L, 2)
        cx, cy, ch = _turn(b, cx, cy, _L, _U)
        cx, cy = _travel(b, cx, cy, _U, 2)
        cx, cy, ch = _turn(b, cx, cy, _U, _D)
        cx, cy = _travel(b, cx, cy, _D, 3)
    else:
        cx, cy, ch = _turn(b, cx, cy, _R, _D)
    cx, cy = _here(b, cx, cy, _D, "C")
    for _ in range(7):
        cx, cy, ch = _turn(b, cx, cy, _D, _L)
        cx, cy = _travel(b, cx, cy, _L, leg)
        cx, cy = _here(b, cx, cy, _L, "D")
        cx, cy = _travel(b, cx, cy, _L, leg)
        cx, cy, ch = _turn(b, cx, cy, _L, _D)
        cx, cy = _travel(b, cx, cy, _D, leg)
        cx, cy = _here(b, cx, cy, _D, "C")
        cx, cy = _travel(b, cx, cy, _D, leg)
    # EOF sink: travel RIGHT to this leaf's D column, run UP to row 0, and the
    # next step wraps into row H-1 where a D cell reads input -> EOFError.
    cx, cy, ch = _turn(b, cx, cy, _D, _R)
    cx, cy = _travel(b, cx, cy, _R, sink_col - cx)
    cx, cy, ch = _turn(b, cx, cy, _R, _U)
    cx, cy = _travel(b, cx, cy, _U, cy)
    b.set(sink_col, b.height - 1, "D")


def abcdirection(truth_table: str) -> str:
    """Build an ABCDirection program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    """
    n = _validate_truth_table(truth_table)
    leaves = 2**n
    sp = 36  # column spacing between adjacent tree nodes at the same depth
    # Clearance between the tree's leftmost descent column and the climb the
    # beam runs up at x = 2.  This was 100, which read like a border keeping
    # the tree off the read staircase; it is not doing that job.  The
    # staircase reaches column 40n + 6 and so already shares columns with the
    # tree from n = 3 on, and what separates them there is rows -- the tree's
    # descents stop at their flip rows, some forty rows above the staircase's
    # first cell.  Only written cells execute, so a beam crossing those
    # columns in between is harmless.
    margin = 18
    # The beam leaves the read staircase near the bottom of the grid, climbs
    # to ``turn_row``, runs right to the tree's column, and drops back to
    # ``root_row`` to enter the tree from above.  Both were 600 and 709,
    # which reserved ~700 rows for a detour that only ever puts one turn
    # cell on one row: the staircase it is clearing sits at the *bottom* of
    # the grid, so there is nothing up there to clear.  Since ``height`` is
    # ``root_row`` plus the leaf bands plus a tail, that constant alone was
    # about two thirds of every program.
    turn_row = 2
    root_row = turn_row + 8  # the tree starts just below the turn

    root_x = margin + leaves // 2 * sp
    tree_bottom = root_row + 8 * (n - 1)  # deepest row the tree itself reaches
    # The tree's rightmost leaf sits (leaves - 1 - leaves // 2 + 0.5) node
    # slots to the right of root_x; that offset is always a half-integer
    # (leaves is a power of two), so round() picks the nearest whole slot
    # deterministically rather than needing a floor/ceil choice here.
    tree_right_offset = round((leaves - 1 + 0.5) - leaves // 2)
    tree_max = root_x + tree_right_offset * sp
    serp_col = tree_max + 40  # serpentine output track, right of the tree
    escape_rows = [tree_bottom + 8 + 52 * i for i in range(leaves)]
    sink_cols = [serp_col + 30 + 8 * i for i in range(leaves)]
    # Both extents are measured from the rightmost/lowest thing placed rather
    # than guessed, since a formula that merely runs parallel to the layout
    # drifts away from it as n grows.  The old width counted 60 columns per
    # leaf while the sinks it has to contain are 8 apart, so the overshoot
    # widened with n: 65 dead columns at n = 3, 193 at n = 4.
    #
    # The last sink's D must not touch the terminator.  ``_parse`` stops at
    # the *first* DDDDDD, so a sink D flush against the run would match one
    # column early and silently shrink every parsed row; the B between them
    # costs a column and removes that coupling.
    width = sink_cols[-1] + 1 + 6 + 1
    # A serpentine band reaches ``band_depth`` rows below its escape row.
    # The 52-row pitch between bands stays: a leaf that flips its bit backs
    # up two rows above its own escape row, so consecutive bands already sit
    # within a couple of rows of each other.  Only the tail was slack --
    # after the last band there were 164 blank rows, at every n, before the
    # staircase began.
    band_depth = 40
    # The staircase is built upward from the bottom row and spans 8n + 8:
    # 8n read pairs plus the entry cell below and the exit cells above.
    stair_rows = 8 * n + 8
    # The staircase exit climbs six rows above its top cell and turns there,
    # so those rows belong to the staircase rather than to the last band.
    exit_clearance = 8
    height = escape_rows[-1] + band_depth + exit_clearance + stair_rows
    b = _Builder(width, height)
    ex, ey, eh = _add_staircase(b, n)
    x, y, h = ex, ey, eh
    x, y = _travel(b, x, y, _U, 6)
    x, y, h = _turn(b, x, y, h, _L)
    x, y = _travel(b, x, y, _L, max(0, x - 2))
    x, y, h = _turn(b, x, y, h, _U)
    x, y = _travel(b, x, y, _U, max(0, y - turn_row))
    x, y, h = _turn(b, x, y, h, _R)
    x, y = _travel(b, x, y, _R, root_x + 1 - x)
    x, y, h = _turn(b, x, y, h, _D)
    x, y = _travel(b, x, y, _D, max(0, root_row - y))
    x, y, h = _turn(b, x, y, h, _L)
    leaf_params = _LeafParams(
        escape_rows=escape_rows,
        sink_cols=sink_cols,
        serp_col=serp_col,
        sp=sp,
    )
    _build_node(b, n, truth_table, 0, 0, root_x, root_row, 0, (), leaf_params)
    return "\n".join(b.grid())
