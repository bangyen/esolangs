"""Boolean-function generator for Streetcode.

Streetcode is a grid language whose programs are laid out as streets, so
the generator builds a decision tree from labelled loop strips
(:func:`_streetcode_strip`) and joins the per-level blocks side by side.

Each per-input strip walks one cell by 48, turning an ASCII digit into a
bare bit and a fresh cell into an ASCII digit. Its hallway loop spends the
48 as unary cells, two per row -- 29 rows tall but only 4 columns wide.

The shared-lap construction uses a product ring, mirrored from the text
generator so the counter sits above the value rather than below it.
"""

from collections.abc import Callable
from functools import cache
from itertools import permutations

from esolangs.tools.boolean.helpers import (
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    permute_truth_table,
)
from esolangs.tools.wrap import shortest

__all__ = ["streetcode"]


def _streetcode_combine(arrs: list[list[str]]) -> list[str]:
    """Lay ``arrs`` side by side, padding each to the tallest one's height."""
    top = max(len(arr) for arr in arrs)
    padded = [arr + [" " * len(arr[0])] * (top - len(arr)) for arr in arrs]
    return ["".join(arr[row] for arr in padded) for row in range(top)]


# The counting-loop ring,.
# ``tests/interpreters/test_stre.
# That one walks an accumulator.
# mirror -- counter above the.
# the value and needs CP left.
# .
# Block coordinates::.
# .
# 01234567.
# 0+ ++ +.
# 1| |.
# 2| ~ _|.
# 3| =++_ |.
# 4|^~++~U|.
# 5|^~~~~_|.
# 6|^^^^^ |.
# 7+------+.
# .
# Drive order: the entry ``^``.
# counting the counter up; the.
# North up the eastern lane and.
# climbs the western lane to.
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

# Entry cells in drive order:.
# The street cell above the.
# one fewer than the counter it.
_RING_ENTRY = [(4, 1), (5, 1), (6, 1)] + [(6, c) for c in range(2, 7)]

# The lap's value cells in.
# stop below the descent gap:.
# before the car climbs past.
# whatever cell CP names -- and.
# which would steer the car out.
_RING_LAP = [(4, 5), (5, 5)] + [(5, c) for c in range(4, 1, -1)] + [(4, 2)]

# 48 is what a collect loop.
# block's runs are long enough.
_RING_COUNTER = 8
_RING_PER_LAP = 6


def _streetcode_ring(c: str) -> list[str]:
    """Build a counting loop that walks a cell by 48, eight laps of six ``c``.

    The car counts the counter up to eight on the way in, U-turns onto the
    island, and laps it; each lap walks the value by six and takes one off
    the counter.  At the island's corner the roads run out through the gap
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

    Driving into the loop and back out crosses 48 ``c`` cells total (two per
    row), so it always adjusts a cell by 48 -- enough to walk an ASCII digit
    (``'0'`` = 48, ``'1'`` = 49) down to a bare 0/1, or a fresh 0 cell up to
    ASCII ``'0'``.

    Twenty-nine rows tall and four columns wide, so it remains available for
    width-constrained programs whose shared-lap layout is too wide.
    """
    top = ["----", "    ", "    ", "+  +", "|  |"]
    row = f"|{c * 2}|"
    return [*top, *([row] * 24), "+--+"]


def _streetcode_strip(before: str, block: list[str]) -> list[str]:
    """Build a labeled loop room: ``before`` runs as instructions, then ``block``.

    ``before`` is both the label text drawn above the room and the actual
    instructions the car drives over to reach it, so callers thread cell/CP
    bookkeeping through the label itself (see ``_streetcode_populate`` and
    the ``strip`` call in ``streetcode``).

    The label sits *beside* the loop, not above it: the whole label has to
    run before the car is level with the loop's mouth, since its trailing
    ``^`` is what the junction there reads.
    """
    width = len(before)
    wall = "-" * width
    first = [wall, " " * width, before, wall]
    return _streetcode_combine([first, block])


# ``~=I^`` leads into a collect.
# left on the cell behind,.
# the next bit (ASCII.
# forces the cell nonzero.
# ambiguous-turn rule (leftmost.
# second-leftmost) has to see a.
# than drive past it.
# The +1 it leaves behind is.
# cell; a bare 0 there would.
# of East onto the next loop.
_Shape = tuple[str, str, Callable[[str], list[str]]]

_HALLWAY_SHAPE: _Shape = ("~=I^", "~=^", _streetcode_hallway)


def _streetcode_constant(block: list[str]) -> bool:
    """Whether every leaf in a rendered subtree prints the same digit.

    Read off the drawing rather than the table, so the same test works at
    any depth: a leaf is ``~O;`` for a zero and ``` O;``` for a one, so a
    block is all-zeros when its ``~`` and ``O`` counts match and all-ones
    when it carries no ``~`` at all.
    """
    text = "".join(block)
    return text.count("~") == text.count("O") or text.count("~") == 0


def _streetcode_leaf(bit: int, skipped: int = 0) -> list[str]:
    r"""Build a leaf that prints ``bit``, reusing the loader loop's cell.

    The car arrives with CP already on the cell ``_streetcode_populate``'s
    closing loop ramped to ASCII ``'0'`` + 1 (one more than 48, from that
    loop's own forced-nonzero ``^``); ``~`` corrects it back down to plain
    ``'0'`` for a 0 leaf, or a no-op leaves it at ``'1'`` for a 1 leaf, and
    ``O`` prints whichever digit results.

    ``skipped`` is how many levels folded away above this leaf.  Every hall
    advances CP by one ``=`` on the way down, so a leaf reached without them
    has to spend those advances itself or it prints from the wrong cell --
    an all-zeros table came out as ``'\x00'`` before this was threaded
    through.
    """
    op = " " if bit else "~"
    body = "=" * skipped + f"{op}O;"
    return [
        "-" * len(body) + "+",
        " " * len(body) + "|",
        body + "|",
        "-" * len(body) + "+",
    ]


# Largest subtable whose.
# .
# The order search rebuilds the.
# it recurses on repeat: at n=6.
# two-row subtable but only 4.
# eight-row one against at most.
# count stops collapsing -- a.
# and the order of the rest, so.
# of the full table are -- so.
# 2160 copies of the whole.
# none of that memory: 276k.
# registry sweep measures 1.50s.
_TREE_CACHE_MAX = 2**4


def _streetcode_tree(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit."""
    if len(table) > _TREE_CACHE_MAX:
        return _streetcode_tree_uncached(table)
    # Copied out: the cache hands.
    # ``_streetcode_combine`` and.
    # as read-only today, which is.
    return list(_streetcode_tree_memo(table))


@cache
def _streetcode_tree_memo(table: str) -> tuple[str, ...]:
    """Remember one small subtree's drawing; see :data:`_TREE_CACHE_MAX`."""
    return tuple(_streetcode_tree_uncached(table))


def _streetcode_tree_uncached(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit.

    Recurses on halves of ``table``, joining the two subtrees with a hall
    that advances CP by one ``=`` and forks the car left/right onto the
    matching subtree -- the same leftmost/second-leftmost ambiguous-turn
    rule the loops use, now keyed on the bit ``_streetcode_populate`` left
    behind instead of a byte fresh off ``I``.

    A subtree whose rows all agree folds to a leaf rather than driving the
    car down halls to identical answers: a constant table is 428 characters
    against 1439 at three inputs.  The reads are unaffected --
    :func:`_streetcode_populate` makes them all before the tree -- so a
    folded program consumes its input exactly as an unfolded one does; only
    the ``=`` advances the skipped halls would have spent move into the
    leaf.  Constancy is read off the rendered block rather than the table:
    a block is constant when every leaf in it is a ``0`` leaf
    (``count("~") == count("O")``) or every leaf is a ``1`` leaf (no ``~``
    at all), which is the same test at any depth.

    Siblings are then padded to a common width, since the two are stacked
    and share one wall.
    """
    size = len(table)
    if size == 1:
        return _streetcode_leaf(int(table[0]))

    half = size // 2
    top = _streetcode_tree(table[:half])
    bot = _streetcode_tree(table[half:])
    if _streetcode_constant(top):
        top = _streetcode_leaf(int(table[0]), half.bit_length() - 1)
    if _streetcode_constant(bot):
        bot = _streetcode_leaf(int(table[half]), half.bit_length() - 1)
    width = max(max(len(row) for row in top), max(len(row) for row in bot))
    top = [row.ljust(width) for row in top]
    bot = [row.ljust(width) for row in bot]
    height = len(top)

    hall = []
    # The hall spans both children.
    # while siblings were always.
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
            # This used to test ``size ==.
            # meant the children are bare.
            # makes a four-row child at any.
            # was always really asking.
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

    Row 1 is the oncoming lane, blank across the whole program: the car only
    drives it coming back from the hairpin at the western wall.  Starting
    the car *there* costs nothing and frees the columns the leading run
    occupied at the head of the driving lane -- the ``C^`` start and the
    first loop's label, nine columns for the ring's labels and seven for the
    hallway's, off every row of the program.

    The run is written East-to-West, since a ``C`` with the northern wall on
    its right heads West: the car reads it in reverse, hairpins at the west
    wall, and arrives back along row 2 at the first loop's mouth exactly as
    it used to.

    The run's leading ``^`` is what makes this safe.  The westbound leg
    passes over every loop mouth in the program, and each is a junction
    reading the CPth cell; a zero there captures the car into the first
    mouth it meets.  The ``^`` the start already carried leaves cell 0
    nonzero for the whole leg, so every crossing passes straight over.
    """
    lane = rows[2]
    # The prefix runs from the.
    # belongs to loops the car only.
    start = lane.index("C")
    end = start
    while end < len(lane) and lane[end] != " ":
        end += 1

    width = max(len(row) for row in rows)
    grid = [list(row.ljust(width)) for row in rows]
    prefix = "".join(grid[2][start:end])
    # Drop the columns the prefix.
    kept = [c for c in range(width) if not (start <= c < end)]
    grid = [[row[c] for c in kept] for row in grid]

    # Write it into row 1 reversed,.
    # .
    # The wall is found rather than.
    # hanging below the street can.
    # ``width`` above is the widest.
    # table whose tree runs past.
    # column east of the street's.
    # outside the walls.
    # border above it, which the.
    # ``generate("Streetcode",.
    # two-input tables, at every.
    # the one selected.
    east = "".join(grid[0]).rindex("+") - 1
    for i, char in enumerate(prefix):
        grid[1][east - i] = char

    # With the label gone, the.
    # street's western wall, which.
    # the street's own, walling.
    # down.
    # drop the street's and let the.
    # taking one more column off.
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
    # The rewind strip walks CP.
    # so it carries n '_'.
    # a single '_' would draw a.
    # pad the label out to the.
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


# The shared lap's ring,.
# fixed -- the ``=`` hop below.
# top row, and the ``_`` that.
# CP on the way out -- because.
# describe.
# lap is deliberately blank:.
# CP on the counter, so the.
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


def _streetcode_walk(frm: int, to: int) -> str:
    """Spell the CP walk from cell ``frm`` to cell ``to``.

    ``=`` moves CP right and ``_`` left, so a walk is just the gap spelled
    in whichever of the two the direction calls for.
    """
    return "=" * (to - frm) if to >= frm else "_" * (frm - to)


def _streetcode_cells(n: int, perm: tuple[int, ...]) -> list[int]:
    """Return the cell each stream input is read into, indexed by input.

    The tree tests cells *positionally* -- every hall spends one ``=``, so
    level ``k`` tests cell ``k + 1`` -- which is what makes the reorder a
    placement rather than layout surgery.  Level ``k`` has to test original
    input ``perm[k]``, so that input is the one stored at cell ``k + 1``.

    The result is therefore the *inverse* of ``perm``, shifted by the one
    cell the rewind leaves CP on.  Reading it in the forward direction
    stores the right bits in the wrong cells and every non-identity order
    computes a different function -- the frame mix-up
    :func:`~esolangs.tools.boolean.helpers.stored_inputs` warns about.
    """
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level + 1
    return cells


def _streetcode_shared(n: int, perm: tuple[int, ...] | None = None) -> list[str]:
    """Build the populate phase as one shared 48-lap loop over every cell.

    The per-input hallway spends a whole 48-cell loop on each input and another
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
    That seed is required.

    The trailing ``_`` then walk CP back to cell 1.  There is nothing to
    correct on the way: with no ``^`` after the reads the ring subtracts 48
    from 48 or 49, so the inputs are already the bare bits the tree wants.

    ``perm`` reorders which cell each input is read into, so the tree's
    fixed positional tests fall on the inputs in ``perm`` order (see
    :func:`_streetcode_cells`).  Only the prefix changes: instead of
    stepping one cell per read it walks to each input's target, so a swap
    at two inputs reads ``==I_I`` where the identity reads ``=I=I``.  The
    reads stay in stream order -- ``I`` fires once per input, left to
    right, exactly as before -- and everything downstream is untouched,
    because the lap and the rewind are position-based over cells 1..n and
    do not care which input sits where.

    Two things keep a permuted prefix as safe as the identity one.  The
    walks are junction-free: they run down the shaft, not along the street,
    so no mouth is crossed while CP names an arbitrary cell.  And the fixed
    seeding suffix is *relative* to cell ``n`` -- it seeds the loader at
    ``n + 1`` and the counter above it -- so the prefix walks CP back to
    cell ``n`` after the last read rather than assuming it landed there.
    """
    perm = tuple(range(n)) if perm is None else perm
    body = "_" * (n + 1) + "~=" * n + "^"
    # No ``^`` after the reads:.
    # 48 or 49, so a cell it has.
    # no bump to satisfy the.
    # exactly 48 and the inputs.
    # walk CP back -- there is no.
    cells = _streetcode_cells(n, perm)
    reads = ""
    at = 0
    for cell in cells:
        reads += _streetcode_walk(at, cell) + "I"
        at = cell
    # Back to cell ``n``, which the.
    # the identity order the last.
    # empty, so the prefix is.
    prefix = "C" + reads + _streetcode_walk(at, n) + "=^" + "=" + "=^"
    tail = "_" * n
    blocks = [_streetcode_ring("^"), _streetcode_shared_lap(body)]

    # The prefix runs down a shaft.
    # drives the western lane.
    # 2n+6 instructions cost four.
    # is drawn bottom-up, since.
    down, up = prefix[: len(prefix) // 2], prefix[len(prefix) // 2 :]
    depth = max(len(down), len(up))
    down = down.ljust(depth)
    up = up.ljust(depth)

    # The street is left open at.
    # by.
    # the strip shapes' populate.
    head = 4  # the shaft's western wall, its.
    width = head + sum(len(b[0]) for b in blocks) + len(tail)
    height = max(3 + max(len(b) for b in blocks), 5 + depth)
    grid = [[" "] * width for _ in range(height)]
    grid[0] = list("+" + "-" * (width - 1))
    for r in (1, 2):
        grid[r][0] = "|"
    grid[3] = list("+" + "-" * (width - 1))
    # Cut the shaft's mouth into.
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


def _streetcode_orders(n: int) -> list[tuple[int, ...]]:
    """Return the input orders to build the shared shape over, identity first.

    Streetcode cannot go through
    :func:`~esolangs.tools.boolean.helpers.best_input_order` the way the
    token-sequence generators do, because that returns one shortest string
    and this generator's ``width`` has to choose among *every* candidate --
    the shapes differ in aspect, so the narrowest program is often not the
    shortest one.  The orders are enumerated here instead and the existing
    selection runs over the whole pool, which is the ``six_five`` and
    ``forth`` precedent.

    The cap is shared with ``best_input_order`` rather than reinvented:
    above it the exhaustive search is ``n!`` builds of an ``O(2**n)``
    drawing, the cost that does not announce itself.  Past the cap this
    returns the identity alone rather than ``best_input_order``'s greedy
    order -- a Streetcode program is a *drawing*, so the greedy score (how
    many subtrees a split leaves constant) misses the per-order cost that
    actually decides the winner here, the walk the prefix spends putting
    each bit in its cell.  A table that big is outside what the suite
    exercises; wiring the greedy path in unmeasured would be guessing at its
    own benchmark.
    """
    identity = tuple(range(n))
    if n <= _ORDER_SEARCH_MAX:
        return [identity, *(p for p in permutations(range(n)) if p != identity)]
    return [identity]


def _streetcode_columns(program: str) -> int:
    """Return the widest row of ``program``, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _streetcode_hallway_program(n: int, tree: list[str]) -> str:
    """Render the narrow per-input layout used for width selection."""
    return "\n".join(
        _streetcode_lift(
            _streetcode_combine([_streetcode_populate(n, _HALLWAY_SHAPE), tree])
        )
    )


def _streetcode_shared_programs(truth_table: str, n: int, tree: list[str]) -> list[str]:
    """Render the shared-lap layouts for every permitted input order."""
    identity = tuple(range(n))
    programs = []
    for perm in _streetcode_orders(n):
        shared = _streetcode_combine(
            [
                _streetcode_shared(n, perm),
                tree
                if perm == identity
                else _streetcode_tree(permute_truth_table(truth_table, perm)),
            ],
        )
        # Padding siblings to a common.
        # shorter one's rows; they are.
        programs.append("\n".join(row.rstrip() for row in shared))
    return programs


def streetcode(truth_table: str, width: int | None = None) -> str:
    """Build a Streetcode program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The car reads each input bit through a wall-hugging loop that walks its
    ASCII value down to a bare 0/1 (built by :func:`_streetcode_populate`
    out of :func:`_streetcode_strip` rooms), then drives into a binary
    decision tree (:func:`_streetcode_tree`) whose T-junctions apply
    Streetcode's ambiguous-turn rule -- leftmost when the CPth cell is 0,
    otherwise second-leftmost -- to fork on each bit in turn.  A final
    loader loop (folded into :func:`_streetcode_populate`) ramps a fresh
    cell up to ASCII ``'0'`` before the tree, so every leaf prints the
    table's digit directly rather than building its own ramp.

    Whichever shape wins, the leading run then moves to the oncoming lane
    and runs westbound (:func:`_streetcode_lift`), which takes its columns
    off every row of the program.

    The tree also splits on its inputs in whichever order emits the
    shortest program, so more subtrees fold.  That is a *placement* here
    rather than layout surgery: the halls test cells positionally, so
    moving which cell an input is read into is enough to change what every
    junction tests, and only the shared shape's prefix changes (see
    :func:`_streetcode_shared`).  The reads stay in stream order.  The
    hallway is built only when a width is requested: its narrower geometry
    can meet a bound the shared layout cannot. Its labels thread the ``+1``
    hand-off between neighbouring loops in a way a permuted placement would
    have to re-derive for no measured gain.

    ``width`` bounds the columns by *choosing among the shapes* rather than
    reflowing the winner: a Streetcode program's rows are streets, so no
    after-the-fact fold can narrow one.  The shapes already differ in aspect
    -- the hallway trades columns for rows -- so a width the shortest shape
    overruns is often met by another that was built anyway. The narrowest
    shape wins when none
    fits, since a width is a preference about layout and returning nothing
    would be worse than returning the best available; the generator has no
    shape narrower than its tree.
    """
    n = _validate_truth_table(truth_table)
    tree = _streetcode_tree(truth_table)
    # The per-input loops trade.
    # needs them.
    # n <= 3 and every sampled n ==.
    # decisively as the input count.
    programs = [_streetcode_hallway_program(n, tree)] if width is not None else []
    # The shared shape is not.
    # three more cells, which makes.
    # westbound run of it crosses.
    # names a cell that nothing has.
    # code that has run.
    # walks over are exactly the.
    # .
    # It is built once per input.
    # no reorder improves keeps the.
    # settled by.
    # argument.
    programs.extend(_streetcode_shared_programs(truth_table, n, tree))
    if width is not None:
        fitting = [p for p in programs if _streetcode_columns(p) <= width]
        if fitting:
            return shortest(*fitting)
        # Nothing fits: fall back to.
        return min(programs, key=_streetcode_columns)
    return shortest(*programs)
