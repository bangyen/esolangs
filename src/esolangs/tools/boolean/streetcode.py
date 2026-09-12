r"""Boolean-function generator for Streetcode."""

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
    r"""Lay ``arrs`` side by side, padding each to the tallest one's height."""
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
    r"""Build a counting loop that walks a cell by 48, eight laps of six."""
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
    r"""Build a wall-hugging loop of exactly 48 ``c`` cells, one per."""
    top = ["----", "    ", "    ", "+  +", "|  |"]
    row = f"|{c * 2}|"
    return [*top, *([row] * 24), "+--+"]


def _streetcode_strip(before: str, block: list[str]) -> list[str]:
    r"""Build a labeled loop room: ``before`` runs as instructions, then."""
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
    r"""Whether every leaf in a rendered subtree prints the same digit."""
    text = "".join(block)
    return text.count("~") == text.count("O") or text.count("~") == 0


def _streetcode_leaf(bit: int, skipped: int = 0) -> list[str]:
    r"""Build a leaf that prints ``bit``, reusing the loader loop's cell."""
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
    r"""Build the binary decision tree: one T-junction turn per input bit."""
    if len(table) > _TREE_CACHE_MAX:
        return _streetcode_tree_uncached(table)
    # Copied out: the cache hands.
    # ``_streetcode_combine`` and.
    # as read-only today, which is.
    return list(_streetcode_tree_memo(table))


@cache
def _streetcode_tree_memo(table: str) -> tuple[str, ...]:
    r"""Remember one small subtree's drawing; see :data:`_TREE_CACHE_MAX`."""
    return tuple(_streetcode_tree_uncached(table))


def _streetcode_tree_uncached(table: str) -> list[str]:
    r"""Build the binary decision tree: one T-junction turn per input bit."""
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
    r"""Run the leading instructions westbound along row 1 instead of row 2."""
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
    r"""Build the car's start plus ``n`` input loops and a final loader."""
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
    r"""Draw the shared lap, widened just enough to hold ``body``."""
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
    r"""Spell the CP walk from cell ``frm`` to cell ``to``."""
    return "=" * (to - frm) if to >= frm else "_" * (frm - to)


def _streetcode_cells(n: int, perm: tuple[int, ...]) -> list[int]:
    r"""Return the cell each stream input is read into, indexed by input."""
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level + 1
    return cells


def _streetcode_shared(n: int, perm: tuple[int, ...] | None = None) -> list[str]:
    r"""Build the populate phase as one shared 48-lap loop over every cell."""
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
    r"""Return the input orders to build the shared shape over, identity."""
    identity = tuple(range(n))
    if n <= _ORDER_SEARCH_MAX:
        return [identity, *(p for p in permutations(range(n)) if p != identity)]
    return [identity]


def _streetcode_columns(program: str) -> int:
    r"""Return the widest row of ``program``, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


def _streetcode_hallway_program(n: int, tree: list[str]) -> str:
    r"""Render the narrow per-input layout used for width selection."""
    return "\n".join(
        _streetcode_lift(
            _streetcode_combine([_streetcode_populate(n, _HALLWAY_SHAPE), tree])
        )
    )


def _streetcode_shared_programs(truth_table: str, n: int, tree: list[str]) -> list[str]:
    r"""Render the shared-lap layouts for every permitted input order."""
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
    r"""Build a Streetcode program computing the given truth table."""
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
