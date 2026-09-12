r"""Fold a LaserFuck program's straight runs so the grid honours a."""

# The column a fold returns to.
# the ``_`` beneath it), which.
# startup, so a zigzag.
# the funnel and start the.
MARGIN = 3

# The narrowest width a fold.
# turns the beam right, at.
# segment.
# the rest of the width.
MIN_WIDTH = MARGIN + 2


def fold(
    grid: list[list[str]],
    ops: str,
    row: int,
    col: int,
    width: int,
    left: int = MARGIN,
) -> tuple[int, int]:
    r"""Lay ``ops`` into ``grid`` as a left-returning zigzag."""
    index = 0
    while index < len(ops):
        room = max(width - col - 1, 1)  # keep a column for the.
        take = min(room, len(ops) - index)
        for char in ops[index : index + take]:
            grid[row][col] = char
            col += 1
        index += take
        if index < len(ops):
            reserve(grid, row + 2)
            grid[row][col] = "v"
            grid[row + 1][col] = "{"  # return row: head back to the.
            grid[row + 1][left] = "v"
            # The leftward leg runs the.
            # carry ops that read the same.
            # character.
            # margin, stopping short of it.
            # the beam.
            index += _fill_backwards(grid[row + 1], ops[index:], col - 1, left + 1)
            row += 2
            grid[row][left] = "}"  # next segment row: face right.
            col = left + 1
    reserve(grid, row + 1)
    return row, col


def _fill_backwards(row: list[str], ops: str, start: int, stop: int) -> int:
    r"""Write the leading same-character run of ``ops`` right-to-left."""
    count = 0
    limit = start - stop + 1
    while count < min(len(ops), limit) and ops[count] == ops[0]:
        count += 1
    for offset in range(count):
        row[start - offset] = ops[offset]
    return count


def reserve(grid: list[list[str]], row: int) -> None:
    r"""Extend ``grid`` downwards so ``row`` exists."""
    width = len(grid[0]) if grid else 0
    while len(grid) <= row:
        grid.append([" "] * width)
