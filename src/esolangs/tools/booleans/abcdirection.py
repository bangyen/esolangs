"""Boolean-function generator for ABCDirection.

ABCDirection routes a pointer around a rectangular grid of ``A``/``B``/
``C``/``D`` cells (a donut), with ``D``-up reading an input bit, ``D``-right
enqueueing into a bit queue, ``D``-left dequeuing into the current tape cell,
``C``-down outputting the current tape bit, and ``C``-up turning the pointer
on a one.  There is no halt: the program reads the input into a queue, routes
a decision tree over the queue (each node dequeues the next bit and tests it
with ``C``-up), and the fired leaf outputs ``48 + f`` as a byte before
running off the terminator row and raising :class:`EOFError` (the harness
treats that as normal termination).

The layout: a read staircase at the bottom fills the queue, a corridor routes
the pointer around the tree to the root, the tree's ``D``-left cells are
spaced one cell apart so no six-``D`` run forms (the grid reader would
mistake it for the terminator), and each leaf serpentine outputs the answer
byte before diverting to the terminator's ``D`` run.
"""

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = ["abcdirection"]

_R, _D, _L, _U = 0, 1, 2, 3
_DIR = [(1, 0), (0, 1), (-1, 0), (0, -1)]


class _Builder:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.cells: dict[tuple[int, int], str] = {}

    def set(self, x: int, y: int, c: str) -> None:
        assert 0 <= x < self.width, (x, y)
        assert 0 <= y < self.height, (x, y)
        old = self.cells.get((x, y))
        assert old is None or old == c, ("collision", (x, y), old, c)
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
        return rows


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
    x: int,
    y: int,
    combo: int,
    path: tuple[int, ...],
    leaf_rows: dict[int, tuple[int, int]],
) -> None:
    """Place a tree node: k D-left's, a turn, a C-up test, then children.

    The D-left's are spaced one cell apart so no six-D run forms (the grid
    reader would mistake it for the terminator).
    """
    k = 1 if depth == 0 else 8
    for j in range(k):
        b.set(x - 2 * j, y, "D")
    b.set(x - 2 * k, y, "A")
    b.set(x - 2 * k, y - 1, "C")
    if depth == n - 1:
        _leaf(b, table, x - 2 * k, y - 2, _U, combo, (*path, 0), leaf_rows)
        _leaf(
            b,
            table,
            x - 2 * k - 1,
            y - 1,
            _L,
            combo | (1 << (n - 1 - depth)),
            (*path, 1),
            leaf_rows,
        )
        return
    zx, zy, zh = x - 2 * k, y - 1, _U
    zx, zy = zx, zy - 1
    zx, zy, zh = _turn(b, zx, zy, zh, _R)
    zx, zy = _travel(b, zx, zy, _R, 3)
    zx, zy, zh = _turn(b, zx, zy, zh, _D)
    zx, zy = _travel(b, zx, zy, _D, 4)
    zx, zy, zh = _turn(b, zx, zy, zh, _L)
    _build_node(b, n, table, depth + 1, zx - 1, zy, combo, (*path, 0), leaf_rows)
    _build_node(
        b,
        n,
        table,
        depth + 1,
        x - 2 * k - 1,
        y - 1,
        combo | (1 << (n - 1 - depth)),
        (*path, 1),
        leaf_rows,
    )


def _leaf(
    b: _Builder,
    table: str,
    x: int,
    y: int,
    entry_heading: int,
    combo: int,
    path: tuple[int, ...],
    leaf_rows: dict[int, tuple[int, int]],
    leg: int = 2,
) -> None:
    """Route a branch into a leaf band and output [f, padding...]."""
    f = int(table[combo])
    last = path[-1]
    flip = f != last
    band_y, band_x = leaf_rows[combo]
    cx, cy, ch = x, y, entry_heading
    if entry_heading == _U:
        cx, cy, ch = _turn(b, cx, cy, ch, _R)
        cx, cy = _travel(b, cx, cy, _R, band_x - cx)
        cx, cy, ch = _turn(b, cx, cy, _R, _U)
        cx, cy = _travel(b, cx, cy, _U, cy - band_y)
        cx, cy, ch = _turn(b, cx, cy, _U, _R)
    else:
        # one side: turned LEFT from the C-up.  Step left one column so the
        # upward path runs in a clear column (the tree's D-left cells sit on
        # the branch column and would be read as input).
        cx, cy = _travel(b, cx, cy, _L, 1)
        cx, cy, ch = _turn(b, cx, cy, _L, _U)
        cx, cy = _travel(b, cx, cy, _U, cy - band_y)
        cx, cy, ch = _turn(b, cx, cy, _U, _R)
        cx, cy = _travel(b, cx, cy, _R, band_x - cx)
    if flip:
        cx, cy = _here(b, cx, cy, _R, "C")
        cx, cy, ch = _turn(b, cx, cy, _R, _L)
        cx, cy = _here(b, cx, cy, _L, "C")
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
    # EOF sink: travel DOWN (wrapping past the bottom) to this leaf's sink
    # row, turn RIGHT, travel RIGHT to this leaf's sink column, turn UP, and
    # the wrap into row H-1 reads at the terminator D cells -> EOFError.  The
    # sink columns are distinct per leaf so the turn cells never sit on
    # another leaf's upward path.
    sink_row = 2 + 10 * combo
    sink_col = 214 + combo
    cx, cy = _travel(b, cx, cy, _D, b.height + sink_row - cy)
    cx, cy, ch = _turn(b, cx, cy, _D, _R)
    cx, cy = _travel(b, cx, cy, _R, sink_col + 1 - cx)
    cx, cy, ch = _turn(b, cx, cy, _R, _U)
    cx, cy = _travel(b, cx, cy, _U, sink_row)


def abcdirection(truth_table: str, n: int) -> str:
    """Build an ABCDirection program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    The program reads ``8*n`` bits (one byte per input) into its queue, then
    routes a decision tree over the queued bits: each node dequeues the next
    bit and tests it with ``C``-up.  The fired leaf prints ``48 + f`` as a
    byte and runs off the terminator row, raising :class:`EOFError`, which
    the harness treats as termination.  The tree's ``D``-left cells are
    spaced one cell apart so no six-``D`` run forms (the grid reader would
    mistake it for the terminator).

    The current layout is verified for ``n <= 2`` (all one- and two-input
    functions).  Deeper trees route the leaves and internal paths through the
    tree's own cells and are not yet correct, so ``n > 2`` raises
    :class:`ValueError`.
    """
    _validate_truth_table(truth_table, n)
    if n > 2:
        raise ValueError(
            "the ABCDirection boolean generator currently supports n <= 2: "
            "deeper trees route the leaves and internal paths through the "
            "tree's own cells",
        )
    b = _Builder(220, 840)
    ex, ey, eh = _add_staircase(b, n)
    x, y, _ = ex, ey, eh
    x, y = _travel(b, x, y, _U, max(0, y - 713))
    x, y, _ = _turn(b, x, y, _U, _L)
    x, y = _travel(b, x, y, _L, max(0, x - 30))
    x, y, _ = _turn(b, x, y, _L, _U)
    x, y = _travel(b, x, y, _U, max(0, y - 600))
    x, y, _ = _turn(b, x, y, _U, _R)
    x, y = _travel(b, x, y, _R, 95 - x)
    x, y, _ = _turn(b, x, y, _R, _D)
    x, y = _travel(b, x, y, _D, max(0, 709 - y))
    x, y, _ = _turn(b, x, y, _D, _L)
    root_x, root_y = x, y
    leaf_rows = {i: (200 + i * 50, 100 + i * 40) for i in range(2**n)}
    _build_node(b, n, truth_table, 0, root_x, root_y, 0, (), leaf_rows)
    return "\n".join(b.grid())
