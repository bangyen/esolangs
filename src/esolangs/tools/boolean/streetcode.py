"""Boolean-function generator for Streetcode.

Streetcode is a grid language whose programs are laid out as hallways, so
the generator builds a decision tree from hallway strips
(:func:`_streetcode_hallway`, :func:`_streetcode_strip`) and joins the
per-level blocks side by side.
"""

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


def _streetcode_strip(before: str, c: str) -> list[str]:
    """Build a labeled loop room: ``before`` runs as instructions, then the loop.

    ``before`` is both the label text drawn above the room and the actual
    instructions the car drives over to reach it, so callers thread cell/CP
    bookkeeping through the label itself (see ``_streetcode_collect`` and
    the ``strip`` call in ``streetcode``).

    The label sits *beside* the ring, not above it: the whole label has to
    run before the car is level with the ring's descent gap, because its
    trailing ``^`` is what starts the counter the gap's junction reads.
    The ring's own top row is the street's southern wall, so the block is
    given three blank street rows above it and the two line up.
    """
    width = len(before)
    wall = "-" * width
    first = [wall, " " * width, before, wall]
    ring = _streetcode_ring(c)
    # Row 0 is the street's northern wall and has to stay solid; rows 1 and
    # 2 are the oncoming and driving lanes the car passes over the block on.
    street = ["-" * len(ring[0]), " " * len(ring[0]), " " * len(ring[0])]
    return _streetcode_combine([first, [*street, *ring]])


def _streetcode_collect() -> list[str]:
    """One input-reading loop: read a bit, then subtract 48 down to 0/1.

    ``~=I^=^`` leads into the loop: ``~`` consumes the +1 the previous
    loop left on the cell behind, ``=`` advances CP onto a fresh cell,
    ``I`` reads the next bit (ASCII ``'0'``/``'1'``), and ``^`` bumps it
    to 49 or 50.  Then ``=^`` steps CP one further onto the ring's counter
    and starts counting it up; that second ``^`` is the forced-nonzero the
    descent gap's junction needs, and the counter is the right cell to
    force because the value is a ``'0'`` half the time.

    The ring subtracts 48, so the cell comes out at ``bit + 1``.  That +1
    is not slack: surfacing through the ring's exit gap is a junction too,
    and it reads the value the ring just walked.  A bare 0 there would
    steer the car West back down the street instead of East onto the next
    loop, so the +1 keeps every gap crossing nonzero and the next label's
    leading ``~`` takes it off again.

    The drained counter sits one cell further along, where the next
    loop's own ``I`` lands and overwrites it.
    """
    return _streetcode_strip("~=I^=^", "~")


def _streetcode_leaf(bit: int) -> list[str]:
    """Build a leaf that prints ``bit``, reusing the loader loop's cell.

    The car arrives with CP already on the cell ``_streetcode_populate``'s
    closing loop ramped to ASCII ``'0'`` -- a plain 48, since the ring adds
    exactly what it is asked to and leaves no forced-nonzero bump behind.
    A 0 leaf is then a no-op, ``^`` walks a 1 leaf up to ``'1'``, and ``O``
    prints whichever digit results.
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


def _streetcode_populate(n: int) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader loop (``strip('==^', '^')``) is structurally identical to an
    input-reading loop but has no ``I`` of its own: the first ``=`` steps
    CP onto the fresh cell the loop will ramp, and ``=^`` steps onto the
    ring's counter and starts it, exactly as a collect label does.  The
    ring then adds 48, so the cell holds ASCII ``'0'`` for the tree's
    leaves to print from (see :func:`_streetcode_leaf`).
    """
    start = ["+--", "|  ", "|C^", "+--"]
    col = _streetcode_collect()
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
            _streetcode_strip("~=^=^", "^"),
            ["-" * width, " " * width, rewind, "-" * width],
        ],
    )


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
    """
    n = _validate_truth_table(truth_table)
    populated = _streetcode_populate(n)
    tree = _streetcode_tree(truth_table)
    return "\n".join(_streetcode_combine([populated, tree]))
