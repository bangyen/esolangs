"""Boolean-function generator for Flowchart.

I/O is Boolfuck's: bytes, low bit first.  Each input is a ``'0'``/``'1'``
byte whose low bit is the value, so input ``k`` is read by eight ``/ /``
nodes -- the previous byte's seven high bits, then this byte's value bit,
which the switch tests.  The first input has no previous byte and the last
byte's high bits are never read: the interpreter has already consumed the
whole byte.  The answer is printed as R and then the seven high bits of
ASCII ``'0'`` (:data:`_ANSWER`), so the output byte is ``'0'`` or ``'1'``.
"""

from itertools import pairwise

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    narrowest_grid,
    read_at,
)

# Leaf pitch: the leaves were five-cell ``(( ))`` nodes plus a gutter.
_FLOWCHART_PITCH = 6

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


def _reads(level: int) -> int:
    """Return the ``/ /`` count that selects input ``level``'s value bit."""
    return 1 if level == 0 else 8


def _answer_column(cells: dict[tuple[int, int], str], middle: int, y: int) -> None:
    """Paint :data:`_ANSWER` down column ``middle`` from row ``y``."""
    for text in _ANSWER:
        left = middle - len(text) // 2
        for i, char in enumerate(text):
            cells[(left + i, y)] = char
        cells[(middle, y + 1)] = "│"
        y += 2
    del cells[(middle, y - 1)]


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves first on a fixed pitch, switches collapsed upwards and centred
    between their entry columns with rails to both.  Rows: ``( )``, rail,
    then per level its reads and switch, each followed by a rail; each leaf
    sets the register and drops onto a westward bus to the shared answer.
    """
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    # top[d] is level d's first read row; top[n] is the leaves' row.
    top = [2]
    for level in range(n):
        top.append(top[-1] + 2 * _reads(level) + 2)
    leaf_top = top[n]

    def read_rows(level: int) -> range:
        return range(top[level], top[level] + 2 * _reads(level), 2)

    middles: list[int] = []

    def leaf(slot: int, bit: str) -> int:
        """Draw the leaf for ``bit`` in column slot ``slot``; return its middle."""
        middle = _FLOWCHART_PITCH * slot + 2
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        middles.append(middle)
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        """Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = top[depth + 1] - 2
        middle = (west + east) // 2
        for y in read_rows(depth):
            put(middle - 1, y, "/ /")
            cells[(middle, y + 1)] = "│"
        put(middle - 1, switch_row, "< >")
        for x in range(west + 1, middle - 1):
            cells[(x, switch_row)] = "─"
        for x in range(middle + 2, east):
            cells[(x, switch_row)] = "─"
        cells[(west, switch_row)] = "┌"
        cells[(east, switch_row)] = "┐"
        cells[(west, switch_row + 1)] = "│"
        cells[(east, switch_row + 1)] = "│"
        return middle

    # Slots are handed out left to right as the walk reaches each leaf, so a
    # folded subtree takes one column band instead of the ``2**k`` its rows
    # would have filled -- the drawing narrows rather than leaving a gap.
    slots = [0]

    def walk(lo: int, hi: int, depth: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return its column."""
        if constant(lo, hi):
            # Constant: no branch below here can change the answer, so this
            # is a leaf.  Leaves all sit on the bottom row whatever their
            # depth, so the rail from the switch above covers the levels this
            # fold skipped: the rows are a fixed grid and only the branching
            # goes away.
            #
            # The *reads* those levels would have done do not go away.  A
            # program must consume its ``n`` inputs whatever the table says
            # -- the reads are the interface, and a folded run that skipped
            # them left the caller's remaining bits on the stream -- so each
            # skipped level puts its ``/ /`` nodes on the rail, where the
            # pointer runs straight through them into the leaf below.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(top[depth], leaf_top):
                cells.setdefault((middle, y), "│")
            for skipped in range(depth, n):
                for y in read_rows(skipped):
                    put(middle - 1, y, "/ /")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"

    # A pointer heading down onto ``┴`` turns clockwise, west, and one
    # heading west runs straight through, so the bus flows west; it jogs
    # round under the first leaf into the answer column.
    bus = leaf_top + 2
    for x in range(1, middles[-1]):
        cells[(x, bus)] = "─"
    for middle in middles:
        cells[(middle, bus)] = "┴"
    cells[(middles[-1], bus)] = "┘"
    cells[(1, bus)] = "┌"
    cells[(1, bus + 1)] = "└"
    cells[(2, bus + 1)] = "┐"
    _answer_column(cells, 2, bus + 2)
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _flowchart_stacked(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the tree with its subtrees stacked rather than side by side.

    The one-branch hangs below the switch and the zero-branch falls down its
    own column past it, so every node shares one column and width costs
    height.  A downward switch sends 1 east and 0 west, so each branch is
    caught by a corner: the one-branch steps east and back, the zero-branch
    runs west to the column reserved for its depth and back.  Corridor ``d``
    is column ``d`` and every descendant is deeper and further east, so no
    rail and corridor ever meet.  Each leaf turns east onto a bus down
    column ``spine + 3``, which returns to the spine below the last leaf.
    """
    n = (len(truth_table) - 1).bit_length()
    # Columns 0..n-1 are the corridors, one per depth; the tree itself sits
    # on ``spine``, far enough east that the answer's ``(( ))`` clears them.
    spine = n + 2
    bus = spine + 3
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)
    taps: list[int] = []

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    def reads(y: int, count: int) -> int:
        """Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            put(spine - 1, y, "/ /")
            cells[(spine, y + 1)] = "│"
            y += 2
        return y

    def leaf(y: int, depth: int, bit: str) -> int:
        """Draw the leaf for ``bit``, entered at ``(spine, y)``.

        A folded leaf's owed reads stack above it.
        """
        y = reads(y, sum(_reads(level) for level in range(depth, n)))
        put(spine - 1, y, "[ }" if bit == "1" else "{ ]")
        cells[(spine, y + 1)] = "│"
        put(spine, y + 2, "└──")
        taps.append(y + 2)
        return y + 3

    def walk(lo: int, hi: int, depth: int, y: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        if constant(lo, hi):
            return leaf(y, depth, truth_table[lo])
        y = reads(y, _reads(depth))
        put(spine - 1, y, "< >")
        # b=1: east out of the switch, down, back west, onto the spine
        cells[(spine + 2, y)] = "┐"
        cells[(spine + 2, y + 1)] = "┘"
        cells[(spine + 1, y + 1)] = "─"
        cells[(spine, y + 1)] = "┌"
        half = (hi - lo) // 2
        below = walk(lo + half, hi, depth + 1, y + 2)
        # b=0: west to this depth's own column, down past everything the
        # one-branch drew, then east again onto the spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y)] = "─"
        cells[(depth, y)] = "┌"
        for row in range(y + 1, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        for x in range(depth + 1, spine):
            cells[(x, below)] = "─"
        cells[(spine, below)] = "┐"
        return walk(lo, lo + half, depth + 1, below + 1)

    walk(0, len(truth_table), 0, 2)
    put(spine - 1, 0, "( )")
    cells[(spine, 1)] = "│"
    # Heading east onto ``┤`` turns clockwise, down, so every tap joins.
    for row in range(taps[0], taps[-1] + 1):
        cells[(bus, row)] = "│"
    for row in taps:
        cells[(bus, row)] = "┤"
    cells[(bus, taps[0])] = "┐"
    end = taps[-1] + 1
    cells[(bus, end)] = "┘"
    put(spine, end, "┌──")
    _answer_column(cells, spine, end + 1)
    return cells


def flowchart(truth_table: str, width: int | None = None) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    Unconstrained programs preload paired answers into deques and select
    one with the input bits. Width-constrained programs draw a decision
    tree, stacking branches when necessary. Every node connection includes
    a path cell; adjacent leaves have a blank gutter. Folded leaves still
    read the skipped inputs.
    """
    _validate_truth_table(truth_table)
    if width is None:
        return _flowchart_deque(truth_table)
    flat = _flowchart_render(_flowchart_cells(truth_table))
    if grid_width(flat) <= width:
        return flat
    stacked = _flowchart_render(_flowchart_stacked(truth_table))
    return narrowest_grid(flat, stacked)


def _flowchart_deque(truth_table: str) -> str:
    r"""Address one preloaded answer by walking the deque cursor to it.

    Entries ``2j`` and ``2j + 1`` are pushed onto deque ``j`` in that order,
    so the preload leaves the cursor on ``T / 2 - 1`` and the first ``n - 1``
    bits walk it back: a zero at level ``k`` steps the cursor down by
    ``2 ** (n - 2 - k)`` and a one leaves it alone.  The last bit needs no
    step at all -- the pair sharing a deque is one at each end, so it picks
    ``\{ }/`` or ``/{ }\`` and halves both the ``[ >`` run and the walk.
    Discarding halves of one deque instead needed a pop node on *both* arms
    of every switch, so a unit of selection cost two five-character nodes
    rather than one three-character ``< ]`` on the arm that moves and a bare
    rail on the arm that does not.

    Two rows, not five, and the pointer runs east to west.  Only one arm of
    a switch leaves the spine, so the drawing needs one row above it rather
    than two on each side; running westwards puts the selector in the low
    columns, which is what keeps that upper row short -- a line is padded
    out to its last non-space cell, so a selector drawn east of the preload
    would have charged the preload's width twice.

    Input ``p``'s value bit is stream bit ``8p``, so an ignored input costs
    only the eight ``/ /`` that skip it, and the deque holds the table over
    the essential inputs alone.
    """
    n = len(truth_table).bit_length() - 1
    # A constant table keeps one input for the selector to switch on.
    used = essential_inputs(truth_table, n) or list(range(n))
    truth_table = read_at(truth_table, used, n)
    skips = [8 * used[0] + 1] + [8 * (b - a) for a, b in pairwise(used)]
    cells: dict[tuple[int, int], str] = {}
    spine = 1
    col = 0

    def west(text: str) -> int:
        """Place ``text`` on the spine ending at ``col``; return its left end."""
        nonlocal col
        left = col - len(text) + 1
        for offset, char in enumerate(text):
            cells[(left + offset, spine)] = char
        cells[(left - 1, spine)] = "─"
        col = left - 2
        return left

    def paint(start: int, row: int, text: str) -> None:
        for offset, char in enumerate(text):
            cells[(start + offset, row)] = char

    west("( )")
    # ``\[ ]/`` and ``[ >`` both leave the register alone, so a run of equal
    # entries is set once and pushed however many times it is long.
    register: str | None = None
    for index, bit in enumerate(truth_table):
        if register != bit:
            west("[ }" if bit == "1" else "{ ]")
            register = bit
        west("\\[ ]/")
        if index % 2 and index + 1 < len(truth_table):
            west("[ >")

    n = len(used)
    for level in range(n - 1):
        for _ in range(skips[level]):
            west("/ /")
        switch = west("< >")
        # Travelling west a switch sends 1 straight on and 0 up, and the
        # rail west of the switch is the one-branch's bypass.
        count = 1 << (n - 2 - level)
        junction = col - 4 * count + 1
        paint(switch, spine - 1, "─┐")
        paint(junction + 1, spine - 1, "< ]─" * count)
        paint(junction + 1, spine, "─" * (4 * count))
        cells[(junction, spine - 1)] = "┌"
        cells[(junction, spine)] = "┴"
        col = junction - 1

    # The last bit picks an end rather than a deque: the pair sharing a deque
    # was pushed even entry first, so its odd half is the top.  Each arm
    # prints its own answer, the upper one a column east of the spine's.
    for _ in range(skips[n - 1]):
        west("/ /")
    switch = west("< >")
    cells[(switch + 1, spine - 1)] = "┐"
    upper = "─".join(reversed(("/{ }\\", *_ANSWER)))
    paint(switch - len(upper), spine - 1, upper + "─")
    for text in ("\\{ }/", *_ANSWER):
        end = west(text)
    del cells[(end - 1, spine)]

    left = min(x for x, _ in cells)
    width = max(x for x, _ in cells) - left + 1
    grid = [[" "] * width for _ in range(2)]
    for (x, row), char in cells.items():
        grid[row][x - left] = char
    return "\n".join("".join(row).rstrip() for row in grid)
