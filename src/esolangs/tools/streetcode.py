"""Boolean-function generator for Streetcode.

A decision tree from labelled loop strips (:func:`_streetcode_strip`),
per-level blocks joined side by side.  Each per-input strip walks a cell
by 48 (an ASCII digit to a bit, a fresh cell to a digit); its hallway
loop spends the 48 as unary cells, 29 rows by 4 columns.  The shared-lap
construction uses a product ring mirrored from the text generator.
"""

from collections.abc import Callable
from functools import cache

from esolangs.tools.helpers import (
    _greedy_input_order,
    _validate_truth_table,
    constant_span_test,
    permute_truth_table,
)
from esolangs.tools.wrap import shortest

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
    room; it sits beside the loop, since its trailing ``^`` is what the
    junction at the mouth reads.
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
_Shape = tuple[str, str, Callable[[str], list[str]]]

_HALLWAY_SHAPE: _Shape = ("~=I^", "~=^", _streetcode_hallway)


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
    """Remember one small subtree's drawing; see :data:`_TREE_CACHE_MAX`."""
    return tuple(_streetcode_tree_uncached(table))


def _streetcode_tree_uncached(table: str) -> list[str]:
    """Build the binary decision tree: one T-junction turn per input bit.

    Halves are joined by a hall that advances CP one ``=`` and forks on the
    bit.  A constant subtree folds to a leaf (428 chars vs 1439 at three
    inputs); the reads happen before the tree, so a folded program consumes
    its input unchanged.  Siblings are padded to a common width.
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
    return _streetcode_join(top, bot)


def _streetcode_join(top: list[str], bot: list[str]) -> list[str]:
    """Join two finished subtrees with their shared branching hall."""
    width = max(max(len(row) for row in top), max(len(row) for row in bot))
    top = [row.ljust(width) for row in top]
    bot = [row.ljust(width) for row in bot]
    height = len(top)

    hall = []
    # The hall spans both children.  ``height * 2`` said the same thing
    # while siblings were always the same height, which folding ends.
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
            # This used to test ``size == 2``, which in an unfolded tree
            # meant the children are bare leaves -- four rows tall.  A fold
            # makes a four-row child at any size, so the height is what it
            # was always really asking about.
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

    # Write it into row 1 reversed, ending against the eastern wall.
    #
    # The wall is found rather than assumed to be the last column.  A block
    # hanging below the street can be wider than the street itself, and
    # ``width`` above is the widest row of the *whole* grid -- so for a
    # table whose tree runs past its street, ``len(grid[0]) - 2`` named a
    # column east of the street's own ``+`` and the prefix was written
    # outside the walls.  The result was a row two columns longer than the
    # border above it, which the interpreter rejects as not two-wide.
    # ``generate("Streetcode", "0001", 20)`` was one: four of the sixteen
    # two-input tables, at every width up to 35, where the narrow shape is
    # the one selected.
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


def _streetcode_populate(n: int, shape: _Shape) -> list[str]:
    """Build the car's start plus ``n`` input loops and a final loader loop.

    The loader is an input loop without ``I``; its label's ``^`` forces the
    turn and ramps a fresh cell to ``'0'`` + 1 (:func:`_streetcode_leaf`).
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
    """Spell the CP walk from cell ``frm`` to cell ``to`` (``=`` right, ``_`` left)."""
    return "=" * (to - frm) if to >= frm else "_" * (frm - to)


def _streetcode_cells(n: int, perm: tuple[int, ...]) -> list[int]:
    """Return the cell each stream input is read into, indexed by input.

    Level ``k`` tests cell ``k + 1``, so input ``perm[k]`` goes there: the
    inverse of ``perm``, shifted one.  Read forward, every non-identity order
    computes a different function.
    """
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level + 1
    return cells


def _streetcode_shared(n: int, perm: tuple[int, ...] | None = None) -> list[str]:
    """Build the populate phase as one shared 48-lap loop over every cell.

    One counter holding 48 and one lap walking every cell -- inputs down,
    loader up, counter down -- so the loop's cost stops scaling with ``n``.
    Cells: inputs at 1..n, loader n+1, counter n+2, ring cell n+3.  Inputs
    reach zero mid-run, but CP is only on an input along junction-free legs;
    both junctions read the counter, and the drop out lands on the loader,
    seeded to 1 (required).  The trailing ``_`` walk CP back to cell 1.
    ``perm`` changes only the prefix (``==I_I`` vs ``=I=I``); reads stay in
    stream order, and the walks are down the shaft, crossing no mouth.  The
    seeding suffix is relative to cell ``n``.
    """
    perm = tuple(range(n)) if perm is None else perm
    body = "_" * (n + 1) + "~=" * n + "^"
    # No ``^`` after the reads: ``I`` stores the code point of an ASCII digit,
    # 48 or 49, so a cell it has just filled is nonzero on its own and needs
    # no bump to satisfy the mouths' junctions.  The ring then subtracts
    # exactly 48 and the inputs land on bare bits, so the tail only has to
    # walk CP back -- there is no +1 for it to take off.
    cells = _streetcode_cells(n, perm)
    reads = ""
    at = 0
    for cell in cells:
        reads += _streetcode_walk(at, cell) + "I"
        at = cell
    # Back to cell ``n``, which the seeding suffix below counts from.  Under
    # the identity order the last read already left CP there and the walk is
    # empty, so the prefix is spelled exactly as it was.
    prefix = "C" + reads + _streetcode_walk(at, n) + "=^" + "=" + "=^"
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


def _streetcode_orders(truth_table: str, n: int) -> list[tuple[int, ...]]:
    """Return the identity and greedy input orders, identity first.

    Not through :func:`~esolangs.tools.helpers.best_input_order`: ``width``
    chooses among every candidate, since the narrowest is often not the
    shortest.  Both are kept and the rendered layouts decide.
    """
    identity = tuple(range(n))
    greedy = _greedy_input_order(truth_table, n)
    return [identity] if greedy == identity else [identity, greedy]


def _streetcode_columns(program: str) -> int:
    """Return the widest row of ``program``, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _streetcode_rotate(program: str) -> str:
    """Rotate a Streetcode grid 180 degrees and trim its new line ends.

    Rotation preserves right-hand driving; a reflection would not.
    """
    rows = program.splitlines()
    width = max(map(len, rows))
    return "\n".join(row.ljust(width)[::-1].rstrip() for row in reversed(rows))


_H_DIR = {"E": (0, 1), "S": (1, 0), "W": (0, -1), "N": (-1, 0)}
_H_LEFT = {"E": "N", "N": "W", "W": "S", "S": "E"}
_H_RIGHT = {value: key for key, value in _H_LEFT.items()}


def _streetcode_h_rect(r0: int, r1: int, c0: int, c1: int) -> set[tuple[int, int]]:
    """Return the cells in one half-open rectangle."""
    return {(r, c) for r in range(r0, r1) for c in range(c0, c1)}


def _streetcode_h_corridor(
    one: tuple[int, int], two: tuple[int, int]
) -> set[tuple[int, int]]:
    """Return a two-cell-wide axis-aligned corridor between two anchors."""
    r0, c0 = one
    r1, c1 = two
    if r0 == r1:
        return _streetcode_h_rect(r0, r0 + 2, min(c0, c1), max(c0, c1) + 2)
    if c0 != c1:  # pragma: no cover - the H layout changes one axis per edge
        raise AssertionError("an H-tree corridor must be axis-aligned")
    return _streetcode_h_rect(min(r0, r1), max(r0, r1) + 2, c0, c0 + 2)


def _streetcode_h_lane(anchor: tuple[int, int], direction: str) -> tuple[int, int]:
    """Return the right-hand lane cell at a two-by-two junction."""
    r, c = anchor
    return {"E": (r + 1, c), "S": (r, c), "W": (r, c + 1), "N": (r + 1, c + 1)}[
        direction
    ]


def _streetcode_h_render(
    open_cells: set[tuple[int, int]],
    glyphs: dict[tuple[int, int], str],
    fixed_walls: dict[tuple[int, int], str],
) -> str:
    """Render a two-wide road union, retaining the normalizer's inner walls."""
    border = {
        (r + dr, c + dc)
        for r, c in open_cells
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (r + dr, c + dc) not in open_cells
    }
    cells = open_cells | border | fixed_walls.keys()
    lo_r = min(r for r, _ in cells)
    lo_c = min(c for _, c in cells)
    hi_r = max(r for r, _ in cells)
    hi_c = max(c for _, c in cells)
    rows: list[str] = []
    for r in range(lo_r, hi_r + 1):
        row: list[str] = []
        for c in range(lo_c, hi_c + 1):
            pos = (r, c)
            if pos in fixed_walls:
                row.append(fixed_walls[pos])
            elif pos in open_cells:
                row.append(glyphs.get(pos, " "))
            elif pos not in border:
                row.append(" ")
            else:
                vertical = (r - 1, c) in open_cells or (r + 1, c) in open_cells
                horizontal = (r, c - 1) in open_cells or (r, c + 1) in open_cells
                row.append("+" if vertical == horizontal else "-" if vertical else "|")
        rows.append("".join(row).rstrip())
    return "\n".join(rows)


def _streetcode_h_layout(
    truth_table: str, n: int
) -> tuple[set[tuple[int, int]], dict[tuple[int, int], str]]:
    """Return an alternating-axis decision tree whose rectangle is O(T)."""
    cells: set[tuple[int, int]] = set()
    glyphs: dict[tuple[int, int], str] = {}
    # The western radius is smaller than this geometric bound.  Keeping the
    # tree east of column zero leaves the input normalizer a private region.
    root = (0, 32 * (1 << (n // 2)))
    cells |= _streetcode_h_corridor((0, 0), root)

    def descend(prefix: str, anchor: tuple[int, int], direction: str) -> None:
        remaining = n - len(prefix)
        if not remaining:
            dr, dc = _H_DIR[direction]
            end = (anchor[0] + 7 * dr, anchor[1] + 7 * dc)
            cells.update(_streetcode_h_corridor(anchor, end))
            at = _streetcode_h_lane(anchor, direction)
            commands = (
                "~" if truth_table[int(prefix, 2)] == "0" else " ",
                "O",
                ";",
            )
            for step, char in enumerate(commands, 2):
                glyphs[(at[0] + step * dr, at[1] + step * dc)] = char
            return

        distance = 16 * (1 << ((remaining - 1) // 2))
        for bit, branch in (("0", _H_LEFT[direction]), ("1", _H_RIGHT[direction])):
            br, bc = _H_DIR[branch]
            child = (anchor[0] + distance * br, anchor[1] + distance * bc)
            cells.update(_streetcode_h_corridor(anchor, child))
            # A junction tests the current input.  Both exits advance CP to
            # the next input (or the prepared output cell) before the child.
            at = _streetcode_h_lane(anchor, branch)
            glyphs[(at[0] + 2 * br, at[1] + 2 * bc)] = "="
            descend(prefix + bit, child, branch)

    descend("", root, "E")
    return cells, glyphs


def _streetcode_h_program(truth_table: str, n: int) -> str:
    """Attach the shared input normalizer to the linear-area H-tree."""
    cells, glyphs = _streetcode_h_layout(truth_table, n)
    rows = _streetcode_shared(n)
    width = max(map(len, rows))
    padded = [row.ljust(width) for row in rows]
    normalizer_open: set[tuple[int, int]] = set()
    for r, row in enumerate(padded):
        walls = [c for c, char in enumerate(row) if char in "+-|"]
        if not walls:
            continue
        # Rows 1 and 2 are the two open-ended street lanes.  Every other row
        # is bounded by its first and last wall; inner walls remain fixed
        # below, so including an island's blank interior cannot join a road.
        stop = width if r in (1, 2) else walls[-1]
        normalizer_open.update(
            (r, c) for c in range(walls[0] + 1, stop) if row[c] not in "+-|"
        )

    # Row 2 is the normalizer's eastbound driving lane; join its open end to
    # row 1 of the H-tree's incoming road.
    east = max(c for r, c in normalizer_open if r == 2)
    shift = (-1, -east)
    fixed_walls = {
        (r + shift[0], c + shift[1]): char
        for r, row in enumerate(padded)
        for c, char in enumerate(row)
        if char in "+-|"
    }
    for r, c in normalizer_open:
        pos = (r + shift[0], c + shift[1])
        cells.add(pos)
        char = padded[r][c]
        if char != " ":
            glyphs[pos] = char
    return _streetcode_h_render(cells, glyphs, fixed_walls)


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
    for perm in _streetcode_orders(truth_table, n):
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


def streetcode(truth_table: str, width: int | None = None) -> str:
    """Build a Streetcode program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  At six
    inputs and above the tree is an alternating-axis H-tree (both dimensions
    O(sqrt(T)), source O(T)); smaller tables stack.  Each input is read
    through a loop walking its ASCII value down to a bit
    (:func:`_streetcode_populate`), then a tree (:func:`_streetcode_tree`)
    whose T-junctions apply the ambiguous-turn rule; a loader loop ramps a
    cell to ``'0'`` so every leaf prints directly.  The leading run then
    moves to the oncoming lane (:func:`_streetcode_lift`).  The compact shape
    is also compared with its 180-degree rotation, and the tree splits in
    whichever input order is shortest -- a placement, since halls test cells
    positionally (:func:`_streetcode_shared`); the hallway is built only
    when a width is requested.  ``width`` chooses among the shapes rather
    than reflowing (rows are streets); the narrowest wins when none fits.
    """
    n = _validate_truth_table(truth_table)
    if n >= 6:
        program = _streetcode_h_program(truth_table, n)
        h_rotated = _streetcode_rotate(program)
        if width is None:
            return shortest(program, h_rotated)
        fitting = [p for p in (program, h_rotated) if _streetcode_columns(p) <= width]
        return (
            shortest(*fitting)
            if fitting
            else min((program, h_rotated), key=_streetcode_columns)
        )
    tree = _streetcode_tree(truth_table)
    # The per-input loops trade rows for columns, so only width selection
    # needs them.  The shared lap is strictly shorter through every table at
    # n <= 3 and every sampled n == 4 table, while its fixed setup wins more
    # decisively as the input count grows.
    programs = [_streetcode_hallway_program(n, tree)] if width is not None else []
    # The shared shape is not lifted.  Its prefix reads every input and seeds
    # three more cells, which makes it as long as the street it heads, so a
    # westbound run of it crosses the loops' own mouths -- and at each one CP
    # names a cell that nothing has seeded yet, because the prefix is the only
    # code that has run.  No ordering of the seeds avoids that: the cells CP
    # walks over are exactly the ones the prefix has not reached.
    #
    # It is built once per input order.  The identity comes first, so a table
    # no reorder improves keeps the program it already emitted -- ties are
    # settled by :func:`~esolangs.tools.wrap.shortest`, which keeps its first
    # argument.
    programs.extend(_streetcode_shared_programs(truth_table, n, tree))
    if width is not None:
        fitting = [p for p in programs if _streetcode_columns(p) <= width]
        if fitting:
            return shortest(*fitting)
        # Nothing fits: fall back to the narrowest rather than the shortest.
        return min(programs, key=_streetcode_columns)
    rotated = [_streetcode_rotate(program) for program in programs]
    return shortest(*programs, *rotated)
