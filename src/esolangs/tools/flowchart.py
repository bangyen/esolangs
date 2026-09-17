"""Boolean-function generator for Flowchart."""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

# A leaf is exactly as wide as the ``(( ))`` it ends on, so consecutive
# leaves abut and the tree needs no gutter between them at all.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves first on a fixed pitch, switches collapsed upwards and centred
    between their entry columns with rails to both.  Rows: ``( )``, rail,
    four rows per level (``/ /``, rail, ``< >``, rail), then the five-row leaf.
    """
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)

    def put(x: int, y: int, text: str) -> None:
        for i, char in enumerate(text):
            cells[(x + i, y)] = char

    n = (len(truth_table) - 1).bit_length()
    leaf_top = 2 + 4 * n

    def leaf(slot: int, bit: str) -> int:
        """Draw the leaf for ``bit`` in column slot ``slot``; return its middle.

        Leaf ``k`` spans ``5k .. 5k + 4``; its middle is ``5k + 2``.
        """
        middle = _FLOWCHART_PITCH * slot + 2
        put(middle - 1, leaf_top, "[ }" if bit == "1" else "{ ]")
        cells[(middle, leaf_top + 1)] = "│"
        put(middle - 1, leaf_top + 2, "\\ \\")
        cells[(middle, leaf_top + 3)] = "│"
        put(middle - 2, leaf_top + 4, "(( ))")
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        """Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = 4 + 4 * depth
        middle = (west + east) // 2
        put(middle - 1, switch_row - 2, "/ /")
        cells[(middle, switch_row - 1)] = "│"
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
            # skipped level puts its ``/ /`` on the rail, where the pointer
            # runs straight through it into the leaf below.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(4 * depth + 2, leaf_top):
                cells.setdefault((middle, y), "│")
            for skipped in range(depth, n):
                put(middle - 1, 4 * skipped + 2, "/ /")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    put(root - 1, 0, "( )")
    cells[(root, 1)] = "│"
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
    rail and corridor ever meet.
    """
    n = (len(truth_table) - 1).bit_length()
    # Columns 0..n-1 are the corridors, one per depth; the tree itself sits
    # on ``spine``, far enough east that a leaf's five-cell ``(( ))`` clears
    # them.
    spine = n + 2
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)

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
        y = reads(y, n - depth)
        put(spine - 1, y, "[ }" if bit == "1" else "{ ]")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "\\ \\")
        cells[(spine, y + 3)] = "│"
        put(spine - 2, y + 4, "(( ))")
        return y + 5

    def walk(lo: int, hi: int, depth: int, y: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        if constant(lo, hi):
            return leaf(y, depth, truth_table[lo])
        put(spine - 1, y, "/ /")
        cells[(spine, y + 1)] = "│"
        put(spine - 1, y + 2, "< >")
        # b=1: east out of the switch, down, back west, onto the spine
        cells[(spine + 2, y + 2)] = "┐"
        cells[(spine + 2, y + 3)] = "┘"
        cells[(spine + 1, y + 3)] = "─"
        cells[(spine, y + 3)] = "┌"
        half = (hi - lo) // 2
        below = walk(lo + half, hi, depth + 1, y + 4)
        # b=0: west to this depth's own column, down past everything the
        # one-branch drew, then east again onto the spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y + 2)] = "─"
        cells[(depth, y + 2)] = "┌"
        for row in range(y + 3, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        for x in range(depth + 1, spine):
            cells[(x, below)] = "─"
        cells[(spine, below)] = "┐"
        return walk(lo, lo + half, depth + 1, below + 1)

    walk(0, len(truth_table), 0, 2)
    put(spine - 1, 0, "( )")
    cells[(spine, 1)] = "│"
    return cells


def flowchart(truth_table: str, width: int | None = None) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Wide
    unconstrained programs preload the table into one deque and each input
    pops half the remaining answers from one end (fewer than ``2T`` pops,
    five rows: O(T)).  Small or width-constrained programs draw a decision
    tree: ``/ /`` reads a bit, ``< >`` switches, each leaf sets, prints and
    halts.  Leaves sit flush on one ``(( ))`` pitch (dropping the gutter
    took ``n = 4`` from 2444 to 1557 chars).  The tree draws ``2**n - 1``
    read nodes but any run executes ``n``, so a folded leaf carries its
    skipped reads -- spatial duplication like an unrolled brainfuck branch,
    not the once-only rule of ``tools.parameterized``, since Flowchart reads
    input.  A deque-first construction (a ``4n``-row prologue, relying on
    FIFO pop-bottom) was verified and shelved.  Without a width both
    layouts are built and the shorter wins; ``width`` under ``2 ** n``
    stacks the tree (:func:`_flowchart_stacked`) at ``n + 5`` columns, and
    under that floor the narrower is returned.
    """
    _validate_truth_table(truth_table)
    if len(truth_table) > 16 and width is None:
        return _flowchart_deque(truth_table)
    flat = _flowchart_render(_flowchart_cells(truth_table))
    if width is not None and max(len(line) for line in flat.split("\n")) <= width:
        return flat
    stacked = _flowchart_render(_flowchart_stacked(truth_table))
    if width is None:
        return min((flat, stacked), key=len)
    if max(len(line) for line in stacked.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return stacked
    return flat


def _flowchart_deque(truth_table: str) -> str:
    """Select one preloaded answer by discarding opposite deque halves."""
    cells: dict[tuple[int, int], str] = {}
    main = 2

    def put(x: int, y: int, text: str) -> None:
        for offset, char in enumerate(text):
            key = (x + offset, y)
            if key in cells:
                raise AssertionError(f"two Flowchart cells at {key}")
            cells[key] = char

    def chain(x: int, y: int, nodes: list[str]) -> int:
        for node in nodes:
            put(x, y, node)
            x += len(node)
            put(x, y, "─")
            x += 1
        return x

    x = 0
    x = chain(x, main, ["( )"])
    preload: list[str] = []
    for bit in truth_table:
        preload.extend(("[ }" if bit == "1" else "{ ]", "\\[ ]/"))
    x = chain(x, main, preload)

    n = len(truth_table).bit_length() - 1
    for level in range(n):
        x = chain(x, main, ["/ /"])
        switch = x
        put(switch, main, "< >")
        middle = switch + 1
        put(middle, main - 1, "│")
        put(middle, main + 1, "│")
        put(middle, main - 2, "┌")
        put(middle, main + 2, "└")

        count = 1 << (n - 1 - level)
        top = chain(middle + 1, main - 2, ["/{ }\\"] * count + ["[ }"])
        bottom = chain(middle + 1, main + 2, ["\\{ }/"] * count + ["{ ]"])
        if top != bottom:  # pragma: no cover - paired node widths are equal
            raise AssertionError("Flowchart selector arms have different widths")
        end = top
        put(end, main - 2, "┐")
        put(end, main + 2, "┘")
        put(end, main - 1, "│")
        put(end, main + 1, "│")
        put(end - 1, main, "< >")
        put(end + 2, main, "─")
        x = end + 3

    x = chain(x, main, ["\\{ }/", "\\ \\"])
    put(x, main, "(( ))")
    width = max(col for col, _ in cells) + 1
    grid = [[" "] * width for _ in range(5)]
    for (col, row), char in cells.items():
        grid[row][col] = char
    return "\n".join("".join(row).rstrip() for row in grid)
