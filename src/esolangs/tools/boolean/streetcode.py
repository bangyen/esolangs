"""Boolean-function generator for Streetcode.

Streetcode is a grid language whose programs are laid out as streets, so
the generator builds a decision tree from labelled loop strips
(:func:`_streetcode_strip`) and joins the per-level blocks side by side.

Each strip walks one cell by 48, which is what turns an ASCII digit into a
bare bit and a fresh cell into an ASCII digit.  There are two shapes for
that walk and the generator builds both, keeping the shorter program:

* :func:`_streetcode_hallway` spends the 48 as unary cells, two per row --
  29 rows tall but only 4 columns wide.
* :func:`_streetcode_ring` makes it a product instead, lapping an island
  eight times under the control of a counter and walking the value six per
  lap -- 8 rows, but 8 columns.

The ring is the same counting loop the text generator uses, mirrored so the
counter sits above the value rather than below it.
"""

from collections.abc import Callable

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["streetcode"]


def _streetcode_combine(arrs: list[list[str]]) -> list[str]:
    """Lay ``arrs`` side by side, padding each to the tallest one's height."""
    top = max(len(arr) for arr in arrs)
    padded = [arr + [" " * len(arr[0])] * (top - len(arr)) for arr in arrs]
    return ["".join(arr[row] for arr in padded) for row in range(top)]


# The counting-loop ring, mirrored from the hand-written program in
# ``tests/interpreters/test_streetcode.py`` (``TestStreetcodeCountingLoop``).
# That one walks an accumulator held *above* its counter; this one is the
# mirror -- counter above the value -- because the generator's tree forks on
# the value and needs CP left on it, exactly where the old hallway left it.
#
# Block coordinates::
#
#      01234567
#     0+  ++  +
#     1|      |
#     2|   ~ _|
#     3| =++_ |
#     4|^~++~U|
#     5|^~~~~_|
#     6|^^^^^ |
#     7+------+
#
# Drive order: the entry ``^`` descend column 1 and run East along row 6,
# counting the counter up; the ``U`` turns onto the island and each lap runs
# North up the eastern lane and West along row 5 walking the value, then
# climbs the western lane to the top and back around to the corner.
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

    The car counts the counter up to eight on the way in, U-turns onto the
    island, and laps it; each lap walks the value by six and takes one off
    the counter.  At the island's corner the roads are out through the gap
    or on around the island, so the countdown steers the loop -- nonzero
    laps again, zero leaves -- and the car exits with CP back on the value.

    ``c`` is ``'~'`` for a collect loop, walking an ASCII digit (``'0'`` =
    48, ``'1'`` = 49) down to a bare 0/1, or ``'^'`` for the loader loop,
    ramping a fresh cell up towards ASCII ``'0'``.
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

    Driving into the loop and back out crosses 48 ``c`` cells total (two
    per row), so it always adjusts a cell by 48 -- enough to walk an ASCII
    digit (``'0'`` = 48, ``'1'`` = 49) down to a bare 0/1, or a fresh 0 cell
    up to ASCII ``'0'``.

    Twenty-nine rows tall and four columns wide, against the ring's eight
    and eight: which of the two is cheaper depends on the tree beside it,
    so :func:`streetcode` builds both programs and keeps the shorter.
    """
    top = ["----", "    ", "    ", "+  +", "|  |"]
    row = f"|{c * 2}|"
    return [*top, *([row] * 24), "+--+"]


def _streetcode_strip(before: str, block: list[str]) -> list[str]:
    """Build a labeled loop room: ``before`` runs as instructions, then ``block``.

    ``before`` is both the label text drawn above the room and the actual
    instructions the car drives over to reach it, so callers thread cell/CP
    bookkeeping through the label itself (see ``_streetcode_collect`` and
    the ``strip`` call in ``streetcode``).

    The label sits *beside* the loop, not above it: the whole label has to
    run before the car is level with the loop's mouth, because its trailing
    ``^`` is what the junction there reads.
    """
    width = len(before)
    wall = "-" * width
    first = [wall, " " * width, before, wall]
    return _streetcode_combine([first, block])


def _streetcode_ring_block(c: str) -> list[str]:
    """Draw the ring with the three street rows it hangs below.

    The hallway draws its own street rows; the ring's top row is already
    the street's southern wall, so it needs them added.  Row 0 is the
    street's northern wall and stays solid; rows 1 and 2 are the oncoming
    and driving lanes the car passes over the block on.
    """
    ring = _streetcode_ring(c)
    width = len(ring[0])
    return ["-" * width, " " * width, " " * width, *ring]


# The two loop shapes, as (collect label, loader label, block builder).  Both
# hand the tree the same thing -- a cell holding ``bit + 1`` -- so everything
# downstream of the loops is shared.
#
# ``~=I^`` leads into a collect loop: ``~`` consumes the +1 the previous loop
# left on the cell behind, ``=`` advances CP onto a fresh cell, ``I`` reads
# the next bit (ASCII ``'0'``/``'1'``), and ``^`` bumps it to 49 or 50, which
# forces the cell nonzero before the loop's junction is tested -- the
# ambiguous-turn rule (leftmost when the CPth cell is 0, otherwise
# second-leftmost) has to see a nonzero cell to turn into the loop rather
# than drive past it.  The loader label is the same without an ``I``.
#
# The ring's labels carry a further ``=^``, which steps CP one cell on and
# starts the ring's counter there.  That second ``^`` is the forced-nonzero
# the ring's descent gap needs, and the counter is the right cell to force
# because the value is a ``'0'`` half the time.  The counter drains to 0 and
# is overwritten by the next loop's own ``I``, so it costs no tape.
#
# The +1 both shapes leave behind is not slack.  Every gap crossing reads the
# CPth cell, the ring's exit gap included, and it reads the value the ring
# just walked; a bare 0 there would steer the car West back down the street
# instead of East onto the next loop.
_Shape = tuple[str, str, Callable[[str], list[str]]]

_HALLWAY_SHAPE: _Shape = ("~=I^", "~=^", _streetcode_hallway)
_RING_SHAPE: _Shape = ("~=I^=^", "~=^=^", _streetcode_ring_block)


def _streetcode_leaf(bit: int) -> list[str]:
    """Build a leaf that prints ``bit``, reusing the loader loop's cell.

    The car arrives with CP already on the cell ``_streetcode_populate``'s
    closing loop ramped to ASCII ``'0'`` + 1 (one more than 48, from that
    loop's own forced-nonzero ``^``); ``~`` corrects it back down to plain
    ``'0'`` for a 0 leaf, or a no-op leaves it at ``'1'`` for a 1 leaf, and
    ``O`` prints whichever digit results.  Both loop shapes leave the same
    49 here, so the leaf is shared.
    """
    op = " " if bit else "~"
    return ["---+", "   |", f"{op}O;|", "---+"]


def _streetcode_tree(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit.

    Recurses on halves of ``table``, joining the two subtrees with a hall
    that advances CP by one ``=`` and forks the car left/right onto the
    matching subtree -- the same leftmost/second-leftmost ambiguous-turn
    rule the loops use, now keyed on the bit ``_streetcode_collect`` left
    behind instead of a byte fresh off ``I``.
    """
    size = len(table)
    if size == 1:
        return _streetcode_leaf(int(table[0]))

    half = size // 2
    top = _streetcode_tree(table[:half])
    bot = _streetcode_tree(table[half:])
    height = len(top)

    hall = []
    for k in range(height * 2):
        if k == 0:
            row = "----"
        elif k == 1:
            row = "    "
        elif k == 2:
            row = "   ="
        elif k == 3:
            row = "+  +"
        elif k == 4:
            row = "|  +" if size == 2 else "|  |"
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

    Row 1 is the oncoming lane, and it is blank across the whole program:
    the car only drives it coming back from the hairpin at the western
    wall.  Starting the car *there* costs nothing and frees the columns the
    leading run occupied at the head of the driving lane -- the ``C^`` start
    and the first loop's label, nine columns for the ring's labels and seven
    for the hallway's, off every row of the program.

    The run is written East-to-West, since a ``C`` with the northern wall on
    its right heads West: the car reads it in reverse, hairpins at the west
    wall, and arrives back along row 2 at the first loop's mouth exactly as
    it used to.

    The run's leading ``^`` is what makes this safe.  The westbound leg
    passes over every loop mouth in the program, and each is a junction that
    reads the CPth cell; a zero there captures the car into the first mouth
    it meets.  The ``^`` the start already carried leaves cell 0 nonzero for
    the whole leg, so every crossing passes straight over.
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

    # Write it into row 1 reversed, ending against the eastern wall.
    east = len(grid[0]) - 2
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


def _streetcode_populate(n: int, shape: _Shape) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader loop is structurally identical to an input-reading loop but
    has no ``I`` of its own: its label's ``^`` supplies the forced-nonzero
    bump instead, so it always turns in and ramps a fresh cell up to ASCII
    ``'0'`` + 1 for the tree's leaves to print from (see
    :func:`_streetcode_leaf`).
    """
    collect_label, loader_label, block = shape
    start = ["+--", "|  ", "|C^", "+--"]
    col = _streetcode_strip(collect_label, block("~"))
    # The rewind strip walks CP back over the n cells the input loops filled,
    # so it carries n '_' instructions.  Streets are two characters wide, so
    # a single '_' would draw a one-wide room the car cannot legally drive:
    # pad the label out to the minimum width with spaces, which are no-ops.
    rewind = "_" * n
    rewind = rewind.ljust(2)
    width = len(rewind)
    return _streetcode_combine(
        [
            start,
            *([col] * n),
            _streetcode_strip(loader_label, block("^")),
            ["-" * width, " " * width, rewind, "-" * width],
        ],
    )


# The shared lap's ring, widened by ``k`` the way the text generator widens
# its own.  Only the steering assembly is fixed -- the ``=`` hop below the
# descent gap, the countdown ``~`` on the top row, and the ``_`` that drops
# CP on the way out -- because those sit on paths the linear body cannot
# describe.  The cell the single-loop ring used to drop CP on for the *next*
# lap is deliberately blank: the body's own rewind is sized for arriving with
# CP on the counter, so the continue path has to hand it the same CP the
# first entry does.
_SHARED_ROWS = (
    "+  +{dash}+  +",
    "|      {gap}|",
    "|   ~ {gap}_|",
    "| =++{plus}  |",
    "|  ++{plus} U|",
    "|     {gap} |",
    "|     {gap} |",
    "+------{dash}+",
)


def _streetcode_shared_lap(body: str) -> list[str]:
    """Draw the shared lap, widened just enough to hold ``body``.

    The lap's cells run from just after the ``U``: North up the eastern
    lane, West along the island's southern side, then one cell North.  They
    stop below the descent gap, where the fixed ``=`` hops CP onto the
    counter -- that gap is a junction and reads whatever cell CP names.
    """
    k = max(0, len(body) - 6)
    grid = [
        list(row.format(plus="+" * k, gap=" " * k, dash="-" * k))
        for row in _SHARED_ROWS
    ]
    cells = [(4, 5 + k), (5, 5 + k)] + [(5, c) for c in range(4 + k, 1, -1)] + [(4, 2)]
    for i, char in enumerate(body):
        r, c = cells[i]
        grid[r][c] = char
    return ["".join(row) for row in grid]


def _streetcode_shared(n: int) -> list[str]:
    """Build the populate phase as one shared 48-lap loop over every cell.

    The per-loop shapes spend a whole 48-cell loop on each input and another
    on the loader.  48 only has to be built once, though: with a counter
    holding it, a single lap that walks *every* cell -- each input down one,
    the loader up one, the counter down one -- does all of that work at
    once, and the loop's cost stops scaling with ``n``.

    Cells are the inputs at 1..n, the loader at n+1, the shared counter at
    n+2, and the counter ring's own second cell at n+3.  The prefix reads
    the inputs and seeds the loader to 1; the first block is the ordinary
    ring, pointed at the counter, which builds it to 48; the second is the
    shared lap.

    What keeps the run safe is the lap's CP schedule rather than the cells'
    values.  A ``'0'`` input walks 48 down to 0, so inputs do reach zero
    mid-run -- but CP is only ever on an input along the lap's junction-free
    legs.  The two junctions read cells chosen for the job: the descent gap
    and the exit corner both read the counter, and the drop on the way out
    lands CP on the loader, which is seeded to 1 and only climbs from there.
    That seed is load-bearing for exactly this reason.

    The trailing ``_`` then walk CP back to cell 1.  There is nothing to
    correct on the way: with no ``^`` after the reads the ring subtracts 48
    from 48 or 49, so the inputs are already the bare bits the tree wants.
    """
    body = "_" * (n + 1) + "~=" * n + "^"
    # No ``^`` after the reads: ``I`` stores the code point of an ASCII digit,
    # 48 or 49, so a cell it has just filled is nonzero on its own and needs
    # no bump to satisfy the mouths' junctions.  The ring then subtracts
    # exactly 48 and the inputs land on bare bits, so the tail only has to
    # walk CP back -- there is no +1 for it to take off.
    prefix = "C" + "=I" * n + "=^" + "=" + "=^"
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


def streetcode(truth_table: str) -> str:
    """Build a Streetcode program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The car reads each input bit through a wall-hugging loop that walks
    its ASCII value down to a bare 0/1 (:func:`_streetcode_collect`), then
    drives into a binary decision tree (:func:`_streetcode_tree`) whose
    T-junctions apply Streetcode's ambiguous-turn rule -- leftmost when the
    CPth cell is 0, otherwise second-leftmost -- to fork on each bit in
    turn.  A final loader loop (folded into :func:`_streetcode_populate`)
    ramps a fresh cell up to ASCII ``'0'`` before the tree, so every leaf
    can print the table's digit directly rather than building its own
    ramp.

    Whichever shape wins, the leading run then moves to the oncoming lane
    and runs westbound (:func:`_streetcode_lift`), which takes its columns
    off every row of the program.
    """
    n = _validate_truth_table(truth_table)
    tree = _streetcode_tree(truth_table)
    # Both shapes are built and the shorter one wins, rather than predicting
    # the winner from ``n``: the two layouts are what they cost.  The ring is
    # 8 rows to the hallway's 29 but 8 columns to its 4, so the ring wins
    # while the loops set the program's height (n <= 2) and the hallway wins
    # once the tree is taller than either and only the width still counts.
    programs = []
    for shape in (_RING_SHAPE, _HALLWAY_SHAPE):
        rows = _streetcode_combine([_streetcode_populate(n, shape), tree])
        programs.append("\n".join(_streetcode_lift(rows)))
    # The shared shape is not lifted.  Its prefix reads every input and seeds
    # three more cells, which makes it as long as the street it heads, so a
    # westbound run of it crosses the loops' own mouths -- and at each one CP
    # names a cell that nothing has seeded yet, because the prefix is the only
    # code that has run.  No ordering of the seeds avoids that: the cells CP
    # walks over are exactly the ones the prefix has not reached.
    shared = _streetcode_combine([_streetcode_shared(n), tree])
    programs.append("\n".join(shared))
    return min(programs, key=len)
