"""Boolean-function generator for Dig."""

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

# Dig blocks for one level of the decision tree.  ``$`` takes its count
# from the digit beside it and looks up, right, down, left for one, so the
# count sits to the *right* of the ``$`` and the whole block is entered
# from the left: the count digit is itself the first of the commands it
# arms, which is why three covers a read and a store.
_DIG_BRANCH = "$3~;#"  # arm three, read a bit, store it, then turn on it


_DIG_ENTER = ">"  # the root's turn out of the column the mole starts down


_DIG_CONTINUE = ">"  # a child of a branch: keep facing right into its block


_DIG_RETURN = "<"  # the same, for a child the mole reaches facing west


_DIG_PRINT = "{}:@"  # set the mole to the result and print it


# ``$`` reads its repeat count from the digit beside it, so a run of cells
# under one ``$`` is at most nine long.
_DIG_SPAN = 9


# Columns one level owns.  A block is five cells and its ``#`` is the last,
# so the child's ``>`` sits under that ``#`` -- which is the cell before the
# child's own block, and the stride is what puts it there.
_DIG_STRIDE = len(_DIG_BRANCH)


# A banded level leaves one column spare.  Six is what makes the two bands
# able to share columns at all: see :func:`_dig_columns`.
_DIG_BAND = _DIG_STRIDE + 1


# Cells a mole walking over them does not obey.  Everything else is
# scenery while the underground counter is at zero -- digits included,
# which is what lets a corridor cross a block's middle.
_DIG_OPAQUE = "^>'<#$@"


# Cells that hold a digit where a neighbouring ``$`` or ``#`` would find
# one.  ``;`` counts: it writes the mole into its own cell, so on the
# executed path it *is* a digit.
_DIG_DIGITS = "0123456789;"


def _dig_leaf(reads: int, value: int, *, aligned: bool) -> str:
    """Build a leaf that consumes ``reads`` inputs, then prints ``value``.

    ``$`` makes the cells after it commands, as many as the digit beside it
    says, so the reads a folded leaf still owes need no block each: one
    ``$`` covers every ``~`` plus the three cells that print.  Its count is
    a single digit, so a window holds at most nine cells; past that the
    windows chain, and a window that spends its whole count leaves the
    counter at zero, which is what arms the next ``$`` with no cell in
    between.

    ``aligned`` is for the banded layout, where a leaf shares columns with
    the other band and its cells have to fall where that band's do not
    care.  Two things change.  Windows become exactly ``_DIG_BAND`` cells
    long, so every ``$`` in the chain keeps the column residue the first
    one had.  And a blank goes before the value when ``reads`` is even --
    a blank inside an armed window only spends a count -- which puts the
    value digit an odd number of cells from the ``$``, where the other
    band's ``$`` and ``#`` never look.
    """
    out = ""
    if not aligned:
        while reads > _DIG_SPAN - 3:
            take = min(_DIG_SPAN - 1, reads - (_DIG_SPAN - 3))
            out += f"${take + 1}" + "~" * take
            reads -= take
        return out + f"${reads + 3}" + "~" * reads + _DIG_PRINT.format(value)
    while reads > _DIG_BAND - 1:
        take = _DIG_BAND - 2
        out += f"${take + 1}" + "~" * take
        reads -= take
    pad = 1 - reads % 2
    tail = "~" * reads + " " * pad + _DIG_PRINT.format(value)
    return out + f"${reads + pad + 3}" + tail


def _dig_columns(n: int, split: int | None) -> tuple[int, int]:
    """Where the two bands start, or the one band if ``split`` is ``None``.

    A flat tree walks east the whole way and every level owns five columns
    of its own.  A banded one turns round once: the levels before ``split``
    run east, the rest run west over the same columns, mirrored so the mole
    still meets each block's ``$`` first.

    The bands can overlap at all only because of how their columns line up.
    Read a block's cells by their offset: a ``$`` or a ``#`` -- the only
    two that consult a neighbour -- sits at 0 or 4, and the digits that
    could confuse one sit at 1 and 3.  So with a stride of six, letting
    ``d`` be an east block's column minus a west block's, a digit lands on
    a neighbour-reading cell when ``d`` is 1, 3, -1 or -3, and a mole
    falling from a ``#`` lands on a ``$`` or a ``#`` when ``d`` is 0 or -4.
    Every one of those is 0, 1, 2, 3 or 5 modulo six.  **Four is not**, so
    fixing ``d`` at four modulo six clears all of them at once, whatever
    the overlap -- and every pair of an east and a west block differs by
    ``d`` plus a multiple of six.

    That also says why the turn happens once and not twice.  A second turn
    would put two bands running the same way, and two east blocks differ by
    a multiple of six, which is zero modulo six -- the case ``d`` had to
    avoid.  So one turn is the whole of what Dig's geometry allows.
    """
    if split is None:
        return 1, 0
    # The west band ends four columns short of where the east band's last
    # ``#`` stands, which is the cell the mole turns west from; putting it
    # one stride further back is what makes ``d`` four modulo six.
    return 1, _DIG_BAND * (n - split) + 3


def _dig_grid(truth_table: str, n: int, split: int | None) -> str:
    """Lay the decision tree out, in one band east or two that turn round."""
    total = 2 ** (n + 1) - 1
    constant = constant_span_test(truth_table)
    east, west = _dig_columns(n, split)
    cells: dict[tuple[int, int], str] = {}
    corridors: list[tuple[int, int, int]] = []

    def leftward(level: int) -> bool:
        """Whether this level's block is entered facing west."""
        return split is not None and level >= split

    def dollar(level: int) -> int:
        """Return the column of this level's ``$``, the cell the mole meets first."""
        if split is None:
            return east + _DIG_STRIDE * level
        if level < split:
            return east + _DIG_BAND * level
        return west + 4 - _DIG_BAND * (level - split)

    def place(row: int, col: int, text: str) -> None:
        """Write ``text`` along ``row`` from ``col``, refusing an occupied cell.

        The columns above are what keeps two cells apart; this is what says
        so.  A Dig cell steers or arms the mole that stands on it, so an
        overwrite is one of the two ways a bad layout goes wrong, and the
        other -- a mole falling through a cell that acts on it -- is what
        :func:`_dig_clear` checks.
        """
        for i, char in enumerate(text):
            if col + i < 0:
                raise AssertionError(f"cell off the left edge at row {row}")
            if (row, col + i) in cells:
                raise AssertionError(f"two cells at {(row, col + i)}")
            cells[row, col + i] = char

    def block(row: int, level: int, text: str) -> None:
        """Write a block so the mole meets its first cell first."""
        col = dollar(level)
        if leftward(level):
            place(row, col - len(text) + 1, text[::-1])
        else:
            place(row, col, text)

    def walk(row: int, level: int, lo: int, hi: int) -> None:
        """Lay the subtree for ``truth_table[lo:hi]`` at ``row``."""
        if level == n or constant(lo, hi):
            # A constant slice cannot be told apart by more branching, so
            # this is a leaf and every row below it goes unwritten.  It
            # still reads what it did not branch on: a program whose input
            # count depended on its table would desync a caller feeding
            # several programs from one stream.
            reads = n - level
            block(
                row,
                level,
                _dig_leaf(reads, int(truth_table[lo]), aligned=split is not None),
            )
            return
        block(row, level, _DIG_BRANCH)
        col = dollar(level)
        hop = col - 4 if leftward(level) else col + 4
        step = 2 ** (n - level - 1)
        half = (hi - lo) // 2
        # ``#`` rotates one way on a 0 and the other on a 1, so which child
        # is up and which is down follows the mole's heading: a bit that
        # sends an eastbound mole down sends a westbound one up.
        one, zero = (
            (row - step, row + step) if leftward(level) else (row + step, row - step)
        )
        for child, bounds in (
            (one, (lo + half, hi)),
            (zero, (lo, lo + half)),
        ):
            # the mole arrives here vertically from the parent's "#", which
            # is the cell right before the child's own block -- so the turn
            # goes in that column, pointing the way the child is entered
            place(child, hop, _DIG_RETURN if leftward(level + 1) else _DIG_CONTINUE)
            corridors.append((hop, row, child))
            walk(child, level + 1, *bounds)

    # The mole starts at (0, 0) facing right, so the ``'`` below turns it
    # down column 0 and this is the cell that turns it back out of it.
    place(total // 2, east - 1, _DIG_ENTER)
    walk(total // 2, 0, 0, 2**n)
    _dig_clear(cells, corridors)

    if (0, 0) in cells:
        raise AssertionError("the start marker's cell is taken")
    cells[0, 0] = "'"
    span = max(col for _, col in cells) + 1
    rows = sorted({row for row, _ in cells})
    grid = [[" "] * span for _ in rows]
    row_index = {row: i for i, row in enumerate(rows)}
    for (row, col), char in cells.items():
        grid[row_index[row]][col] = char
    # Rows are painted into a rectangle of blanks, but the mole never walks
    # past the last command on a row, so the trailing filler is inert and is
    # trimmed rather than committed.
    return "\n".join("".join(row).rstrip() for row in grid)


def _dig_clear(
    cells: dict[tuple[int, int], str],
    corridors: list[tuple[int, int, int]],
) -> None:
    """Refuse a grid whose moles would be stopped on their way.

    Two things can go wrong that placing cells cannot see.  A mole falling
    from a ``#`` to its child passes every row between, and a cell it meets
    there steers or arms it unless it is scenery -- which, with the counter
    at zero, everything but :data:`_DIG_OPAQUE` is.  And a ``$`` or a ``#``
    takes its digit from the first of up, right, down, left that has one,
    so a digit directly above or below either is a wrong answer that runs.

    Both are checked against the grid rather than argued from the column
    rule, because the rule is what *places* the cells and an argument that
    places and checks with the same reasoning checks nothing.
    """
    for col, start, end in corridors:
        low, high = sorted((start, end))
        for row in range(low + 1, high):
            char = cells.get((row, col))
            if char is not None and char in _DIG_OPAQUE:
                raise AssertionError(
                    f"mole from row {start} meets {char!r} at {(row, col)}"
                )
    for (row, col), char in cells.items():
        if char not in "$#":
            continue
        for step in (-1, 1):
            above = cells.get((row + step, col))
            if above is not None and above in _DIG_DIGITS:
                raise AssertionError(f"{char!r} at {(row, col)} reads {above!r} first")


_DIG_DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))


def _dig_alternating(truth_table: str, n: int) -> str:
    """Lay a full Dig tree with its branch axis rotating at every level.

    A ``#`` naturally sends its zero and one children left and right.  Let a
    subtree's local x-axis be its entering heading.  Its children therefore
    enter on the local y-axis; placing each just beyond its own most-backward
    cell keeps the two child rectangles on opposite sides of the parent.
    Width and height swap, then one doubles, at successive levels.  Thus each
    pair of levels doubles both and the rendered rectangle is O(2**n).
    """
    # Bounds of a complete m-level subtree entered east, inclusive and local
    # to its first ``$``: (min_x, max_x, min_y, max_y).  Leaves and branch
    # blocks are both five cells long.
    bounds = [(0, 4, 0, 0)]
    for _ in range(n):
        min_x, max_x, min_y, max_y = bounds[-1]
        distance = 1 - min_x
        bounds.append(
            (
                min(0, 4 + min_y, 4 - max_y),
                max(4, 4 + max_y, 4 - min_y),
                -(distance + max_x),
                distance + max_x,
            )
        )

    cells: dict[tuple[int, int], str] = {}

    def place(point: tuple[int, int], char: str) -> None:
        if point in cells:
            raise AssertionError(f"two cells at {point}: {cells[point]!r} and {char!r}")
        cells[point] = char

    def text(point: tuple[int, int], heading: int, code: str) -> None:
        dr, dc = _DIG_DIRECTIONS[heading]
        for offset, char in enumerate(code):
            place((point[0] + dr * offset, point[1] + dc * offset), char)

    def node(
        level: int,
        point: tuple[int, int],
        heading: int,
        lo: int,
        hi: int,
    ) -> None:
        if level == n:
            text(point, heading, f"$3{truth_table[lo]}:@")
            return
        text(point, heading, _DIG_BRANCH)
        dr, dc = _DIG_DIRECTIONS[heading]
        end = (point[0] + 4 * dr, point[1] + 4 * dc)
        half = (lo + hi) // 2
        distance = 1 - bounds[n - level - 1][0]
        for bit, child_bounds in ((0, (lo, half)), (1, (half, hi))):
            child_heading = (heading - 1) % 4 if bit == 0 else (heading + 1) % 4
            cr, cc = _DIG_DIRECTIONS[child_heading]
            child = (end[0] + distance * cr, end[1] + distance * cc)
            node(level + 1, child, child_heading, *child_bounds)

    # Build locally with the root heading east.  Its ray from the west is
    # empty by the same bounds recurrence, so an external L-shaped entry can
    # reach it without crossing the tree.
    node(0, (0, 0), 1, 0, len(truth_table))
    min_row = min(row for row, _ in cells)
    min_col = min(col for _, col in cells)
    row_shift, col_shift = 2 - min_row, 2 - min_col
    cells = {
        (row + row_shift, col + col_shift): char for (row, col), char in cells.items()
    }
    root_row, root_col = row_shift, col_shift
    if any((root_row, col) in cells for col in range(root_col)):
        raise AssertionError("the alternating Dig tree blocked its entry ray")
    for row in range(root_row):
        cells[(row, 0)] = " "
    for col in range(root_col):
        cells[(root_row, col)] = " "
    cells[(0, 0)] = "'"
    cells[(root_row, 0)] = ">"

    height = max(row for row, _ in cells) + 1
    width = max(col for _, col in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (row, col), char in cells.items():
        grid[row][col] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def dig(truth_table: str, width: int | None = None) -> str:
    """Build a Dig program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    Past four inputs the default alternates the branch axis at every level.
    Its width and height each double once per pair of levels, so its area and
    construction time are O(T).  ``width`` retains the folded one- or
    two-band layouts below; a width under their floor returns the narrower
    program rather than refusing.

    The tree is laid out so the mole starts in the top-left corner (``'``)
    facing down into the root.  Each branch block reads one input bit:
    ``~`` inputs it, ``;`` stores it in the grid, and ``#`` turns the mole
    down or up on that bit.  The two children of a node keep facing the way
    the next level's branch is entered, and the leaves print the function's
    value for the input combination they stand for.

    A subtree whose rows all agree becomes a leaf, and the rows it would
    have filled are never written -- which is what the walk buys over filling
    the grid level by level, where a pruned row still had to be skipped by
    hand.  A constant table collapses to a single line.

    A folded leaf still reads the inputs it never branched on, since a
    program whose input count depended on its table would desync a caller
    feeding several programs from one stream.  Those reads are cheap: a
    branch spends ``;`` to store its bit for its own ``#``, and a leaf turns
    nowhere, so the read is bare -- and ``$`` covers a run of cells at once,
    so they need no block each.

    A level costs five columns, not seven.  Two cells the blocks used to
    spend are not needed.  The ``>`` that opened a block only ever repeated
    the heading the mole already had -- every block but the root's is
    entered moving right -- so only the root keeps one, to turn out of the
    column it starts down.  And the ``@`` that closed a block was never
    reached: ``;`` writes the bit it just read, so the ``#`` beside it
    always sees a 0 or a 1 and always turns.  Putting the count to the
    right of its ``$`` rather than the left is what lets the blocks abut,
    since ``$`` looks up, right, down, left and takes the first digit it
    finds.

    In the explicit-width layout, ``5 * n + 6`` columns is what that comes
    to, and a width under it is met
    by turning the tree round once: the levels past the turn run west over
    the columns the levels before it already used, their blocks mirrored so
    the mole still meets each ``$`` first.  Nothing has to be routed back --
    the ``#`` at the end of the last eastbound block turns the mole onto its
    child's row, and a ``<`` there points it into a block that starts where
    it stands.  What the two bands cost is one spare column a level, and
    :func:`_dig_columns` is where the arithmetic that lets them overlap
    lives, along with the reason a *second* turn is not possible.
    """
    n = _validate_truth_table(truth_table)
    if width is None and n > 4:
        return _dig_alternating(truth_table, n)
    flat = _dig_grid(truth_table, n, None)
    if n < 2:
        return flat
    # The turn has to leave the westbound band room to finish left of where
    # the eastbound one starts its last block, which is what fixes the
    # split rather than any search: the halves are as even as that allows.
    banded = _dig_grid(truth_table, n, -(-(n + 2) // 2))
    if width is None:
        return min((flat, banded), key=len)
    if max(len(line) for line in flat.split("\n")) <= width:
        return flat
    if max(len(line) for line in banded.split("\n")) < max(
        len(line) for line in flat.split("\n")
    ):
        return banded
    return flat
