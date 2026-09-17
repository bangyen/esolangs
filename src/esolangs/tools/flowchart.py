"""Boolean-function generator for Flowchart."""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

# A leaf is exactly as wide as the ``(( ))`` it ends on, so consecutive
# leaves abut and the tree needs no gutter between them at all.
_FLOWCHART_PITCH = 5


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves are placed first, on a fixed pitch, and the switches are then
    collapsed upwards: each pair of entry columns yields a ``< >`` centred
    between them with rails drawn out to both.  Positioning everything from
    the leaf pitch keeps the drawing tight -- an earlier recursive version
    assembled each subtree into its own padded block and separated the blocks
    by a gutter, costing a column of blanks for every leaf at every level
    even though two ``(( ))`` boxes may sit flush against each other.

    Rows run ``( )``, its rail, then four rows per level (``/ /``, a rail,
    ``< >``, a rail), then the five-row leaf block.
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

        Leaf ``k`` spans columns ``5k`` to ``5k + 4``, so its middle -- the
        column every rail in that leaf's band lands on -- is ``5k + 2``.
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
        """Draw the subtree for ``truth_table[lo:hi]``; return its column.

        ``depth`` is the level it sits at, which fixes its rows; its columns
        come from the leaf slots it consumes.
        """
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

    The flat drawing gives every leaf a column of its own, so it grows as
    ``2 ** n``.  Stacking separates the two subtrees by *rows* instead: the
    one-branch hangs directly below the switch, and the zero-branch falls
    down a column of its own, past every row the one-branch occupies, to
    start below it.  Every node then sits on the same column, and what the
    width costs is height -- the drawing is as tall as the whole tree.

    A switch entered travelling down sends register 1 to the grid-east and
    register 0 to the grid-west, so neither branch may simply continue
    down; each is caught by a corner and routed.  The one-branch turns down
    one column east, comes back west a row later, and drops onto the spine.
    The zero-branch runs west to a column reserved for its depth, falls the
    height of the one-branch, and comes back east.

    Those corridors need no crossings, which is what keeps the drawing
    simple.  A corridor for depth ``d`` occupies column ``d``, and
    everything below it in the tree is at a *deeper* depth and so further
    east; the rails that run west to reach it do so on the switch's own
    row, above every descendant.  So no rail and no corridor ever meet.
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

        A folded leaf still owes the reads of the levels it skipped -- the
        reads are the interface -- and here they simply stack above it,
        which is what the flat drawing spends a rail on.
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Wide unconstrained programs preload the table into one deque.  Each input
    selects between two arms that pop half the remaining answers from opposite
    ends.  The upper arm sets register 1 and enters the merge switch downward;
    the lower sets 0 and enters upward, so both leave that switch east.  Across
    all levels the two arms contain fewer than ``2T`` pops, and the drawing is
    five rows high, making both construction and rendered output O(T).

    Small or width-constrained programs use a binary decision tree drawn on
    the grid: every level
    reads one input bit with ``/ /`` and hands it to a ``< >`` switch whose
    two sides are the halves of the table, and each of the ``2**n`` leaves
    sets the register to its own digit, prints it, and halts.

    Unlike the repo's other 2D boolean generators there is no geometry to
    build for the branch itself -- Flowchart has a real conditional node --
    and each input arrives as a bare bit, so no per-input decoding loop is
    needed either.  What the layout has to get right instead is routing:
    every switch is centred over the two subtree entries it feeds, with
    rails drawn out to each.

    The leaves are laid down first, on a pitch of exactly one ``(( ))``
    width, and the switches are collapsed upwards from them.  Nothing
    separates one leaf from the next: two ``(( ))`` boxes may sit flush
    against each other, since a rail only has to clear a node when it needs
    to pass *through* that node's row.  Sibling subtrees never do -- they
    descend in their own column bands -- so the gutter an earlier version
    kept between them was never required, and dropping it takes the
    ``n = 4`` drawing from 2444 characters to 1557.

    **The tree holds many ``/ /`` nodes but reads each input once.**  A
    depth-``n`` tree draws ``2**n - 1`` read nodes, one per internal node,
    yet any single run walks one root-to-leaf path and so executes exactly
    ``n`` of them -- which is why a *folded* leaf carries the reads of the
    levels it skipped on its own rail.  Without them a run that folded early
    would consume fewer inputs than one that did not, making the program's
    stream consumption a function of its truth table; only the branching may
    fold away, never the reads.  The duplication is spatial, the way an
    unrolled brainfuck branch repeats ``,`` in each arm of a nested ``[ ]``
    without any one execution reading twice.  This is deliberately *not* the
    once-only embedding rule that ``tools.parameterized`` documents:
    that rule exists so a language with no input mechanism cannot, through
    repeated substitution of an input's run, consult a bit more often than an
    input-capable language would.  Flowchart has a real input command, so it
    is an input-reading generator like :func:`streetcode` (whose ``I``
    commands likewise repeat across tree branches), not a parameterized one.

    An alternative construction reads all ``n`` bits up front into a deque
    and pops one per level instead, exercising the deques -- the language's
    defining feature, untouched here.  It was built and verified over the
    same tables, and is worth revisiting if Flowchart ever gets a cross-check
    that would benefit from the wider coverage; it costs a ``4n``-row
    prologue and depends on push-top/pop-bottom being FIFO, a silent
    wrong-answer trap if the pop is ever changed to pop-top.
    Without a width, both named layouts are built and the shorter rendered
    program wins; this is a fixed two-way comparison, not a layout search.
    ``width`` asks for a column count.  The flat drawing gives every leaf a
    column of its own and so grows as ``2 ** n``; a width under that is met
    by *stacking* the tree instead, separating the two subtrees by rows and
    putting every node on one column.  See :func:`_flowchart_stacked` for
    how the branches are routed and why the corridors never cross.  The
    stacked drawing is ``n + 5`` columns whatever the table, so the width
    stops tracking ``n`` -- and pays for it in height, being as tall as the
    whole tree.  A width under that floor returns the narrower of the two
    rather than refusing, and a heavily folded table is sometimes already
    narrower flat.
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
