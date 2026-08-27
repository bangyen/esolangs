r"""Fold a LaserFuck program's straight runs so the grid honours a width.

Both LaserFuck generators lay their code along *rows*, and both are wide
for the same reason: a run of tape commands is written straight out.  The
boolean generator spends 49 columns on each input reader (``,`` and 48
``-`` to normalize ``'0'``/``'1'``) and another 49 on each leaf's ``+``
run, and the text generator's linear fallback writes one ``+`` per unit of
every byte -- 2423 columns for twenty ``x``\ s.

A newline cannot be inserted into a LaserFuck program the way it can into a
brainfuck one: rows are grid rows, and moving code to the next row moves it
somewhere the beam does not go.  But the beam can be *steered* there, and a
straight run is the easiest thing to steer: it has no mirrors and no
branches, so the only thing that matters is that the beam crosses its cells
in order, moving right.

:func:`fold` does that with a left-returning zigzag, which costs rows
instead of columns.  A straight run is all it handles, because it may break
between any two cells.

The zigzag's leftward legs are usable too, for the runs whose order does
not matter: a stretch of one repeated character reads the same in either
direction, so ``fold`` lays such a stretch backwards along the return row
rather than leaving it blank.  Since the runs that make these grids wide
are precisely the long same-character ones -- 48 ``-`` per reader, one
``+`` per unit of text -- that halves the rows the fold spends on them.

The text generator's *frame* is not a straight run: it interleaves tape ops
with bracket markers, and a marker owns mirror cells on the rows beneath it
whose columns must match its own.  Breaking inside one of those groups
would separate a mirror from the marker it serves.  :func:`fold_groups`
folds the frame anyway, by treating each marker and its mirrors as a single
unbreakable token and only ever breaking between two of them -- the same
token-aware rule the brainfuck-family wrappers in
:mod:`esolangs.tools.wrap` follow, applied to a grid rather than a line.
"""

# The column a fold returns to.  Columns 0..2 carry the funnel (``|o^`` and
# the ``_`` beneath it), which every initial heading is routed through at
# startup, so a zigzag returning to column 0 would drop the beam back onto
# the funnel and start the program over.
MARGIN = 3

# The narrowest width a fold can make progress in: the margin cell that
# turns the beam right, at least one op, and the turn-down that ends the
# segment.  A width below this is ignored rather than raising, matching the
# rest of the width plumbing.
MIN_WIDTH = MARGIN + 2


def fold(
    grid: list[list[str]],
    ops: str,
    row: int,
    col: int,
    width: int,
    left: int = MARGIN,
) -> tuple[int, int]:
    r"""Lay ``ops`` into ``grid`` as a left-returning zigzag.

    ``ops`` is a straight run of tape commands -- no mirrors, no branching
    -- entered on ``row`` at ``col`` with the beam moving right.  Whenever
    the run would pass ``width`` it turns down instead and resumes at
    ``left`` on a lower row, so the run costs rows rather than columns.

    Each fold takes two rows.  ``v`` ends a segment and drops the beam onto
    a *return* row, whose ``{`` sends it back left to the margin, where a
    second ``v`` drops it onto the next segment row; that row opens with
    ``}`` to face the beam right again.  The return row exists because a
    beam travelling left along a segment row would re-execute that segment
    backwards, so the leftward leg needs a row whose code is safe to run in
    reverse.

    A run of one repeated character is exactly that: ``-----`` executed
    right-to-left is the same program as left-to-right.  So the return row
    is not left blank but carries as much of the remaining run as is a
    single repeated character, laid leftwards from the turn-down.  A run
    that is all one character -- every ``+`` run a leaf writes, every ``-``
    run an input reader normalizes with -- therefore uses both legs of the
    zigzag instead of only the rightward one, halving the rows it costs.
    The fill stops at the first character that differs, so the mixed runs
    (a reader's ``,``, a leaf's pointer moves) simply resume rightwards on
    the next segment row as before.

    ``grid`` grows downwards as the fold needs rows, so a caller only has to
    size it for its own geometry; :func:`rows_needed` still estimates the
    cost of a run for a caller that wants to reserve the space up front.

    Returns the row and column the beam occupies once the run is laid, so
    the caller can put whatever follows the run -- ``x``, or the next
    command -- at that cell.
    """
    index = 0
    while index < len(ops):
        room = max(width - col - 1, 1)  # keep a column for the turn-down 'v'
        take = min(room, len(ops) - index)
        for char in ops[index : index + take]:
            grid[row][col] = char
            col += 1
        index += take
        if index < len(ops):
            reserve(grid, row + 2)
            grid[row][col] = "v"
            grid[row + 1][col] = "{"  # return row: head back to the margin
            grid[row + 1][left] = "v"
            # The leftward leg runs the return row backwards, so it may only
            # carry ops that read the same either way: one repeated
            # character.  Lay them from the turn-down back towards the
            # margin, stopping short of it so the 'v' there still catches
            # the beam.
            index += _fill_backwards(grid[row + 1], ops[index:], col - 1, left + 1)
            row += 2
            grid[row][left] = "}"  # next segment row: face right again
            col = left + 1
    reserve(grid, row + 1)
    return row, col


def _fill_backwards(row: list[str], ops: str, start: int, stop: int) -> int:
    """Write the leading same-character run of ``ops`` right-to-left.

    Cells ``start`` down to ``stop`` are filled with the longest prefix of
    ``ops`` made of one repeated character.  Returns how many ops that
    consumed, so the caller can resume the run after them.
    """
    count = 0
    limit = start - stop + 1
    while count < min(len(ops), limit) and ops[count] == ops[0]:
        count += 1
    for offset in range(count):
        row[start - offset] = ops[offset]
    return count


def fold_groups(
    grid: list[list[str]],
    groups: list[tuple[str, str, str]],
    row: int,
    col: int,
    width: int,
    left: int = MARGIN,
) -> tuple[int, int]:
    r"""Lay ``groups`` into ``grid``, breaking only between two of them.

    Each group is a ``(top, middle, bottom)`` triple: what the frame writes
    on its own row, and the mirror cells that must sit directly beneath it
    on the next two rows.  A plain tape op carries blank mirrors; a bracket
    marker carries the cells that turn the beam back into the frame.  The
    triple is written as a unit, so a marker never loses its mirrors to a
    row break -- that is the whole reason this exists rather than
    :func:`fold`.

    The three rows of a segment are followed by a return row, so a segment
    costs four rows against :func:`fold`'s two.  The beam turns down at the
    end of a segment, crosses the two mirror rows, and the return row's
    ``{`` sends it back to ``left`` to start the next segment -- the same
    idiom :func:`fold` uses, given room for the mirrors.

    Returns the row and column the beam occupies after the last group, on
    the *top* row of the final segment.
    """
    index = 0
    while index < len(groups):
        reserve(grid, row + 2)
        room = max(width - col - 1, 1)  # keep a column for the turn-down 'v'
        take = 0
        used = 0
        while index + take < len(groups):
            span = len(groups[index + take][0])
            if used + span > room and take:
                break
            used += span
            take += 1
            # Exactly filling the row ends it here rather than on the check
            # above; the groups so far always leave a cell short of it.
            if used >= room:  # pragma: no cover - no group set fills a row exactly
                break

        for top, middle, bottom in groups[index : index + take]:
            for offset, char in enumerate(top):
                grid[row][col + offset] = char
            for offset, char in enumerate(middle):
                if char != " ":
                    grid[row + 1][col + offset] = char
            for offset, char in enumerate(bottom):
                if char != " ":
                    grid[row + 2][col + offset] = char
            col += len(top)
        index += take

        if index < len(groups):
            reserve(grid, row + 4)
            grid[row][col] = "v"
            # the beam drops past both mirror rows before turning back left
            grid[row + 3][col] = "{"
            grid[row + 3][left] = "v"
            row += 4
            grid[row][left] = "}"
            col = left + 1
    reserve(grid, row + 3)
    return row, col


def reserve(grid: list[list[str]], row: int) -> None:
    """Extend ``grid`` downwards so ``row`` exists."""
    width = len(grid[0]) if grid else 0
    while len(grid) <= row:
        grid.append([" "] * width)


def segment_width(width: int, left: int = MARGIN) -> int:
    """Columns a folded segment can hold between the margin and the turn."""
    return max(width - left - 1, 1)


def rows_needed(run: int, width: int, left: int = MARGIN) -> int:
    """Rows a run of ``run`` ops takes when folded to ``width``.

    Two rows per segment (the segment and the return row beneath it), plus
    a spare pair so a caller can always put a terminator on a fresh row.

    This is an upper bound, not an exact count: :func:`fold` also fills the
    return rows when the run is one repeated character, which can halve the
    rows an all-``+`` or all-``-`` run actually uses.  Callers size their
    grid from this and :func:`fold` grows it further if it ever needs to,
    so an overestimate costs only the blank trailing rows a caller trims.
    """
    segment = segment_width(width, left)
    return 2 * (-(-run // segment) + 1)
