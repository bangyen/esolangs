"""Boolean-function generator for Streetcode.

Through five inputs, a decision tree from labelled loop strips
(:func:`_streetcode_strip`), per-level blocks joined side by side.  Each
per-input strip walks a cell by 48 (an ASCII digit to a bit, a fresh cell
to a digit); its hallway loop spends the 48 as unary cells, 29 rows by 4
columns.

From six inputs the tree goes away: the table is written one cell per
entry and the inputs address it (:func:`_streetcode_flat`), which is nine
rows of street however many entries there are.  The tree folds constant
subtrees; a repeated one is redrawn, not shared: at n=5, sharing every
repeat of 8+ rows for free would save 0.0% (random, const-half) to 0.9%
(tiled), and the flat lookup already wins 40/40 random, 36/40 tiled tables.
"""

from collections.abc import Callable
from functools import cache

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    grid_width,
    input_orders,
    input_weights,
    level_cells,
    move_text,
    permute_truth_table,
)
from esolangs.tools.wrap import balance_score, shortest

__all__ = ["streetcode"]


def _streetcode_combine(arrs: list[list[str]]) -> list[str]:
    """Lay ``arrs`` side by side, padding each to the tallest one's height."""
    top = max(len(arr) for arr in arrs)
    padded = [arr + [" " * len(arr[0])] * (top - len(arr)) for arr in arrs]
    return ["".join(arr[row] for arr in padded) for row in range(top)]


# The counting-loop ring from ``TestStreetcodeCountingLoop``, mirrored
# (counter above the value) so the tree forks with CP left on the value.
# Drive order: the entry ``^`` descend column 1 and run East along row 6
# counting up; ``U`` turns onto the island, and each lap runs North up the
# eastern lane, West along row 5 walking the value, then climbs the western
# lane back around to the corner.
_RING_ROWS = (
    "+  ++  +",
    "|      |",
    "|   ~ _|",
    "| =++_ |",
    "|^ ++ U|",
    "|^    _|",
    "|^^^^^ |",
    "+------+",
)

# Entry cells in drive order: the descent, then East along the southern lane.
# The street cell above the descent is the first of them, so the block holds
# one fewer than the counter it builds.
_RING_ENTRY = [(4, 1), (5, 1), (6, 1)] + [(6, c) for c in range(2, 7)]

# The lap's value cells in drive order, starting just after the ``U``.  They
# stop below the descent gap: the ``=`` at (3,2) hops CP onto the counter
# before the car climbs past it, because that gap is a junction and reads
# whatever cell CP names -- and the value passes through 0 for a ``'0'`` bit,
# which would steer the car out through the gap and back onto the street.
_RING_LAP = [(4, 5), (5, 5)] + [(5, c) for c in range(4, 1, -1)] + [(4, 2)]

# 48 is what a collect loop subtracts and what a loader loop adds, and the
# block's runs are long enough to factor it as eight laps of six.
_RING_COUNTER = 8
_RING_PER_LAP = 6


def _streetcode_ring(c: str) -> list[str]:
    """Build a counting loop that walks a cell by 48, eight laps of six ``c``.

    The car counts the counter to eight, U-turns onto the island and laps
    it; the countdown steers the exit with CP back on the value.  ``c`` is
    ``'~'`` (walk a digit down to a bit) or ``'^'`` (ramp a cell up).
    """
    grid = [list(row) for row in _RING_ROWS]
    for cells, keep, char in (
        (_RING_ENTRY, _RING_COUNTER - 1, "^"),
        (_RING_LAP, _RING_PER_LAP, c),
    ):
        for i, (r, col) in enumerate(cells):
            if i < keep:
                grid[r][col] = char
    return ["".join(row) for row in grid]


def _streetcode_hallway(c: str) -> list[str]:
    """Build a wall-hugging loop of exactly 48 ``c`` cells, one per row-pair.

    29 rows by 4 columns, for width-constrained programs.
    """
    top = ["----", "    ", "    ", "+  +", "|  |"]
    row = f"|{c * 2}|"
    return [*top, *([row] * 24), "+--+"]


def _streetcode_strip(before: str, block: list[str]) -> list[str]:
    """Build a labeled loop room: ``before`` runs as instructions, then ``block``.

    ``before`` is both the label and the instructions driven to reach the
    room; its trailing ``^`` is what the junction at the mouth reads.
    """
    width = len(before)
    wall = "-" * width
    first = [wall, " " * width, before, wall]
    return _streetcode_combine([first, block])


# ``~=I^`` leads into a collect loop: ``~`` consumes the +1 the previous loop
# left on the cell behind, ``=`` advances CP onto a fresh cell, ``I`` reads
# the next bit (ASCII ``'0'``/``'1'``), and ``^`` bumps it to 49 or 50, which
# forces the cell nonzero before the loop's junction is tested -- the
# ambiguous-turn rule (leftmost when the CPth cell is 0, otherwise
# second-leftmost) has to see a nonzero cell to turn into the loop rather
# than drive past it.  The loader label is the same without an ``I``.
# The +1 it leaves behind is not slack. Every gap crossing reads the CPth
# cell; a bare 0 there would steer the car West back down the street instead
# of East onto the next loop.


def _streetcode_constant(block: list[str]) -> bool:
    """Whether every leaf in a rendered subtree prints the same digit.

    Read off the drawing: a zero leaf is ``~O;`` and a one leaf ``` O;```, so
    all-zeros has matching ``~`` and ``O`` counts and all-ones no ``~``.
    """
    text = "".join(block)
    return text.count("~") == text.count("O") or text.count("~") == 0


def _streetcode_leaf(bit: int, skipped: int = 0) -> list[str]:
    r"""Build a leaf that prints ``bit``, reusing the loader loop's cell.

    CP arrives on a cell at ``'0'`` + 1; ``~`` corrects a 0 leaf.  ``skipped``
    folded levels each owed one ``=`` advance, which the leaf spends itself
    (an all-zeros table printed ``'\x00'`` before this).
    """
    op = " " if bit else "~"
    body = "=" * skipped + f"{op}O;"
    return [
        "-" * len(body) + "+",
        " " * len(body) + "|",
        body + "|",
        "-" * len(body) + "+",
    ]


# Largest subtable whose drawing is worth remembering across the identity
# and greedy candidates.  Small repeated halves share drawings; caching
# larger, usually distinct subtrees only retains their grids.
_TREE_CACHE_MAX = 2**4


def _streetcode_tree(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit."""
    if len(table) > _TREE_CACHE_MAX:
        return _streetcode_tree_span(table, 0, len(table), constant_span_test(table))
    # Copied out: the cache hands back the same object to every caller, and
    # ``_streetcode_combine`` and ``_streetcode_lift`` both treat their rows
    # as read-only today, which is not a property to leave load-bearing.
    return list(_streetcode_tree_memo(table))


def _streetcode_tree_span(
    table: str,
    start: int,
    stop: int,
    constant: Callable[[int, int], bool],
) -> list[str]:
    """Build a large tree by bounds, delegating small spans to the cache."""
    size = stop - start
    if size <= _TREE_CACHE_MAX:
        return _streetcode_tree(table[start:stop])

    half = size // 2
    middle = start + half
    skipped = half.bit_length() - 1
    top = (
        _streetcode_leaf(int(table[start]), skipped)
        if constant(start, middle)
        else _streetcode_tree_span(table, start, middle, constant)
    )
    bot = (
        _streetcode_leaf(int(table[middle]), skipped)
        if constant(middle, stop)
        else _streetcode_tree_span(table, middle, stop, constant)
    )
    return _streetcode_join(top, bot)


@cache
def _streetcode_tree_memo(table: str) -> tuple[str, ...]:
    """Build one small subtree, remembered; see :data:`_TREE_CACHE_MAX`.

    Halves are joined by a hall that advances CP one ``=`` and forks on the
    bit.  A constant subtree folds to a leaf (389 chars for the constant table
    at three inputs); the reads happen before the tree, so a folded program
    consumes its input unchanged.  Siblings are padded to a common width.
    """
    size = len(table)
    if size == 1:
        return tuple(_streetcode_leaf(int(table[0])))

    half = size // 2
    top = _streetcode_tree(table[:half])
    bot = _streetcode_tree(table[half:])
    if _streetcode_constant(top):
        top = _streetcode_leaf(int(table[0]), half.bit_length() - 1)
    if _streetcode_constant(bot):
        bot = _streetcode_leaf(int(table[half]), half.bit_length() - 1)
    return tuple(_streetcode_join(top, bot))


def _streetcode_join(top: list[str], bot: list[str]) -> list[str]:
    """Join two finished subtrees with their shared branching hall."""
    width = max(max(len(row) for row in top), max(len(row) for row in bot))
    top = [row.ljust(width) for row in top]
    bot = [row.ljust(width) for row in bot]
    height = len(top)

    hall = []
    # The hall spans both children, which folding can leave unequal in height.
    for k in range(len(top) + len(bot)):
        if k == 0:
            row = "----"
        elif k == 1:
            row = "    "
        elif k == 2:
            row = "   ="
        elif k == 3:
            row = "+  +"
        elif k == 4:
            # Four rows tall means a leaf-height child, folded or not.
            row = "|  +" if height == 4 else "|  |"
        elif k < height:
            row = "|  |"
        elif k == height:
            row = "|  +"
        elif k < height + 2:
            row = "|   "
        elif k == height + 2:
            row = "|  ="
        elif k == height + 3:
            row = "+---"
        else:
            row = "    "
        hall.append(row)

    return _streetcode_combine([hall, [*top, *bot]])


def _streetcode_lift(rows: list[str]) -> list[str]:
    """Run the leading instructions westbound along row 1 instead of row 2.

    Row 1 is the blank oncoming lane, so starting the car there frees the
    leading run's columns (nine for the ring's labels, seven for the
    hallway's) from every row.  Written East-to-West, hairpinning at the west
    wall.  The run's leading ``^`` keeps cell 0 nonzero across every loop
    mouth, so no junction captures the car.
    """
    lane = rows[2]
    # The prefix runs from the ``C`` to the first blank; what follows it
    # belongs to loops the car only meets after the hairpin.
    start = lane.index("C")
    end = start
    while end < len(lane) and lane[end] != " ":
        end += 1

    width = max(len(row) for row in rows)
    grid = [list(row.ljust(width)) for row in rows]
    prefix = "".join(grid[2][start:end])
    # Drop the columns the prefix occupied, from every row.
    kept = [c for c in range(width) if not (start <= c < end)]
    grid = [[row[c] for c in kept] for row in grid]

    # Write it into row 1 reversed, ending against the eastern wall, which
    # is found rather than assumed to be the last column: a block hanging
    # below the street can be wider than the street, and ``width`` is the
    # widest row of the whole grid.  ``generate("Streetcode", "0001", width=20)``
    # was one of four two-input tables whose prefix landed outside the wall.
    east = "".join(grid[0]).rindex("+") - 1
    for i, char in enumerate(prefix):
        grid[1][east - i] = char

    # With the label gone, the first loop's block is flush against the
    # street's western wall, which leaves two wall columns side by side:
    # the street's own, walling rows 0-3, and the block's, walling rows 3
    # down.  They only ever meet at row 3, so one column does for both --
    # drop the street's and let the block's carry the street rows too,
    # taking one more column off every row.
    grid = [row[1:] for row in grid]
    grid[0][0] = "+"
    grid[1][0] = "|"
    grid[2][0] = "|"
    return ["".join(row).rstrip() for row in grid]


def _streetcode_populate(n: int) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader is an input loop without ``I``; its label's ``^`` forces the
    turn and ramps a fresh cell to ``'0'`` + 1 (:func:`_streetcode_leaf`).
    """
    start = ["+--", "|  ", "|C^", "+--"]
    col = _streetcode_strip("~=I^", _streetcode_hallway("~"))
    # The rewind strip walks CP back over the n cells the input loops filled,
    # so it carries n '_' instructions.  Streets are two characters wide, so
    # a single '_' would draw a one-wide room the car cannot legally drive:
    # pad the label out to the minimum width with spaces, which are no-ops.
    rewind = ("_" * n).ljust(2)
    width = len(rewind)
    return _streetcode_combine(
        [
            start,
            *([col] * n),
            _streetcode_strip("~=^", _streetcode_hallway("^")),
            ["-" * width, " " * width, rewind, "-" * width],
        ],
    )


# The shared lap's ring, widened by ``k``.  Only the steering assembly is
# fixed -- the ``=`` hop below the descent gap, the countdown ``~`` on the
# top row, and the ``_`` that drops
# CP on the way out -- because those sit on paths the linear body cannot
# describe.  The cell the single-loop ring used to drop CP on for the *next*
# lap is deliberately blank: the body's own rewind is sized for arriving with
# CP on the counter, so the continue path has to hand it the same CP the
# first entry does.
_SHARED_ROWS = (
    "+  +{dash}+  +",
    "|      {gap}|",
    "|   ~ {gap}_|",
    "| =+{dash}+  |",
    "|  +{dash}+ U|",
    "|     {gap} |",
    "|     {gap} |",
    "+------{dash}+",
)


def _streetcode_shared_lap(body: str) -> list[str]:
    """Draw the shared lap, widened just enough to hold ``body``.

    North up the eastern lane, West along the island, one cell North, stopping
    below the descent gap whose ``=`` hops CP onto the counter.
    """
    k = max(0, len(body) - 6)
    grid = [list(row.format(gap=" " * k, dash="-" * k)) for row in _SHARED_ROWS]
    cells = [(4, 5 + k), (5, 5 + k)] + [(5, c) for c in range(4 + k, 1, -1)] + [(4, 2)]
    for i, char in enumerate(body):
        r, c = cells[i]
        grid[r][c] = char
    return ["".join(row) for row in grid]


def _streetcode_shared(n: int, perm: tuple[int, ...] | None = None) -> list[str]:
    """Build the populate phase as one shared 48-lap loop over every cell.

    Cells: inputs at 1..n, loader n+1, counter n+2, ring cell n+3.  Both
    junctions read the counter, and the drop out lands on the loader, seeded
    to 1 (required).  ``perm`` changes only the prefix (``==I_I`` vs
    ``=I=I``); reads stay in stream order, and the walks are down the shaft,
    crossing no mouth.  The seeding suffix is relative to cell ``n``.
    """
    perm = tuple(range(n)) if perm is None else perm
    body = "_" * (n + 1) + "~=" * n + "^"
    # No ``^`` after the reads: ``I`` stores the code point of an ASCII digit,
    # 48 or 49, so a cell it has just filled is nonzero on its own and needs
    # no bump to satisfy the mouths' junctions.  The ring then subtracts
    # exactly 48 and the inputs land on bare bits, so the tail only has to
    # walk CP back -- there is no +1 for it to take off.
    cells = level_cells(perm)
    reads = ""
    at = 0
    for cell in cells:
        reads += move_text(at, cell, "=", "_") + "I"
        at = cell
    # Back to cell ``n``, which the seeding suffix below counts from.  Under
    # the identity order the last read already left CP there and the walk is
    # empty, so the prefix is spelled exactly as it was.
    prefix = "C" + reads + move_text(at, n, "=", "_") + "=^==^"
    tail = "_" * n
    blocks = [_streetcode_ring("^"), _streetcode_shared_lap(body)]

    # The prefix runs down a shaft rather than along the street: the car
    # drives the western lane downward and the eastern one back up, so its
    # 2n+6 instructions cost four columns instead of 2n+6.  The eastern lane
    # is drawn bottom-up, since that is the order the climb reads it.
    down, up = prefix[: len(prefix) // 2], prefix[len(prefix) // 2 :]
    depth = max(len(down), len(up))
    down = down.ljust(depth)
    up = up.ljust(depth)

    # The street is left open at its eastern end: the tree is joined on there
    # by :func:`_streetcode_combine` and supplies the closing wall, exactly as
    # the strip shapes' populate does.
    head = 4  # the shaft's western wall, its two lanes, and its eastern wall
    width = head + sum(len(b[0]) for b in blocks) + len(tail)
    height = max(3 + max(len(b) for b in blocks), 5 + depth)
    grid = [[" "] * width for _ in range(height)]
    grid[0] = list("+" + "-" * (width - 1))
    for r in (1, 2):
        grid[r][0] = "|"
    grid[3] = list("+" + "-" * (width - 1))
    # Cut the shaft's mouth into the street's southern wall and draw it.
    grid[3][1] = grid[3][2] = " "
    grid[3][3] = "+"
    for i in range(depth):
        grid[4 + i][0] = "|"
        grid[4 + i][1] = down[i]
        grid[4 + i][2] = up[depth - 1 - i]
        grid[4 + i][3] = "|"
    for c in range(head):
        grid[4 + depth][c] = "+" if c in (0, head - 1) else "-"
    left = head
    for block in blocks:
        for r, row in enumerate(block):
            for c, char in enumerate(row):
                grid[3 + r][left + c] = char
        left += len(block[0])
    for i, char in enumerate(tail):
        grid[2][left + i] = char
    return ["".join(row) for row in grid]


def _streetcode_rotate(program: str) -> str:
    """Rotate a Streetcode grid 180 degrees and trim its new line ends.

    Rotation preserves right-hand driving; a reflection would not.  The
    generator no longer tries it; the balancer does.
    """
    rows = program.splitlines()
    width = max(map(len, rows))
    return "\n".join(row.ljust(width)[::-1].rstrip() for row in reversed(rows))


def _streetcode_quarter_turn(program: str) -> str:
    """Turn the complete street clockwise, exchanging horizontal/vertical walls."""
    rows = program.splitlines()
    span = max(map(len, rows))
    walls = str.maketrans("-|", "|-")
    padded = [row.ljust(span) for row in rows]
    return "\n".join(
        "".join(row[col] for row in reversed(padded)).translate(walls).rstrip()
        for col in range(span)
    )


# The flat lookup's nine rows, top to bottom.  Sharing the kerb removes the
# stalk; both sets of corners still bound the junction.
_ROOF, _UP, _DOWN, _FLOOR, _STALK, _KERB, _WEST, _EAST, _SILL = range(9)


def _streetcode_shared_kerb(program: str) -> str:
    """Share the side-room floors with the street kerb, removing the stalk."""
    rows = program.splitlines()
    kerb = list(rows[_KERB])
    for col, char in enumerate(rows[_FLOOR]):
        if char == "+":
            kerb[col] = char
    return "\n".join([*rows[:_FLOOR], "".join(kerb), *rows[_WEST:]])


# ``I`` and the 48 ``~`` behind it: a junction tests a cell for zero and an
# ASCII digit is 48 or 49, so the read has to be walked down to its bit.
_READ_RUN = 49

# The finish, driven east to west and so written backwards: ``_`` onto the
# answer cell, 48 ``^`` to lift its bit to a digit, then print and halt.
_TAIL = ";O" + "^" * 48 + "_"


def _streetcode_mouths(
    n: int, first: int, gaps: list[int]
) -> list[tuple[int, int, int]]:
    """Return each level's mouth column, room width and leftward walk.

    Level ``k`` skips ``2 ** (n - 1 - k)`` cells, so the rooms halve going
    east and the narrow ones are spaced by their read run instead.  A room
    holds two cells per column and one more than the walk, for the ``^``
    that steers the exit.  The gap to the next mouth is sized from the room
    *that* mouth carries, since a room hangs west of its own: sized from
    this one's the rooms overlap from eight inputs up, where a room first
    outgrows the read run, and the grid stops rendering.  ``gaps``, in read
    order, widens a read run by the ignored inputs read just ahead of it.
    """
    walks = [1 << level for level in range(n)]
    rooms = [max(2, -(-(walk + 1) // 2)) for walk in walks]
    mouths = []
    col = first
    for step, (walk, room) in enumerate(zip(walks, rooms, strict=True)):
        mouths.append((col, room, walk))
        if step + 1 < n:
            col += max(_READ_RUN + 2 + gaps[n - 1 - step], rooms[step + 1] + 2)
    mouths.reverse()
    return mouths


def _streetcode_room(
    grid: dict[tuple[int, int], str], mouth: int, room: int, walk: int
) -> None:
    """Draw one level's side room, its stalk, and the read run east of it.

    The room is a dead end: up the stalk's eastern lane, west along the
    upper lane, hairpin, back east along the lower one, so its two lanes run
    ``2 * room`` cells in that order.  The walk's ``_`` fill them and the
    ``^`` after them leaves the cell CP lands on nonzero, which is what
    steers the merge back west -- a merge re-reads the cell, and on a zero
    it would rejoin the street heading east instead.
    """
    east = mouth + 1
    west = east - room + 1
    grid[_ROOF, west - 1] = grid[_ROOF, east + 1] = "+"
    for col in range(west, east + 1):
        grid[_ROOF, col] = "-"
    for row in (_UP, _DOWN):
        grid[row, west - 1] = grid[row, east + 1] = "|"
        for col in range(west, east + 1):
            grid[row, col] = " "
    grid[_FLOOR, west - 1] = grid[_FLOOR, mouth - 1] = "+"
    for col in range(west, mouth - 1):
        grid[_FLOOR, col] = "-"
    grid[_FLOOR, east + 1] = grid[_STALK, east + 1] = "|"
    grid[_STALK, mouth - 1] = "|"
    grid[_KERB, mouth - 1] = grid[_KERB, east + 1] = "+"
    for row in (_FLOOR, _STALK, _KERB):
        grid[row, mouth] = grid[row, east] = " "
    drive = [(_DOWN, east), (_UP, east)]
    drive += [(_UP, col) for col in range(east - 1, west - 1, -1)]
    drive += [(_DOWN, col) for col in range(west, east)]
    for row, col in drive[:walk]:
        grid[row, col] = "_"
    grid[drive[walk]] = "^"
    grid[_WEST, mouth + _READ_RUN + 1] = "I"
    for col in range(mouth + 2, mouth + _READ_RUN + 1):
        grid[_WEST, col] = "~"


def _streetcode_flat(truth_table: str, n: int) -> str:
    """Build the table as cells and drive to the one the inputs address.

    Cell ``c`` holds entry ``T - 1 - c``, written by the eastbound lane; the
    westbound lane then reads input ``k`` and forks at level ``k``'s mouth,
    whose room walks CP left by ``2 ** (n - 1 - k)`` when the bit is one.
    CP lands on ``T - index``, one east of the answer, and every cell an
    ``I`` overwrites is east of that.  The fill's last ``^`` leaves cell
    ``T`` nonzero, which is what drives the fill past the mouths.

    An ignored input is a lone ``I`` just east of the next indexed input's,
    whose read overwrites the cell; one past the last indexed input is an
    ``I`` ahead of the tail.  The table holds the indexed inputs' entries alone.
    """
    weights, table = input_weights(truth_table, n)
    if len(table) > 1:
        truth_table, n = table, len(table).bit_length() - 1
    else:
        weights = [1] * n  # a constant keeps one level to fork on
    gaps, pending = [], 0
    for weight in weights:
        if weight:
            gaps.append(pending)
            pending = 0
        else:
            pending += 1
    fill = "".join(("^" if bit == "1" else "") + "=" for bit in reversed(truth_table))
    fill += "^"
    # ``pending`` trailing ignored inputs are lone ``I`` between the last
    # mouth and the tail; each overwrites the cell CP rests on, one east of
    # the answer, which the tail's ``_`` leaves behind.
    mouths = _streetcode_mouths(n, max(len(fill) + 3, len(_TAIL) + pending + 1), gaps)
    width = mouths[0][0] + _READ_RUN + 2 + gaps[0]
    grid: dict[tuple[int, int], str] = {}
    for col in range(width + 2):
        grid[_KERB, col] = grid[_SILL, col] = "-"
    for row, char in ((_KERB, "+"), (_SILL, "+"), (_WEST, "|"), (_EAST, "|")):
        grid[row, 0] = grid[row, width + 1] = char
    for col in range(1, width + 1):
        grid[_WEST, col] = grid[_EAST, col] = " "
    for (mouth, room, walk), gap in zip(mouths, gaps, strict=True):
        _streetcode_room(grid, mouth, room, walk)
        for col in range(mouth + _READ_RUN + 2, mouth + _READ_RUN + 2 + gap):
            grid[_WEST, col] = "I"
    for step, char in enumerate(_TAIL + "I" * pending):
        grid[_WEST, mouths[-1][0] - len(_TAIL) - pending + step] = char
    grid[_EAST, 1] = "C"
    for step, char in enumerate(fill):
        grid[_EAST, 2 + step] = char
    return "\n".join(
        "".join(grid.get((row, col), " ") for col in range(width + 2)).rstrip()
        for row in range(_SILL + 1)
    )


def _streetcode_hallway_program(n: int, tree: list[str]) -> str:
    """Render the narrow per-input layout used for width selection."""
    return "\n".join(
        _streetcode_lift(_streetcode_combine([_streetcode_populate(n), tree]))
    )


def _streetcode_shared_programs(truth_table: str, n: int, tree: list[str]) -> list[str]:
    """Render the shared-lap layouts for every permitted input order."""
    identity = tuple(range(n))
    programs = []
    for perm in input_orders(truth_table):
        shared = _streetcode_combine(
            [
                _streetcode_shared(n, perm),
                tree
                if perm == identity
                else _streetcode_tree(permute_truth_table(truth_table, perm)),
            ],
        )
        # Padding siblings to a common width leaves trailing blanks on the
        # shorter one's rows; they are outside the walls and never driven.
        programs.append("\n".join(row.rstrip() for row in shared))
    return programs


def _streetcode_narrow(flat: str, width: int) -> str:
    """Turn the indexed street clockwise: nine columns, or seven with a shared kerb."""
    return _streetcode_quarter_turn(
        _streetcode_shared_kerb(flat) if width < _SILL + 1 else flat
    )


def streetcode(truth_table: str, width: int | None = None) -> str:
    """Build a Streetcode program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  From
    six inputs the table is one cell per entry, addressed by the inputs
    (:func:`_streetcode_flat`); below that, a populate phase plus a decision
    tree.  The shortest shape wins.  A 180-degree rotation only strips
    trailing blanks (0.0% by area at n=2-8, worse at n=5), so it is not tried.
    ``width`` chooses among the shapes rather than reflowing (rows are
    streets); when none fit, a clockwise turn of the indexed street gives a
    nine-column floor, seven with its room floors shared with the kerb.
    That floor is the indexed street, one cell per entry addressed by position,
    so constant halves and repeats have no subtree to fold or share; ignored
    inputs still drop.  A tree one column past ``width`` falls to it (11x38
    -> 258x9 at ``width=40``), which is a shape switch, not a missing piece.
    """
    n = _validate_truth_table(truth_table)
    if n >= 6:
        flat = _streetcode_flat(truth_table, n)
        if width is None or grid_width(flat) <= width:
            return flat
        return _streetcode_narrow(flat, width)
    tree = _streetcode_tree(truth_table)
    # The per-input loops trade rows for columns, so only width selection
    # needs them.  The shared lap is strictly shorter through every table at
    # n <= 3 and every sampled n == 4 table, while its fixed setup wins more
    # decisively as the input count grows.
    programs = [_streetcode_hallway_program(n, tree)] if width is not None else []
    # The shared shape is not lifted: its prefix is as long as the street it
    # heads, so a westbound run of it crosses the loops' own mouths, and at
    # each one CP names a cell nothing has seeded yet.  No ordering of the
    # seeds avoids that.  It is built once per input order, identity first,
    # so a table no reorder improves keeps the program it already emitted.
    programs.extend(_streetcode_shared_programs(truth_table, n, tree))
    # At five the flat lookup wins on dense and parity tables and loses on
    # one that folds, so it is compared; without it parity at five costs
    # 3251 against 2534 and the odd rungs stop growing linearly.
    if n == 5:
        programs.append(_streetcode_flat(truth_table, n))
    if width is not None:
        fitting = [p for p in programs if grid_width(p) <= width]
        if fitting:
            return shortest(*fitting)
        # The indexed street has nine rows at every arity; rotating it
        # makes those the width floor while preserving right-hand driving.
        return _streetcode_narrow(_streetcode_flat(truth_table, n), width)
    return shortest(*programs)
    rotated = [_streetcode_rotate(program) for program in programs]
    return shortest(*programs, *rotated)


def _balance(table: str, default: str) -> str:
    """Compare each fit threshold and the seven/nine-column fallback regimes."""
    n = _validate_truth_table(table)
    if n >= 6:
        flat = _streetcode_flat(table, n)
        shapes = [flat, _streetcode_rotate(flat)]
    else:
        tree = _streetcode_tree(table)
        shapes = [
            _streetcode_hallway_program(n, tree),
            *_streetcode_shared_programs(table, n, tree),
        ]
        if n == 5:
            shapes.append(_streetcode_flat(table, n))
    # A requested width changes the shortest fitting shape only when another
    # shape starts fitting; asking at that shape's span also excludes losers.
    candidates = [default, streetcode(table, 1), streetcode(table, 9)]
    candidates.extend(streetcode(table, grid_width(shape)) for shape in shapes)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Streetcode",
    "grid_based.streetcode",
    boolean=streetcode,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="Streetcode program cannot be empty",
)
