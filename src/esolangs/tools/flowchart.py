"""Boolean-function generator for Flowchart.

I/O is Boolfuck's: bytes, low bit first.  Each input is a ``'0'``/``'1'``
byte whose low bit is the value, so input ``k`` is read by eight ``/ /``
nodes -- the previous byte's seven high bits, then this byte's value bit,
which the switch tests.  The first input has no previous byte and the last
byte's high bits are never read: the interpreter has already consumed the
whole byte.  The answer is printed as R and then the seven high bits of
ASCII ``'0'`` (:data:`_ANSWER`), so the output byte is ``'0'`` or ``'1'``.

The default is a deque lookup, one pushed entry a row (a run of equal entries
sets the register once), so it has no subtrees to share.
"""

from collections import Counter
from itertools import pairwise

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_width,
    narrowest_grid,
    read_at,
    subtree_ids,
)
from esolangs.tools.wrap import balance_score

# Fewest table rows a subtree must span for the stacked layout to draw it once.
_SHARE_ROWS = 8

# Leaf column pitch: 5-cell ``(( ))`` plus 1 gutter.
_FLOWCHART_PITCH = 6

# Prints the register, then bits 1..7 of 0x30 low bit first, and halts.
_ANSWER = (
    "\\ \\",
    "{ ]",
    "\\ \\",
    "\\ \\",
    "\\ \\",
    "[ }",
    "\\ \\",
    "\\ \\",
    "{ ]",
    "\\ \\",
    "\\ \\",
    "(( ))",
)


def _set(bit: str) -> str:
    """Return the node that sets the register to ``bit``."""
    return "[ }" if bit == "1" else "{ ]"


def _paint(cells: dict[tuple[int, int], str], x: int, y: int, text: str) -> None:
    """Write ``text`` into ``cells`` along row ``y`` from column ``x``."""
    for i, char in enumerate(text):
        cells[(x + i, y)] = char


def _reads(level: int) -> int:
    """Return the ``/ /`` count that selects input ``level``'s value bit."""
    return 1 if level == 0 else 8


def _plan(truth_table: str) -> tuple[str, list[int], int]:
    """Return the essential-input table, the ``/ /`` count per switch, the tail.

    The tail is the ``/ /`` count owed after the last switch.  An ignored
    input is read, not branched on: its eight ``/ /`` join the next level's,
    or the tail.  A constant table keeps every level, folded.
    """
    n = len(truth_table).bit_length() - 1
    used = essential_inputs(truth_table, n)
    if not used:
        return truth_table, [_reads(level) for level in range(n)], 0
    costs = [8 * used[0] + 1] + [8 * (b - a) for a, b in pairwise(used)]
    return read_at(truth_table, used, n), costs, 8 * (n - 1 - used[-1])


def _answer_column(cells: dict[tuple[int, int], str], middle: int, y: int) -> None:
    """Paint :data:`_ANSWER` down column ``middle`` from row ``y``."""
    for text in _ANSWER:
        _paint(cells, middle - len(text) // 2, y, text)
        cells[(middle, y + 1)] = "│"
        y += 2
    del cells[(middle, y - 1)]


def _flowchart_cells(truth_table: str) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves first on a fixed pitch, switches collapsed upwards and centred
    between their entry columns with rails to both.  Rows: ``( )``, rail,
    then per level its reads and switch, each followed by a rail; each leaf
    sets the register and drops onto a westward bus to the shared answer.
    """
    cells: dict[tuple[int, int], str] = {}
    truth_table, costs, tail = _plan(truth_table)
    constant = constant_span_test(truth_table)
    n = len(costs)
    # top[d] is level d's first read row; top[n] is where the tail's reads
    # start and the leaves follow them.
    top = [2]
    for level in range(n):
        top.append(top[-1] + 2 * costs[level] + 2)
    leaf_top = top[n] + 2 * tail

    def read_rows(level: int) -> range:
        return range(top[level], top[level] + 2 * costs[level], 2)

    middles: list[int] = []

    def leaf(slot: int, bit: str) -> int:
        """Draw the leaf for ``bit`` in column slot ``slot``; return its middle."""
        middle = _FLOWCHART_PITCH * slot + 2
        _paint(cells, middle - 1, leaf_top, _set(bit))
        cells[(middle, leaf_top + 1)] = "│"
        middles.append(middle)
        return middle

    def switch(depth: int, west: int, east: int) -> int:
        """Join two subtrees at ``depth``; return the column it sits on."""
        switch_row = top[depth + 1] - 2
        middle = (west + east) // 2
        for y in read_rows(depth):
            _paint(cells, middle - 1, y, "/ /")
            cells[(middle, y + 1)] = "│"
        _paint(cells, middle - 1, switch_row, "< >")
        for x in range(west + 1, middle - 1):
            cells[(x, switch_row)] = "─"
        for x in range(middle + 2, east):
            cells[(x, switch_row)] = "─"
        cells[(west, switch_row)] = "┌"
        cells[(east, switch_row)] = "┐"
        cells[(west, switch_row + 1)] = "│"
        cells[(east, switch_row + 1)] = "│"
        return middle

    # Slots are handed out left to right as the walk reaches each leaf, so a
    # folded subtree takes one column band instead of the ``2**k`` its rows
    # would have filled -- the drawing narrows rather than leaving a gap.
    slots = [0]

    def walk(lo: int, hi: int, depth: int) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return its column."""
        if constant(lo, hi):
            # Constant: no branch below here can change the answer, so this
            # is a leaf.  Leaves all sit on the bottom row whatever their
            # depth, so the rail from the switch above covers the levels this
            # fold skipped: the rows are a fixed grid and only the branching
            # goes away.
            #
            # The *reads* those levels would have done do not go away.  A
            # program must consume its ``n`` inputs whatever the table says
            # -- the reads are the interface, and a folded run that skipped
            # them left the caller's remaining bits on the stream -- so each
            # skipped level puts its ``/ /`` nodes on the rail, where the
            # pointer runs straight through them into the leaf below.
            middle = leaf(slots[0], truth_table[lo])
            slots[0] += 1
            for y in range(top[depth], leaf_top):
                cells.setdefault((middle, y), "│")
            for skipped in range(depth, n):
                for y in read_rows(skipped):
                    _paint(cells, middle - 1, y, "/ /")
            for y in range(top[n], leaf_top, 2):
                _paint(cells, middle - 1, y, "/ /")
            return middle
        half = (hi - lo) // 2
        west = walk(lo, lo + half, depth + 1)
        east = walk(lo + half, hi, depth + 1)
        return switch(depth, west, east)

    root = walk(0, len(truth_table), 0)
    _paint(cells, root - 1, 0, "( )")
    cells[(root, 1)] = "│"

    # A pointer heading down onto ``┴`` turns clockwise, west, and one
    # heading west runs straight through, so the bus flows west; it jogs
    # round under the first leaf into the answer column.
    bus = leaf_top + 2
    for x in range(1, middles[-1]):
        cells[(x, bus)] = "─"
    for middle in middles:
        cells[(middle, bus)] = "┴"
    cells[(middles[-1], bus)] = "┘"
    cells[(1, bus)] = "┌"
    cells[(1, bus + 1)] = "└"
    cells[(2, bus + 1)] = "┐"
    _answer_column(cells, 2, bus + 2)
    return cells


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _occurrences(ids: list[list[int]]) -> Counter[int]:
    """Count, per id, the subtrees of ``_SHARE_ROWS`` rows or more that repeat.

    Scans in drawing order, one-branch first, and stops at such a subtree
    (its inside is never shared), so a path jumps at most once.
    """
    counts = [Counter(level) for level in ids]
    found: Counter[int] = Counter()

    def scan(lo: int, hi: int, depth: int) -> None:
        sid = ids[depth][lo // (hi - lo)]
        if sid < 2:
            return
        if hi - lo >= _SHARE_ROWS and counts[depth][sid] > 1:
            found[sid] += 1
            return
        half = (hi - lo) // 2
        scan(lo + half, hi, depth + 1)
        scan(lo, lo + half, depth + 1)

    scan(0, len(ids[-1]), 0)
    return found


def _flowchart_stacked(
    truth_table: str, *, share: bool = False
) -> dict[tuple[int, int], str]:
    """Paint the tree with its subtrees stacked rather than side by side.

    The one-branch hangs below the switch and the zero-branch falls down its
    own column past it, so every node shares one column and width costs
    height.  A downward switch sends 1 east and 0 west, so each branch is
    caught by a corner: the one-branch steps east and back, the zero-branch
    runs west to the column reserved for its depth and back.  Corridor ``d``
    is column ``d`` and every descendant is deeper and further east, so no
    rail and corridor ever meet.  Each leaf turns east onto a bus down
    column ``spine + 3``, which returns to the spine below the last leaf.

    With ``share``, a subtree of ``_SHARE_ROWS`` rows or more that repeats at
    its depth is drawn once, at its last copy.  Its entry is the east detour's
    ``┴``, which a pointer from above and one from the east both leave west;
    each earlier copy runs east over the bus to a rail column (``spine + 4``
    on) and down to the entry row.  A pointer may not cross a cell it already
    left (it would take the exit remembered from the first pass), and its
    later way down the bus starts below the entry row, so the rails must run
    down to the copy; running up to it would cross that bus.
    """
    truth_table, costs, tail = _plan(truth_table)
    n = len(costs)
    # Columns 0..n-1 are the corridors, one per depth; the tree itself sits
    # on ``spine``, far enough east that the answer's ``(( ))`` clears them.
    spine = n + 2
    bus = spine + 3
    cells: dict[tuple[int, int], str] = {}
    constant = constant_span_test(truth_table)
    taps: list[int] = []
    ids = subtree_ids(truth_table)
    counts = [Counter(level) for level in ids] if share else []
    copies = _occurrences(ids) if share else Counter()
    seen: Counter[int] = Counter()
    entries: dict[int, int] = {}
    # (row, first column east, id) of each copy drawn as a jump.
    jumps: list[tuple[int, int, int]] = []

    def reads(y: int, count: int) -> int:
        """Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            _paint(cells, spine - 1, y, "/ /")
            cells[(spine, y + 1)] = "│"
            y += 2
        return y

    def leaf(y: int, depth: int, bit: str) -> int:
        """Draw the leaf for ``bit``, entered at ``(spine, y)``.

        A folded leaf's owed reads stack above it.
        """
        y = reads(y, sum(costs[depth:]) + tail)
        _paint(cells, spine - 1, y, _set(bit))
        cells[(spine, y + 1)] = "│"
        _paint(cells, spine, y + 2, "└──")
        taps.append(y + 2)
        return y + 3

    def repeat(lo: int, hi: int, depth: int, *, locked: bool) -> int | None:
        """Return the id of a subtree that may repeat, or ``None``."""
        if not share or locked or hi - lo < _SHARE_ROWS:
            return None
        sid = ids[depth][lo // (hi - lo)]
        return sid if sid >= 2 and counts[depth][sid] > 1 else None

    def role(sid: int | None) -> str:
        """Return ``"jump"`` for an earlier copy, ``"body"`` for the last."""
        if sid is None or copies[sid] < 2:
            return "plain"
        seen[sid] += 1
        return "body" if seen[sid] == copies[sid] else "jump"

    def walk(lo: int, hi: int, depth: int, y: int, *, locked: bool = False) -> int:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        if constant(lo, hi):
            return leaf(y, depth, truth_table[lo])
        y = reads(y, costs[depth])
        _paint(cells, spine - 1, y, "< >")
        half = (hi - lo) // 2
        # b=1: east out of the switch, down, back west, onto the spine
        cells[(spine + 2, y)] = "┐"
        one = repeat(lo + half, hi, depth + 1, locked=locked)
        how = role(one)
        if one is not None and how == "jump":
            cells[(spine + 2, y + 1)] = "└"
            jumps.append((y + 1, spine + 3, one))
            below = y + 2
        else:
            cells[(spine + 2, y + 1)] = "┴" if how == "body" else "┘"
            if one is not None and how == "body":
                entries[one] = y + 1
            cells[(spine + 1, y + 1)] = "─"
            cells[(spine, y + 1)] = "┌"
            below = walk(
                lo + half, hi, depth + 1, y + 2, locked=locked or one is not None
            )
        # b=0: west to this depth's own column, down past everything the
        # one-branch drew, then east again onto the spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y)] = "─"
        cells[(depth, y)] = "┌"
        for row in range(y + 1, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        zero = repeat(lo, lo + half, depth + 1, locked=locked)
        how = role(zero)
        if zero is not None and how == "jump":
            for x in range(depth + 1, spine + 2):
                cells[(x, below)] = "─"
            jumps.append((below, spine + 2, zero))
            return below + 1
        for x in range(depth + 1, spine + 2 if how == "body" else spine):
            cells[(x, below)] = "─"
        if zero is None or how == "plain":
            cells[(spine, below)] = "┐"
            return walk(
                lo, lo + half, depth + 1, below + 1, locked=locked or zero is not None
            )
        # A repeated zero-branch is entered from the east like a one-branch.
        cells[(spine + 2, below)] = "┐"
        cells[(spine + 2, below + 1)] = "┴"
        cells[(spine + 1, below + 1)] = "─"
        cells[(spine, below + 1)] = "┌"
        entries[zero] = below + 1
        return walk(lo, lo + half, depth + 1, below + 2, locked=True)

    walk(0, len(truth_table), 0, 2)
    _paint(cells, spine - 1, 0, "( )")
    cells[(spine, 1)] = "│"
    # Heading east onto ``┤`` turns clockwise, down, so every tap joins.
    for row in range(taps[0], taps[-1] + 1):
        cells[(bus, row)] = "│"
    for row in taps:
        cells[(bus, row)] = "┤"
    cells[(bus, taps[0])] = "┐"
    end = taps[-1] + 1
    cells[(bus, end)] = "┘"
    _paint(cells, spine, end, "┌──")
    _answer_column(cells, spine, end + 1)
    _join_jumps(cells, jumps, entries, spine)
    return cells


def _join_jumps(
    cells: dict[tuple[int, int], str],
    jumps: list[tuple[int, int, int]],
    entries: dict[int, int],
    spine: int,
) -> None:
    """Draw each copy's rail down to the entry row of its drawn subtree.

    The topmost copy of an id is the trunk: east along its row, down column
    ``spine + 4 + k`` and west along the entry row to the ``┴``.  A lower copy
    runs east along its own row and turns down onto the trunk at ``┤`` (a
    pointer heading east onto it turns down).  Groups whose spans are apart
    share a column; crossings (the bus, other rails) become ``┼``.
    """

    def put(x: int, y: int, char: str) -> None:
        crossing = {cells.get((x, y)), char} == {"│", "─"}
        cells[(x, y)] = "┼" if crossing else char

    last_row: list[int] = []  # per rail column, the entry row it reaches
    groups: dict[int, list[tuple[int, int]]] = {}
    for row, start, sid in jumps:
        groups.setdefault(sid, []).append((row, start))
    for sid in sorted(groups, key=lambda sid: min(groups[sid])):
        copies = sorted(groups[sid])
        top, entry = copies[0][0], entries[sid]
        column = next((k for k, end in enumerate(last_row) if end < top), None)
        if column is None:
            column = len(last_row)
            last_row.append(entry)
        last_row[column] = entry
        x = spine + 4 + column
        for y in range(top + 1, entry):
            put(x, y, "│")
        cells[(x, entry)] = "┘"
        for i in range(spine + 3, x):
            put(i, entry, "─")
        for number, (row, start) in enumerate(copies):
            for i in range(start, x):
                put(i, row, "─")
            cells[(x, row)] = "┐" if number == 0 else "┤"


def flowchart(truth_table: str, width: int | None = None) -> str:
    """Build a Flowchart program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    Constants read a straight skip chain and print once. Otherwise, without
    ``width``, preloads paired answers into deques and selects one
    by the input bits; with it, draws a decision tree, stacked if narrower,
    and in the stacked one draws a repeated subtree once when ``width`` leaves
    room for its rail columns and characters and rectangle both shrink.
    """
    _validate_truth_table(truth_table)
    if width is None:
        return _flowchart_deque(truth_table)
    flat = _flowchart_render(_flowchart_cells(truth_table))
    if grid_width(flat) <= width:
        return flat
    stacked = _flowchart_render(_flowchart_stacked(truth_table))
    best = narrowest_grid(flat, stacked)
    if best is not stacked:
        return best
    # Drawing repeats once costs rail columns, so it needs room and a gain
    # in both characters and the rectangle.
    shared = _flowchart_render(_flowchart_stacked(truth_table, share=True))
    fits = grid_width(shared) <= width
    if fits and len(shared) < len(stacked) and _area(shared) < _area(stacked):
        return shared
    return stacked


def _area(program: str) -> int:
    """Return the cells of the program's bounding rectangle."""
    return grid_width(program) * (program.count("\n") + 1)


def _flowchart_deque(truth_table: str, *, keep_constant_input: bool = False) -> str:
    r"""Address one preloaded answer by walking the deque cursor to it.

    Entries ``2j`` and ``2j + 1`` are pushed onto deque ``j`` in that order,
    so the preload leaves the cursor on ``T / 2 - 1`` and the first ``n - 1``
    bits walk it back: a zero at level ``k`` steps the cursor down by
    ``2 ** (n - 2 - k)`` and a one leaves it alone.  The last bit needs no
    step at all -- the pair sharing a deque is one at each end, so it picks
    ``\{ }/`` or ``/{ }\`` and halves both the ``[ >`` run and the walk.

    Two rows; the pointer runs east to west, so the selector sits in the low
    columns and the upper row stays short (a line is padded to its last
    non-space cell).

    Input ``p``'s value bit is stream bit ``8p``, so an ignored input costs
    only the eight ``/ /`` that skip it, and the deque holds the table over
    the essential inputs alone.  Trailing ignored inputs are read in each
    answer arm, ahead of its pop.
    """
    n = len(truth_table).bit_length() - 1
    used = essential_inputs(truth_table, n)
    if not used and not keep_constant_input:
        # Read only the value bit of the final byte; earlier bytes are skipped.
        nodes = ["( )", *["/ /"] * (8 * (n - 1) + 1), _set(truth_table[0]), *_ANSWER]
        return "─".join(reversed(nodes))
    used = used or list(range(n))
    truth_table = read_at(truth_table, used, n)
    skips = [8 * used[0] + 1] + [8 * (b - a) for a, b in pairwise(used)]
    cells: dict[tuple[int, int], str] = {}
    spine = 1
    col = 0

    def west(text: str) -> int:
        """Place ``text`` on the spine ending at ``col``; return its left end."""
        nonlocal col
        left = col - len(text) + 1
        _paint(cells, left, spine, text)
        cells[(left - 1, spine)] = "─"
        col = left - 2
        return left

    west("( )")
    # ``\[ ]/`` and ``[ >`` both leave the register alone, so a run of equal
    # entries is set once and pushed however many times it is long.
    register: str | None = None
    for index, bit in enumerate(truth_table):
        if register != bit:
            west(_set(bit))
            register = bit
        west("\\[ ]/")
        if index % 2 and index + 1 < len(truth_table):
            west("[ >")

    m = len(used)
    for level in range(m - 1):
        for _ in range(skips[level]):
            west("/ /")
        switch = west("< >")
        # Travelling west a switch sends 1 straight on and 0 up, and the
        # rail west of the switch is the one-branch's bypass.
        count = 1 << (m - 2 - level)
        # "< ]─" is 4 cells
        junction = col - 4 * count + 1
        _paint(cells, switch, spine - 1, "─┐")
        _paint(cells, junction + 1, spine - 1, "< ]─" * count)
        _paint(cells, junction + 1, spine, "─" * (4 * count))
        cells[(junction, spine - 1)] = "┌"
        cells[(junction, spine)] = "┴"
        col = junction - 1

    # The last bit picks an end rather than a deque: the pair sharing a deque
    # was pushed even entry first, so its odd half is the top.  Each arm
    # prints its own answer, the upper one a column east of the spine's.
    for _ in range(skips[m - 1]):
        west("/ /")
    switch = west("< >")
    cells[(switch + 1, spine - 1)] = "┐"
    # A trailing ignored input is read before the pop, which overwrites the
    # register they leave behind; the arms split here so each repeats them.
    owed = ("/ /",) * (8 * (n - 1 - used[-1]))
    upper = "─".join(reversed((*owed, "/{ }\\", *_ANSWER)))
    _paint(cells, switch - len(upper), spine - 1, upper + "─")
    for text in (*owed, "\\{ }/", *_ANSWER):
        end = west(text)
    del cells[(end - 1, spine)]

    left = min(x for x, _ in cells)
    return _flowchart_render({(x - left, row): c for (x, row), c in cells.items()})


def _balance(table: str, default: str) -> str:
    """Compare deque lookup, flat tree and the supported stacked fallback."""
    flat = _flowchart_render(_flowchart_cells(table))
    candidates = [default, flat, flowchart(table, 1)]
    if len(set(table)) == 1:
        candidates.append(_flowchart_deque(table, keep_constant_input=True))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Flowchart",
    "grid_based.flowchart",
    # The README frame: a grid language, so the screenshot shows the 2D
    # program pane and a tuple ``ip``, neither of which a tape language
    # exercises.  ``replay`` derives the frame from nothing, so this is a
    # coordinate, not a recording.
    showcase=True,
    boolean=flowchart,
    # Not a tree: one deque push per entry.
    shape=Shape.LOOKUP,
    split=True,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    eof="reads at input nodes, including the constant skip chain",
    empty_program="Flowchart program has no '( )' start node",
)
