"""Streetcode Boolean program generator: a decision tree, then a flat indexed street.

Through five inputs, a decision tree from labelled loop strips
(:func:`_streetcode_strip`), per-level blocks joined side by side.  Each
per-input strip walks a cell by 48 (an ASCII digit to a bit, a fresh cell
to a digit); its hallway loop spends the 48 as unary cells, 30 rows by 4
columns.

From six inputs the canonical shape is flat: the table is written one cell
per entry and the inputs address it (:func:`_streetcode_flat`), which is
nine rows of street however many entries there are; only the minority
entries are marked: a one by ``^``, or, when the zeros are fewer by two,
a zero by ``~`` (the tail lifts 49 and the rooms steer with two ``^``), so
a table dense in ones writes as short a street as its complement (thr2
n=8: 8,856 -> 6,723 cells); the tree races it by
area where it folds ([ablations.flat_tree_race]). The tree folds constant
subtrees and draws equal nonconstant sibling cofactors once, advancing CP
past their selector. Nonadjacent repeats still have separate drawings: they
hold 2.4% of tree nodes at n=4 and 5.1% at n=5 (200 random tables), an
upper bound on sharing before the routing that would merge two paths.

Size:
    O(T) area from six inputs, at most the flat street's; n=4 parity: 3,391
    chars, n=10 random 1847: 21,421 chars, n=10 parity: 21,421 chars.

Decisions:
    A half-turn rotation only strips trailing blanks (0.0% by area at n=2-8),
    so it is not tried.  When no shape fits ``width``, a clockwise turn of the
    indexed street gives a nine-column floor, seven with its room floors
    shared with the kerb.  Being one cell per entry, it has no constant halves
    or repeats to fold or share; ignored inputs still drop.  A tree one column
    past ``width`` falls to it (``00000011``: 12x41 -> 165x9 at ``width=40``):
    a shape switch, not a missing piece.

    ``balance`` snakes the indexed street into strips (456x9 -> 98x48 at
    n=6 random).  Blocks stand two blank rows apart and cuts keep four clear
    columns each side, so no foreign wall is within a car's three-cell
    reading; that keeps the fold sound without a drive check (the
    oracle is in the tests).  The gaps cost area against the old shared-sill
    fold: 80x45 -> 98x48 at n=6, 91x47 -> 110x54 at n=7, 112x51 -> 127x66
    at n=8.  From n=9 the rooms chain into one uncuttable block about ``T/2``
    wide (n=11: 1021 columns), which caps the gain near 4x.
"""

from collections.abc import Callable, Iterator
from functools import cache
from itertools import pairwise
from math import isqrt
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    grid_area,
    grid_rank,
    grid_width,
    input_weights,
)
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.streetcode.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

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
        for r, col in cells[:keep]:
            grid[r][col] = char
    return ["".join(row) for row in grid]


def _streetcode_hallway(c: str) -> list[str]:
    """Build a wall-hugging loop of exactly 48 ``c`` cells, one per row-pair.

    30 rows by 4 columns, for width-constrained programs.
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
    # ``_streetcode_combine`` treats its rows as read-only today, which is
    # not a property to leave load-bearing.
    return list(_streetcode_tree_memo(table))


def _streetcode_tree_span(
    table: str,
    start: int,
    stop: int,
    constant: Callable[[int, int], bool],
) -> list[str]:
    """Build a tree by bounds, caching only its small nonconstant children."""
    size = stop - start
    shared = _streetcode_shared_half(table[start:stop])
    if shared is not None:
        return shared
    middle = start + size // 2
    skipped = (size // 2).bit_length() - 1

    def child(lo: int, hi: int) -> list[str]:
        if constant(lo, hi):
            return _streetcode_leaf(int(table[lo]), skipped)
        # A child is half a span, and spans start at most 32 long (the tree
        # is only built through five inputs), so every child fits the memo.
        return list(_streetcode_tree_memo(table[lo:hi]))

    return _streetcode_join(child(start, middle), child(middle, stop))


def _streetcode_shared_half(table: str) -> list[str] | None:
    """Draw equal nonconstant sibling cofactors once, skipping their selector."""
    # At n=3, emitted grid area falls from 258856 to 228946 cells over all
    # tables; none grows. Two label columns preserve the two-lane street.
    half = len(table) // 2
    child = table[:half]
    if child != table[half:] or len(set(child)) != 2:
        return None
    return _streetcode_strip("= ", _streetcode_tree(child))


@cache
def _streetcode_tree_memo(table: str) -> tuple[str, ...]:
    """Build one small subtree, remembered; see :data:`_TREE_CACHE_MAX`.

    Halves are joined by a hall that advances CP one ``=`` and forks on the
    bit.  A constant subtree folds to a leaf (389 chars for the constant table
    at three inputs); the reads happen before the tree, so a folded program
    consumes its input unchanged.  Siblings are padded to a common width.
    """
    return tuple(_streetcode_tree_span(table, 0, len(table), constant_span_test(table)))


def _streetcode_join(top: list[str], bot: list[str]) -> list[str]:
    """Join two finished subtrees with their shared branching hall."""
    width = max(map(len, [*top, *bot]))
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


def _streetcode_populate(n: int) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader is an input loop without ``I``; its label's ``^`` forces the
    turn and ramps a fresh cell to ``'0'`` + 1 (:func:`_streetcode_leaf`).
    """
    start = ["+--", "|  ", "|C^", "+--"]
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
    for (r, c), char in zip(cells, body, strict=False):
        grid[r][c] = char
    return ["".join(row) for row in grid]


def _streetcode_shared(n: int) -> list[str]:
    """Build the populate phase as one shared 48-lap loop over every cell.

    Cells: inputs at 1..n, loader n+1, counter n+2, ring cell n+3.  Both
    junctions read the counter, and the drop out lands on the loader, seeded
    to 1 (required).  The walks are down the shaft, crossing no mouth.  The
    seeding suffix is relative to cell ``n``.
    """
    body = "_" * (n + 1) + "~=" * n + "^"
    # No ``^`` after the reads: ``I`` stores the code point of an ASCII digit,
    # 48 or 49, so a cell it has just filled is nonzero on its own and needs
    # no bump to satisfy the mouths' junctions.  The ring then subtracts
    # exactly 48 and the inputs land on bare bits, so the tail only has to
    # walk CP back -- there is no +1 for it to take off.
    reads = "=I" * n
    # Cells 1..n are read in turn, and CP ends on cell ``n`` where the seeding
    # suffix counts from.
    prefix = "C" + reads + "=^==^"
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
            grid[3 + r][left : left + len(row)] = row
        left += len(block[0])
    grid[2][left : left + len(tail)] = tail
    return ["".join(row) for row in grid]


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
    grid: dict[tuple[int, int], str],
    mouth: int,
    room: int,
    walk: int,
    steer: int = 1,
) -> None:
    """Draw one level's side room, its stalk, and the read run east of it.

    The room is a dead end: up the stalk's eastern lane, west along the
    upper lane, hairpin, back east along the lower one, so its two lanes run
    ``2 * room`` cells in that order.  The walk's ``_`` fill them and the
    ``^`` after them leaves the cell CP lands on nonzero, which is what
    steers the merge back west -- a merge re-reads the cell, and on a zero
    it would rejoin the street heading east instead.  A cell marked ``~``
    holds -1, which one ``^`` zeroes; ``steer`` is the ``^`` count (two
    fit the room: it has 2 * room >= walk + 2 cells).
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
    for cell in drive[walk : walk + steer]:
        grid[cell] = "^"
    grid[_WEST, mouth + _READ_RUN + 1] = "I"
    for col in range(mouth + 2, mouth + _READ_RUN + 1):
        grid[_WEST, col] = "~"


class _FlatInputs(NamedTuple):
    """The indexed table, its arity, per-level ignored-input gaps, trailing run."""

    table: str
    n: int
    gaps: list[int]
    pending: int


def _flat_inputs(truth_table: str, n: int) -> _FlatInputs:
    """Return the table reduced to its indexed inputs."""
    weights, table = input_weights(truth_table, n)
    if len(table) > 1:
        n = len(table).bit_length() - 1
    else:
        # A constant keeps one level to fork on, over two equal cells; the
        # other inputs are lone reads.
        weights = [0] * (n - 1) + [1]
        table, n = table * 2, 1
    gaps, pending = [], 0
    for weight in weights:
        if weight:
            gaps.append(pending)
            pending = 0
        else:
            pending += 1
    return _FlatInputs(table, n, gaps, pending)


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
    truth_table, n, gaps, pending = _flat_inputs(truth_table, n)
    # Only the minority entry is marked: a one by ``^``, or, with the zeros
    # marked ``~`` and the tail lifting 49, a zero.  The tail's extra ``^``
    # is paid for by the minority.
    negated = truth_table.count("0") + 1 < truth_table.count("1")
    mark = "~" if negated else "^"
    tail = _TAIL.replace("_", "^_") if negated else _TAIL
    marked = "0" if negated else "1"
    fill = "".join(
        (mark if bit == marked else "") + "=" for bit in reversed(truth_table)
    )
    fill += "^"
    # ``pending`` trailing ignored inputs are lone ``I`` between the last
    # mouth and the tail; each overwrites the cell CP rests on, one east of
    # the answer, which the tail's ``_`` leaves behind.
    # The tail gets its own columns between the fill and the first mouth.
    # Overlapping it onto the fill's columns saved a fixed ~51 columns --
    # 8.6% of area at n=7, 6.0% at n=8, a share falling with arity -- under
    # the genuine-percentage rule in docs/CONTRIBUTING.md.
    mouths = _streetcode_mouths(n, len(fill) + 3 + len(tail) + pending, gaps)
    width = mouths[0][0] + _READ_RUN + 2 + gaps[0]
    grid: dict[tuple[int, int], str] = {}
    for col in range(width + 2):
        grid[_KERB, col] = grid[_SILL, col] = "-"
    for row, char in ((_KERB, "+"), (_SILL, "+"), (_WEST, "|"), (_EAST, "|")):
        grid[row, 0] = grid[row, width + 1] = char
    for col in range(1, width + 1):
        grid[_WEST, col] = grid[_EAST, col] = " "
    for (mouth, room, walk), gap in zip(mouths, gaps, strict=True):
        _streetcode_room(grid, mouth, room, walk, 1 + negated)
        for col in range(mouth + _READ_RUN + 2, mouth + _READ_RUN + 2 + gap):
            grid[_WEST, col] = "I"
    for step, char in enumerate(tail + "I" * pending):
        grid[_WEST, mouths[-1][0] - len(tail) - pending + step] = char
    grid[_EAST, 1] = "C"
    for step, char in enumerate(fill):
        grid[_EAST, 2 + step] = char
    return "\n".join(
        "".join(grid.get((row, col), " ") for col in range(width + 2)).rstrip()
        for row in range(_SILL + 1)
    )


def _streetcode_hallway_program(n: int, tree: list[str]) -> str:
    """Render the narrow per-input layout used for width selection."""
    return "\n".join(_streetcode_combine([_streetcode_populate(n), tree]))


def _streetcode_shared_program(n: int, tree: list[str]) -> str:
    """Render the shared-lap layout in input order.

    The greedy reorder saved 3.6% of area at n=3, 3.8% at n=4 and 0% at n=5
    (over 256/150/150 tables; the lookup replaces trees from n=6), under the
    10% bar.  Padding siblings to a common width leaves trailing blanks on
    the shorter one's rows; they are outside the walls and never driven.
    """
    shared = _streetcode_combine([_streetcode_shared(n), tree])
    return "\n".join(row.rstrip() for row in shared)


def _streetcode_narrow(flat: str, width: int) -> str:
    """Turn the indexed street clockwise: nine columns, or seven with a shared kerb."""
    return _streetcode_quarter_turn(
        _streetcode_shared_kerb(flat) if width < _SILL + 1 else flat
    )


_WALLS = frozenset("-|+")

# Blank rows between two blocks (a strip with its room band), and clear
# columns each side of a cut.  A car reads walls three cells to a side
# (:func:`_road_mouth`, :func:`_plus_dist`), and a lane's nearest outer wall
# is one or two cells out, so two blank rows put every other block's wall at
# least four rows from any road cell.  Four columns put a room's wall at least
# four from the end column, hence beyond what a bend's road cells can read.
_GAP = 2
_MARGIN = 4


def _streetcode_cuts(rows: list[str]) -> list[bool]:
    """Return where the indexed street may be cut: plain road, no room near."""
    span = len(rows[0])
    clear = [
        all(row[col] == " " for row in rows[:_KERB])
        and rows[_KERB][col] == rows[_SILL][col] == "-"
        for col in range(span)
    ]
    return [
        _MARGIN <= col <= span - _MARGIN and all(clear[col - _MARGIN : col + _MARGIN])
        for col in range(span)
    ]


def _streetcode_bounds(rows: list[str], target: int, *, east: bool) -> list[int]:
    """Return strip bounds: legal cuts at most ``target`` apart where possible.

    Cutting from the east packs the rooms, which all lie there, into the
    fewest strips (each adds a band); from the west, the fill does.
    """
    span = len(rows[0])
    legal = _streetcode_cuts(rows)

    def cuts(cols: range) -> Iterator[int]:
        return (col for col in cols if legal[span - col if east else col])

    bounds = [0]
    while span - bounds[-1] > target:
        start = bounds[-1]
        within = list(cuts(range(start + 4, start + target + 1)))
        beyond = cuts(range(start + target + 1, span))
        # A cut always remains in range: columns 5 and ``span - 5`` are
        # legal cuts at the street's plain ends, and every caller passes
        # ``target >= 8``, so this pass starts at most ``span - 9`` and
        # the far end's cut lies in the searched range either direction.
        cut = within[-1] if within else next(beyond)
        bounds.append(cut)
    bounds.append(span)
    return [span - bound for bound in reversed(bounds)] if east else bounds


def _streetcode_fold(
    flat: str, target: int, *, east: bool
) -> tuple[str, dict[tuple[int, int], tuple[int, int]]]:
    """Snake the indexed street into strips of at most ``target`` columns.

    Odd strips are turned a half turn, which keeps right-hand driving, and
    run back under the one before.  A block is a strip with its room band
    (rooms hang above an even strip's kerb, below an odd one's); blocks are
    stacked ``_GAP`` blank rows apart, each walled on its own.  A bend is a
    U of road two cells wide: an inner bar closing the gap between the two
    strips' inner walls, an outer wall from one outer wall to the other.
    Also returns each strip cell's flat cell; the bends have none.
    """
    rows = flat.splitlines()
    span = max(map(len, rows))
    rows = [row.ljust(span) for row in rows]
    bounds = _streetcode_bounds(rows, target, east=east)

    canvas: dict[tuple[int, int], str] = {}
    origin: dict[tuple[int, int], tuple[int, int]] = {}

    def put(row: int, col: int, char: str) -> None:
        # Walls that meet join through a corner.
        old = canvas.get((row, col))
        if old in _WALLS and char in _WALLS and old != char:
            char = "+"
        canvas[row, col] = char

    def column(col: int, top: int, bottom: int) -> None:
        put(top, col, "+")
        for row in range(top + 1, bottom):
            put(row, col, "|")
        put(bottom, col, "+")

    segments = [[row[a:b] for row in rows] for a, b in pairwise(bounds)]
    rooms = [any(row.strip() for row in segment[:_KERB]) for segment in segments]
    # Odd blocks are the flat turned over: row r is at 8 - r.
    top = 0
    start = 0  # the column the strip's first flat column lies on
    for i, segment in enumerate(segments):
        first = 0 if rooms[i] else _KERB
        height = _SILL - first + 1
        even = i % 2 == 0
        step = 1 if even else -1
        for row in range(first, _SILL + 1):
            at_row = top + row - first if even else top + _SILL - row
            for col, char in enumerate(segment[row]):
                at = at_row, start + step * col
                origin[at] = row, bounds[i] + col
                if char != " ":
                    put(*at, char)
        north = top + _KERB - first if even else top
        if i + 1 == len(segments):
            break
        # The far end of this strip is where the next one begins.
        far = start + step * (len(segment[0]) - 1)
        later = top + height + _GAP
        north_next = later if even else later + _KERB - (0 if rooms[i + 1] else _KERB)
        # Inner bar from this strip's south wall to the next one's north wall;
        # the outer wall from this north wall to the next one's south wall.
        column(far, north + 3, north_next)
        column(far + 3 * step, north, north_next + 3)
        for col in (far + step, far + 2 * step):
            put(north, col, "-")
            put(north_next + 3, col, "-")
        top, start = later, far
    ymin = min(row for row, _ in canvas)
    xmin = min(col for _, col in canvas)
    height = max(row for row, _ in canvas) - ymin + 1
    width = max(col for _, col in canvas) - xmin + 1
    grid = [[" "] * width for _ in range(height)]
    for (row, col), char in canvas.items():
        grid[row - ymin][col - xmin] = char
    program = "\n".join("".join(row).rstrip() for row in grid)
    return program, {(row - ymin, col - xmin): at for (row, col), at in origin.items()}


def _streetcode_folded(flat: str) -> str:
    """Return the indexed street folded to about square, east cuts first.

    A strip's block is ``_SILL - _KERB + 1 + _GAP`` rows plain, ``_SILL + 1 +
    _GAP`` with its room band.  East cuts pack the room columns into the
    fewest strips, so the share of strips with a band is the room columns'
    share of the span, and a strip averages ``h`` rows between those.  With
    ``span / target`` strips the height is ``span * h / target``; it squares
    the width when ``target = CELL_ASPECT * span * h / target``.
    """
    rows = flat.splitlines()
    span = grid_width(flat)
    west = min(
        (
            col
            for col in range(span)
            if any(row[col : col + 1].strip() for row in rows[:_KERB])
        ),
        default=span,
    )
    plain = _SILL - _KERB + 1 + _GAP
    # h = plain + _KERB * (span - west) / span, kept in integers.
    target = isqrt(CELL_ASPECT * (plain * span + _KERB * (span - west)))
    return _streetcode_fold(flat, target, east=True)[0]


# Arity from which the flat lookup is the canonical shape.  Random tables at
# n=5 are 38% smaller flat (599555 vs 961692 chars over 200), and 64% at n=6;
# the tree still wins tables that fold ([ablations.flat_tree_race]).
_FLAT_FROM = 6


def _smallest(*programs: str) -> str:
    """Return the smallest grid by area, then length; ties keep the earlier."""
    return min(programs, key=grid_rank)


def _tree_leaves(table: str) -> int:
    """Count the leaves :func:`_streetcode_tree` draws, four rows each."""
    half = len(table) // 2
    child = table[:half]
    if child == table[half:] and len(set(child)) == 2:
        return _tree_leaves(child)
    return sum(
        1 if len(set(part)) == 1 else _tree_leaves(part)
        for part in (child, table[half:])
    )


def _tree_may_win(truth_table: str, n: int, flat: str) -> bool:
    """Whether the tree's area floor (leaf rows by setup width) is below flat's."""
    setup = len(_streetcode_shared(n)[0])
    return 4 * _tree_leaves(truth_table) * (setup + 1) < grid_area(flat)


def _tree_shapes(truth_table: str, n: int, *, hallway: bool) -> list[str]:
    """Return the tree shapes, hallway first if asked, and the flat lookup.

    The flat lookup joins the race at the last tree arity and is canonical
    from ``_FLAT_FROM``, where the tree is drawn only if its area floor wins.
    """
    # The per-input loops trade rows for columns, so only width selection
    # needs them.  The shared lap is strictly shorter through every table at
    # n <= 3 and every sampled n == 4 table, while its fixed setup wins more
    # decisively as the input count grows.
    if n >= _FLAT_FROM:
        flat = _streetcode_flat(truth_table, n)
        if not _tree_may_win(truth_table, n, flat):
            return [flat]
    tree = _streetcode_tree(truth_table)
    programs = [_streetcode_hallway_program(n, tree)] if hallway else []
    programs.append(_streetcode_shared_program(n, tree))
    # At five the flat lookup wins on dense and parity tables and loses on
    # one that folds, so it is compared; without it parity at five costs
    # 3251 against 2534 and the odd rungs stop growing linearly.
    if n == _FLAT_FROM - 1:
        programs.append(_streetcode_flat(truth_table, n))
    if n >= _FLAT_FROM:
        programs.append(flat)
    return programs


def streetcode(truth_table: str, width: int | None = None) -> str:
    """Build a Streetcode program; the shortest shape wins.

    ``width`` chooses among the shapes rather than reflowing (rows are streets).
    """
    n = _validate_truth_table(truth_table)
    programs = _tree_shapes(truth_table, n, hallway=width is not None)
    if width is not None:
        fitting = [p for p in programs if grid_width(p) <= width]
        if fitting:
            return _smallest(*fitting)
        # The indexed street has nine rows at every arity; rotating it
        # makes those the width floor while preserving right-hand driving.
        return _streetcode_narrow(_streetcode_flat(truth_table, n), width)
    return _smallest(*programs)


def _balance(table: str, default: str) -> str:
    """Compare the default with the fold from six inputs, else also the tree fits.

    From six inputs the fold beat every other layout (default, the one- and
    nine-column fits, the indexed street and its half-turn) on every table
    measured; the free default stays so balance never scores worse than it.
    """
    n = _validate_truth_table(table)
    if n >= _FLAT_FROM:
        folded = _streetcode_folded(_streetcode_flat(table, n))
        return min([default, folded], key=balance_score)
    shapes = _tree_shapes(table, n, hallway=True)
    # A requested width changes the shortest fitting shape only when another
    # shape starts fitting; asking at that shape's span also excludes losers.
    candidates = [default, streetcode(table, 1), streetcode(table, 9)]
    candidates.extend(streetcode(table, grid_width(shape)) for shape in shapes)
    candidates.append(_streetcode_folded(_streetcode_flat(table, n)))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Streetcode",
    "streetcode",
    category="grid_based",
    layout_switch=(5, 6),
    slow_scaling=True,
    boolean=streetcode,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="Streetcode program cannot be empty",
    proof_execution=(execution, True, (6, 8)),
    proof_workspace=(workspace, False, (6, 7)),
    grid=True,
)
