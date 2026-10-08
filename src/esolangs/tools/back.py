"""Boolean-function generator for Back."""

from itertools import pairwise

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    input_weights,
    move_text,
    subtree_ids,
)

#: Finisher for a cell primed to 1: ``-`` flips it to 0, ``+`` is inert.
#: Both are one grid cell, so a run is the exact width of its program.
PAIR = ("-", "+")
_BACK_INPUT = TEMPLATE_CHAR
_WRAP_ROWS = 8
_MIRROR = {"/": "\\", "\\": "/"}


def _render(rows: list[dict[int, str]]) -> str:
    """Join sparse rows, gaps blank, each row only as long as its last cell."""
    return "\n".join(
        "".join(cells.get(x, " ") for x in range(max(cells, default=-1) + 1))
        for cells in rows
    )


def _reflect_back(grid: dict[tuple[int, int], str], height: int, width: int) -> str:
    r"""Reflect a Back template and route the fixed eastward start into it.

    ``grid`` maps ``(row, column)`` to a character; ``width`` is the widest
    row.  An input's run is one grid cell like every other character, so
    reflection reverses cells.  Only the beam mirrors swap; ``<`` and ``>``
    move the tape head and keep their meanings.  Rendered from the sparse
    cells, each row only as long as its last one, so the cost is the
    output's size rather than the bounding box (``2**n`` rows by ``4n``).
    """
    rows: list[dict[int, str]] = [{} for _ in range(height)]
    for (row, column), cell in grid.items():
        rows[row][width - column] = _MIRROR.get(cell, cell)

    # East, south, wrap west, north, west into the reflected root.  The two
    # extra columns touch only rows 0-1; tree padding is trailing and rstrips.
    rows[0][0] = rows[0][width + 1] = "\\"
    rows[1][0] = "/"
    rows[1][width + 1] = "\\"
    return _render(rows)


def _descending_back(grid: dict[tuple[int, int], str], units: list[str]) -> str:
    """Reflect the tree below a downward loader, without outer entry columns."""
    top = len(units) + 1
    last = max(column for _, column in grid)
    rows: dict[int, dict[int, str]] = {0: {last: "\\"}}
    for row, unit in enumerate(units, 1):
        rows[row] = {last: unit}
    rows[top] = {last: "/"}
    for (row, column), char in grid.items():
        rows.setdefault(top + row, {})[last - column] = _MIRROR.get(char, char)
    return _render([rows.get(y, {}) for y in range(max(rows) + 1)])


def _back_parity(truth_table: str, n: int) -> str | None:
    """Return a one-column parity accumulator, or None for another function."""
    bias = int(truth_table[0])
    parity = bytearray(len(truth_table))
    for row in range(1, len(truth_table)):
        parity[row] = parity[row >> 1] ^ (row & 1)
        if int(truth_table[row]) != parity[row] ^ bias:
            return None
    # The primer flips the accumulator. Zero flips it back; one keeps it,
    # and its possible skip consumes only the blank spacer, not the next bit.
    rows = ["\\", *(">" * n), *(["-"] if bias else [])]
    for _ in range(n):
        rows.extend(("-", _BACK_INPUT, " "))
    return "\n".join([*rows, "*"])


def back(truth_table: str, width: int | None = None, *, wrap: bool = True) -> str:
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    Width puts the loader above the tree, removing two entry columns.
    Unfitting parity tables use a one-column accumulator in answer cell n;
    earlier cells remain scratch rather than carrying the inputs.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell over two load rows: a constant ``-`` primes the
    cell to 1 for either bit, then the input's run finishes it -- ``+`` (inert on
    a set cell) for a one, ``-`` (flipping it back) for a zero.  So cells
    ``0..n-1`` hold the inputs and cell ``n`` is the answer cell.  Both
    bits cost the same two rows, so the height cannot leak an input.

    A decision node is ``+\>``: ``+`` tests the current tape bit (advancing
    the beam straight past the ``\`` when it is 0) and ``\`` reflects the
    beam down when it is 1, while ``>`` advances the tape pointer to the next
    input.  Both branches advance the pointer once, so a leaf at depth ``d``
    has the pointer at cell ``d``.  A leaf walks to cell ``n``, flips it with
    ``-`` when its value is 1, and halts.

    The load runs *down column 0* and the tree starts at column 1, so no row
    carries the load's width as indent.  A ``/`` at the origin does both
    turns: the beam starts heading right, the ``/`` sends it up and off the
    top edge onto the bottom row, it runs the load upward back to the origin,
    and the ``/`` -- now taking a beam heading up -- turns it right into the
    tree.  The load is written bottom-to-top, and the drawing is reflected
    for output, so the tree grows left and its triangular padding lands at
    line ends where it is stripped.  A two-row outer route converts Back's
    fixed eastward start into the westward entry the reflected root needs.

    The answer is the *value* of cell ``n``, which the halt dump prints;
    the head's position is not printed.

    A node whose one-subtree equals the zero-subtree of the next node on its
    level draws none: the beam falls down the column onto that node's mirror,
    the first cell below, and turns east into the zero side.  The column
    wraps, so the level's last node reaches its first the same way, from eight
    rows up.  Other repeats are drawn again: bending the beam round column 1,
    the one lane free below the root, to any mirror in its column saves 0.7 /
    0.8 more points of characters (tiled, n=8/9) but takes the worst commands
    from 122 / 221 to 154 / 306 at n=6/7, since a bend walks the distance
    between the nodes.  Area (rows x longest row), seeded tables, n=6/7:
    random -21.9% / -23.6%, tiled from two random blocks -17.5% / -35.8%,
    constant half 0% / -13.1%; n <= 5 is unchanged, the load column setting
    the height.  The wrap, over the next-node fall alone, n=8/9: tiled -9.7% /
    -6.6% of characters (-16.5% / -9.7% of area), random and constant half 0%.
    """
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    if len(table) == 1:
        # A constant already folds to one leaf; it keeps every input.
        weights, table = [1] * n, truth_table
    levels = len(table).bit_length() - 1
    # A wrapped fall only removes rows; the shorter build, the plain one on a
    # tie, is the guard that no table grows.
    program = min(
        (
            _back_ordered(table, tuple(range(levels)), width, weights, wrap=w)
            for w in ((False, True) if wrap else (False,))
        ),
        key=len,
    )
    if width is not None and width > 0 and max(map(len, program.splitlines())) > width:
        parity = _back_parity(truth_table, n)
        if parity is not None:
            return parity
    return program


def _back_ordered(
    truth_table: str,
    perm: tuple[int, ...],
    width: int | None = None,
    weights: list[int] | None = None,
    *,
    wrap: bool = False,
) -> str:
    r"""Build one Back template, loading its inputs in ``perm`` order.

    ``truth_table`` is already permuted, so row indices are in the permuted
    frame; ``perm`` only picks the cell each input loads into.

    A node tests the current cell, *then* advances, so level ``k`` tests cell
    ``k`` and input ``perm[k]`` must load there -- one cell lower than
    Streetcode's halls and LaserFuck's ``>#v)``, which test cell ``k + 1``.
    Getting it wrong computes a different function.

    The load runs the inputs in name order (run k *is* input k) and walks the
    pointer to cell ``perm.index(i)``, the inverse permutation; reading
    ``perm`` forward computes a different function.  Filling in cell order
    needs no walk and screens 12.0% against 9.15% here, but breaks name
    order.  The walk is ``4n - 2`` moves, 10 of the 236 characters at n=3.
    A ``-``/run pair is never split, so both bits still cost two rows.

    ``weights`` names the stream inputs, zero for an ignored one: the table
    indexes the rest, and the answer cell stays at the stream's input count.
    An ignored input's run lands on the empty cell the next load fills and
    a ``-`` follows it: a zero's ``-`` sets the cell and the ``-`` clears it,
    a one's ``+`` meets the empty cell and skips the ``-``.  Two rows, no
    walk, and the cell is empty again.
    """
    levels = _validate_truth_table(truth_table)
    if weights is None:
        weights = [1] * levels
    n = len(weights)

    # Level c tests cell c and input perm[c], so input i lives at cell
    # perm.index(i).
    essential = [i for i, weight in enumerate(weights) if weight]
    cells = [levels] * n
    for level, i in enumerate(perm):
        cells[essential[i]] = level

    def walk(frm: int, to: int) -> list[str]:
        """Move the pointer from cell ``frm`` to cell ``to``, one per row."""
        return list(move_text(frm, to, ">", "<"))

    def load(order: list[int]) -> list[str]:
        """Load the inputs in ``order``, then open the answer cell and home."""
        # An ignored input borrows the cell loaded after it, or a spare one.
        borrowed = dict(enumerate(cells))
        spare = levels
        for i in reversed(order):
            if weights[i]:
                spare = cells[i]
            borrowed[i] = spare
        units: list[str] = []
        at = 0
        for i in order:
            # Primer '-' then the run, one row each (the beam reads one cell
            # per row).  Bit on the trailing row so every load row executes;
            # the walk goes before the pair, never between, or the height
            # leaks the bit.
            units.extend(walk(at, borrowed[i]))
            units.extend(("-", _BACK_INPUT) if weights[i] else (_BACK_INPUT, "-"))
            at = borrowed[i]
        units.extend(walk(at, n))
        units.extend("<" * n)
        return units

    # Reverse name order: the load is drawn bottom-up in column 0, so this
    # emits input 0 first.
    units = load(list(range(n - 1, -1, -1)))

    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)

    def draw(
        shared: set[tuple[int, int]], *, vertical: bool
    ) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], tuple[int, int]]]:
        """Draw the tree; return its cells and each node's cell by (level, block).

        A node in ``shared`` draws no one-subtree: its mirror drops the beam down
        the column to the next mirror below, the zero-side entry of the next
        node on that level.
        """
        grid: dict[tuple[int, int], str] = {}
        where: dict[tuple[int, int], tuple[int, int]] = {}
        next_row = [1]

        def leaf(level: int, value: str, row: int, col: int) -> None:
            # Walk to cell n, flip it (starts 0) for a 1-leaf, halt.
            code = ">" * (n - level) + ("-" if value == "1" else "") + "*"
            if vertical:
                # Reserved DFS rows turn leaf finishers down without widening the tree.
                grid[(row, col)] = "\\"
                for k, ch in enumerate(code, 1):
                    grid[(row + k, col)] = ch
                next_row[0] = max(next_row[0], row + len(code) + 1)
            else:
                for k, ch in enumerate(code):
                    grid[(row, col + k)] = ch

        def emit(level: int, lo: int, hi: int, row: int, col: int) -> None:
            if level == levels or constant(lo, hi):
                leaf(level, truth_table[lo], row, col)
                return
            mid = lo + (hi - lo) // 2
            grid[(row, col)] = "+"
            grid[(row, col + 1)] = "\\"
            grid[(row, col + 2)] = ">"
            block = lo >> (levels - level)
            where[level, block] = (row, col + 1)
            emit(level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight
            if (level, block) in shared:
                return
            nrow = next_row[0]
            next_row[0] += 1
            grid[(nrow, col + 1)] = "\\"
            grid[(nrow, col + 2)] = ">"
            emit(level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child

        # Tree root at column 1, the beam arriving rightward.
        emit(0, 0, 2**levels, 0, 1)
        return grid, where

    def level_order(k: int, shared: set[tuple[int, int]]) -> list[int]:
        """Return level ``k``'s nodes in text order, one-subtrees of ``shared`` cut."""
        order: list[int] = []

        def walk(level: int, block: int) -> None:
            size = 2 ** (levels - level)
            if level == levels or constant(block * size, (block + 1) * size):
                return
            if level == k:
                order.append(block)
            walk(level + 1, 2 * block)
            if (level, block) not in shared:
                walk(level + 1, 2 * block + 1)

        walk(0, 0)
        return order

    def plan(*, vertical: bool) -> set[tuple[int, int]]:
        """Pick the nodes whose one-edge can fall onto an equal zero-side subtree.

        Level by level: a node qualifies when the next node on its level (in
        text order) has an equal zero subtree and that node's mirror is the
        first cell below it in the column.
        """
        shared: set[tuple[int, int]] = set()
        for k in range(levels):
            order = level_order(k, shared)
            # The last node's beam falls off the bottom and wraps to the top,
            # where the level's first mirror is the first in the column.  Its
            # walk is about the rows it saves, but only from eight rows up:
            # below that it is a few cells saved for a whole column walked.
            ring = wrap and 2 ** (levels - k - 1) >= _WRAP_ROWS
            follower = dict(pairwise([*order, *order[:1]] if ring else order))
            tried = {
                (k, a)
                for a, b in follower.items()
                if ids[k + 1][2 * a + 1] == ids[k + 1][2 * b]
            }
            if not tried:
                continue
            grid, where = draw(shared | tried, vertical=vertical)
            height = max(r for r, _ in grid) + 1
            column = 3 * k + 2
            owner = {cell: node for node, cell in where.items()}
            for _, a in tried:
                row = where[k, a][0] + 1
                while row < height and (row, column) not in grid:
                    row += 1
                if ring and row == height:
                    # Off the bottom the beam wraps to the top of the column.
                    row = 0
                    while (row, column) not in grid:
                        row += 1
                if owner.get((row, column)) == (k, follower[a]):
                    shared.add((k, a))
        return shared

    grid, _ = draw(plan(vertical=False), vertical=False)

    if width is not None and width > 0:
        span = max(c for _, c in grid) + 3
        if span > width:
            down = load(list(range(n)))
            wide = _descending_back(grid, down)
            grid, _ = draw(plan(vertical=True), vertical=True)
            tall = _descending_back(grid, down)
            return min((wide, tall), key=lambda code: max(map(len, code.splitlines())))

    # Height is max(tree 2**n, load units + 1).  Past n=3 load rows share with
    # tree rows; safe only because a run is one character for either bit.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    tree_width = max(c for _, c in grid) + 1
    # One '/' at the origin does both turns: right -> up off the top edge onto
    # the bottom row (toroidal wrap), up the load, then up -> right into the
    # tree at column 1.
    grid[(0, 0)] = "/"
    for k, unit in enumerate(units):
        grid[(height - 1 - k, 0)] = unit
    # No input row can instantiate to whitespace (a zero used to embed as a
    # blank, and the height revealed it).
    return _reflect_back(grid, height, tree_width)


LANGUAGE = Language(
    "Back",
    "tape_based.back",
    boolean=back,
    split=True,
    contract=BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n, past the n input cells",
        parameterized=True,
    ),
)
