"""Flowchart Boolean program generator: a deque lookup, or a decision tree.

I/O is byte-oriented, low bit first.  Each input is a ``'0'``/``'1'``
byte whose low bit is the value, so input ``k`` is read by eight ``/ /``
nodes -- the previous byte's seven high bits, then this byte's value bit,
which the switch tests.  The first input has no previous byte and the last
byte's high bits are never read: the interpreter has already consumed the
whole byte.  The answer is printed as R and then the seven high bits of
ASCII ``'0'`` (:data:`_ANSWER`), so the output byte is ``'0'`` or ``'1'``.

The default is a deque lookup, one pushed entry a row (a run of equal entries
sets the register once), so it has no subtrees to share.  With ``width`` it
draws a decision tree, stacked if narrower; the stacked one draws a repeated
subtree once when ``width`` leaves room for its rail columns and characters
and rectangle both shrink.

Size:
    O(T) characters; n=10 random 1847: 15,154 chars, n=12 random 1847:
    58,138 chars.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    grid_area,
    grid_width,
    narrowest_grid,
    read_at,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.flowchart.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

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


def _folded_walk[C, R](
    rows: int,
    constant: Callable[[int, int], bool],
    leaf: Callable[[int, int, C], R],
    branch: Callable[[int, int, int, C, Callable[[int, int, int, C], R]], R],
    cursor: C,
) -> R:
    """Walk the folded decision tree, painting it through callbacks.

    ``leaf(lo, depth, cursor)`` paints a constant span; ``branch(lo, hi,
    depth, cursor, descend)`` paints a switch and calls ``descend(lo, hi,
    depth, cursor)`` for each half it draws, in whichever order its layout
    needs.  The traversal -- constant test, halving, recursion -- is shared;
    the painters differ only in cell placement.  The cursor is opaque to the
    walk: the stacked painter threads its row and lock flag through it, the
    others pass ``None``.  Returns whatever the root call returns.
    """

    def descend(lo: int, hi: int, depth: int, cursor: C) -> R:
        if constant(lo, hi):
            return leaf(lo, depth, cursor)
        return branch(lo, hi, depth, cursor, descend)

    return descend(0, rows, 0, cursor)


@dataclass(frozen=True)
class _SnakeRun:
    """The shape of one snaking path: where it starts and how it folds.

    The path enters column 0 at ``(x, y)`` heading down and reads the
    columns in turn, ``step`` apart (negative runs west).  A column has
    ``slots`` node rows two apart.  With ``pad`` the unused slots are
    rails (the path then ends at the bottom of the last column when
    ``cols`` is odd, which the caller needs); without it the path stops
    after its last node and its trailing rail is removed.
    """

    x: int
    y: int
    cols: int
    step: int
    slots: int
    pad: bool


def _snake(
    cells: dict[tuple[int, int], str], run: _SnakeRun, nodes: Sequence[str | None]
) -> int:
    """Paint ``nodes`` along the path ``run`` describes; return its exit.

    Columns are read down, then up, joined by ``└─┘`` below and ``┌─┐``
    above; a ``None`` node is a bare rail.  Returns the column the path
    leaves from.
    """
    x, y, step, slots = run.x, run.y, run.step, run.slots
    count = len(nodes)
    for col in range(run.cols):
        cx = x + step * col
        down = col % 2 == 0
        for slot in range(slots):
            index = col * slots + slot
            if index >= count and not run.pad:
                break
            row = y + 2 * (slot if down else slots - 1 - slot)
            node = nodes[index] if index < count else None
            if node is None:
                cells[(cx, row)] = "│"
            else:
                _paint(cells, cx - len(node) // 2, row, node)
            cells[(cx, row + 1)] = cells[(cx, row - 1)] = "│"
    for col in range(run.cols - 1):
        if not run.pad and (col + 1) * slots >= count:
            break
        cx = x + step * col
        down = col % 2 == 0
        row = y + 2 * slots - 1 if down else y - 1
        for i in range(min(cx, cx + step), max(cx, cx + step) + 1):
            cells[(i, row)] = "─"
        # Heading down the turn is to the east when ``step`` is positive.
        corner = ("└", "┘") if down else ("┌", "┐")
        cells[(cx, row)] = corner[step < 0]
        cells[(cx + step, row)] = corner[step > 0]
    return x + step * (run.cols - 1)


class _TreePainter:
    """Painter state for the flat layout: the grid the walk paints onto.

    The walk (see :func:`_folded_walk`) hands each leaf and branch to this
    painter; the state its phases share -- the cell map, the per-level row
    plan, the leaf slots handed out so far -- lives here instead of in
    closures over one function's locals.
    """

    def __init__(
        self,
        truth_table: str,
        fold: int,
        answer_cols: int,
        plan: tuple[str, list[int], int] | None = None,
    ) -> None:
        self.fold = fold
        self.answer_cols = answer_cols
        self.cells: dict[tuple[int, int], str] = {}
        self.truth_table, self.costs, self.tail = plan or _plan(truth_table)
        self.constant = constant_span_test(self.truth_table)
        self.n = len(self.costs)
        self.lanes = [-(-cost // fold) for cost in self.costs]
        # top[d] is level d's first read row; top[n] is where the tail's
        # reads start and the leaves follow them.
        self.top = [2]
        for level in range(self.n):
            self.top.append(self.top[-1] + 2 * self.lanes[level] + 2)
        self.leaf_top = self.top[self.n] + 2 * -(-self.tail // fold)
        self.reach = 4 * (fold - 1)
        # Leaf slots are handed out left to right as the walk reaches each
        # leaf, so a folded subtree takes one column band instead of the
        # ``2**k`` its rows would have filled -- the drawing narrows rather
        # than leaving a gap.
        self.middles: list[int] = []
        self.previous: list[tuple[int, bool]] = []

    def paint(self) -> dict[tuple[int, int], str]:
        """Walk the folded tree, then join the leaves to the answer."""
        # A left child's chain runs west of its node and is entered at its
        # east end, so siblings' entries face each other and the switch
        # between them clears both; a right child's runs east.  Unfolded,
        # all face east.
        root = _folded_walk(
            len(self.truth_table),
            self.constant,
            self.paint_leaf,
            self.paint_branch,
            4,
        )
        _paint(self.cells, root - 1, 0, "( )")
        self.cells[(root, 1)] = "│"
        self._paint_bus()
        left = min(x for x, _ in self.cells)
        return {(x - left, y): c for (x, y), c in self.cells.items()}

    def paint_leaf(self, lo: int, depth: int, step: int) -> int:
        """Draw the leaf for ``truth_table[lo]``; return its entry column."""
        cells, previous, reach = self.cells, self.previous, self.reach
        mirrored = step < 0
        # Constant: no branch below can change the answer.  Leaves sit on the
        # bottom row whatever their depth, so the rail from the switch above
        # covers the skipped levels (rows are a fixed grid; the cursor is the
        # chain's step, west for a left child).  The skipped levels' *reads*
        # stay: a folded run that skipped them left the caller's remaining
        # bits on the stream, so each puts its ``/ /`` nodes on the rail.
        entry = reach + 2 if mirrored else 2
        if previous:
            before, was_mirrored = previous[-1]
            # Regions are [entry - 1 - reach, entry + 1] mirrored, else
            # [entry - 1, entry + 1 + reach]; keep two blank columns.
            entry = max(
                _FLOWCHART_PITCH + before,
                before
                + (1 if was_mirrored else reach + 1)
                + 3
                + (reach if mirrored else 0),
            )
            if was_mirrored and not mirrored and self.fold > 1:
                entry = max(entry, before + 7)
        previous.append((entry, mirrored))
        path: list[str | None] = []
        for skipped in range(depth, self.n):
            path += ["/ /"] * self.costs[skipped] + [None]
        path += ["/ /"] * self.tail
        slots = (self.leaf_top - self.top[depth]) // 2
        middle = entry
        if slots:
            middle = _snake(
                cells,
                _SnakeRun(
                    entry, self.top[depth], self.fold, step, slots=slots, pad=True
                ),
                path,
            )
        _paint(cells, middle - 1, self.leaf_top, _set(self.truth_table[lo]))
        cells[(middle, self.leaf_top + 1)] = "│"
        self.middles.append(middle)
        return entry

    def switch(self, depth: int, west: int, east: int, step: int) -> int:
        """Join two subtrees at ``depth``; return the column it is entered at."""
        cells, top = self.cells, self.top
        switch_row = top[depth + 1] - 2
        middle = (west + east) // 2
        entry = middle - step * (self.fold - 1)
        _snake(
            cells,
            _SnakeRun(
                entry,
                top[depth],
                self.fold,
                step,
                slots=self.lanes[depth],
                pad=True,
            ),
            ["/ /"] * self.costs[depth],
        )
        _paint(cells, middle - 1, switch_row, "< >")
        for x in range(west + 1, middle - 1):
            cells[(x, switch_row)] = "─"
        for x in range(middle + 2, east):
            cells[(x, switch_row)] = "─"
        cells[(west, switch_row)] = "┌"
        cells[(east, switch_row)] = "┐"
        cells[(west, switch_row + 1)] = "│"
        cells[(east, switch_row + 1)] = "│"
        return entry

    def paint_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        step: int,
        descend: Callable[[int, int, int, int], int],
    ) -> int:
        """Draw the subtrees for ``truth_table[lo:hi]``; return the entry."""
        half = (hi - lo) // 2
        west = descend(lo, lo + half, depth + 1, -4 if self.fold > 1 else 4)
        east = descend(lo + half, hi, depth + 1, 4)
        return self.switch(depth, west, east, step)

    def _paint_bus(self) -> None:
        """Join every leaf to the answer column along the westward bus."""
        cells, middles = self.cells, self.middles
        # A pointer heading down onto ``┴`` turns clockwise, west, and one
        # heading west runs straight through, so the bus flows west; it
        # jogs round under the first leaf into the answer column.
        bus = self.leaf_top + 2
        base, last = min(middles), max(middles)
        for x in range(base - 1, last):
            cells[(x, bus)] = "─"
        for middle in middles:
            cells[(middle, bus)] = "┴"
        cells[(last, bus)] = "┘"
        cells[(base - 1, bus)] = "┌"
        cells[(base - 1, bus + 1)] = "└"
        cells[(base, bus + 1)] = "┐"
        if self.answer_cols > 1:
            slots = -(-len(_ANSWER) // self.answer_cols)
            _snake(
                cells,
                _SnakeRun(base, bus + 2, self.answer_cols, 6, slots=slots, pad=False),
                _ANSWER,
            )
            last = len(_ANSWER) - 1
            col, slot = divmod(last, slots)
            row = bus + 2 + 2 * (slot if col % 2 == 0 else slots - 1 - slot)
            del cells[(base + 6 * col, row + (1 if col % 2 == 0 else -1))]
            cells[(base, bus + 1)] = "┐"
        else:
            _answer_column(cells, base, bus + 2)


def _normalized(
    cells: dict[tuple[int, int], str],
) -> tuple[dict[tuple[int, int], str], int]:
    """Return ``cells`` shifted to start at column 0, and the shift."""
    left = min(x for x, _ in cells)
    return {(x - left, y): c for (x, y), c in cells.items()}, left


class _BandPainter(_TreePainter):
    """One flat subtree of a banded drawing, entered from its east.

    The ``( )`` is replaced by a corner taking the rail in along row 0, and
    the bus stops at its west end for the caller to extend.
    """

    def paint_band(self) -> tuple[dict[tuple[int, int], str], int, int, int]:
        """Return the cells, root column, bus west end and bus row."""
        cells, middles = self.cells, self.middles
        root = _folded_walk(
            len(self.truth_table), self.constant, self.paint_leaf, self.paint_branch, 4
        )
        cells[(root, 0)] = "┌"
        cells[(root, 1)] = "│"
        bus = self.leaf_top + 2
        base, last = min(middles), max(middles)
        for x in range(base, last):
            cells[(x, bus)] = "─"
        for middle in middles:
            cells[(middle, bus)] = "┴"
        cells[(last, bus)] = "┘"
        cells, left = _normalized(cells)
        return cells, root - left, base - left, bus


class _TopPainter(_TreePainter):
    """The top ``k`` levels of a banded drawing, one leaf per band."""

    def __init__(self, costs: list[int]) -> None:
        size = 1 << len(costs)
        super().__init__("0" * size, 1, 1, ("0" * size, costs, 0))
        self.constant = lambda lo, hi: hi - lo == 1

    def paint_leaf(self, _lo: int, _depth: int, _step: int) -> int:
        """Return the entry column of the next band's channel."""
        entry = self.middles[-1] + _FLOWCHART_PITCH if self.middles else 2
        self.middles.append(entry)
        return entry

    def paint_top(self) -> tuple[dict[tuple[int, int], str], list[int], int]:
        """Return the cells, the channel columns and the first channel row."""
        cells = self.cells
        root = _folded_walk(
            len(self.truth_table), self.constant, self.paint_leaf, self.paint_branch, 4
        )
        _paint(cells, root - 1, 0, "( )")
        cells[(root, 1)] = "│"
        cells, left = _normalized(cells)
        return cells, [m - left for m in self.middles], self.leaf_top


def _banded(table: str, split: int, fold: int) -> str:
    """Stack the ``2**split`` subtrees of ``table`` and join their buses.

    A top tree over the first ``split`` inputs sits at the upper east and
    drops one channel per subtree; channel ``b`` turns west into band ``b``,
    and the channels leave in band order so no rail crosses another.  Each
    band's bus runs west to a staircase column, turns down and joins the next
    band's bus, so one answer column serves all.
    """
    reduced, costs, tail = _plan(table)
    bands = len(reduced) >> (len(costs) - split)
    size = len(reduced) // bands
    subs = [reduced[b * size : (b + 1) * size] for b in range(bands)]
    painted = [
        _BandPainter(sub, fold, 1, (sub, costs[split:], tail)).paint_band()
        for sub in subs
    ]
    height = painted[0][3] + 1
    stairs = [2 * (bands - b) for b in range(bands)]
    west = 2 * bands + 3
    east = west + max(max(x for x, _ in cells) for cells, *_ in painted) + 2
    top_cells, channels, start = _TopPainter(costs[:split]).paint_top()
    out: dict[tuple[int, int], str] = {
        (east + x, y): c for (x, y), c in top_cells.items()
    }
    for b, (cells, root, base, bus) in enumerate(painted):
        row = start + b * height
        for (x, y), c in cells.items():
            out[(west + x, row + y)] = c
        chan = east + channels[b]
        for y in range(start, row):
            out[(chan, y)] = "│"
        out[(chan, row)] = "┘"
        for x in range(west + root + 1, chan):
            out[(x, row)] = "─"
        wire = row + bus
        for x in range(stairs[b] + 1, west + base):
            out[(x, wire)] = "─"
        out[(stairs[b], wire)] = "┌"
        if b:
            out[(stairs[b - 1], wire)] = "┴"
            for y in range(wire - height + 1, wire):
                out[(stairs[b - 1], y)] = "│"
    _answer_column(out, stairs[-1], row + bus + 1)
    return _flowchart_render(out)


def _flowchart_cells(
    truth_table: str, fold: int = 1, answer_cols: int = 1
) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves first on a fixed pitch, switches collapsed upwards and centred
    between their entry columns with rails to both.  Rows: ``( )``, rail,
    then per level its reads and switch, each followed by a rail; each leaf
    sets the register and drops onto a westward bus to the shared answer.
    ``fold`` (odd) snakes every read chain over that many columns, and
    ``answer_cols`` the answer column; ``1, 1`` is the plain tall drawing.
    """
    return _TreePainter(truth_table, fold, answer_cols).paint()


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    height = max(y for _, y in cells) + 1
    width = max(x for x, _ in cells) + 1
    grid = [[" "] * width for _ in range(height)]
    for (x, y), char in cells.items():
        grid[y][x] = char
    return "\n".join("".join(row).rstrip() for row in grid)


def _shareable(
    ids: list[list[int]], counts: list[Counter[int]], depth: int, lo: int, hi: int
) -> int | None:
    """Return the subtree id if the span is drawn once and shared, else None.

    A span is shared when it covers at least ``_SHARE_ROWS`` rows and its
    subtree id repeats at this depth.  Constant spans have ids 0/1 and are
    never shared.
    """
    if hi - lo < _SHARE_ROWS:
        return None
    sid = ids[depth][lo // (hi - lo)]
    return sid if sid >= 2 and counts[depth][sid] > 1 else None


def _occurrences(
    ids: list[list[int]], constant: Callable[[int, int], bool]
) -> Counter[int]:
    """Count, per id, the subtrees of ``_SHARE_ROWS`` rows or more that repeat.

    Scans in drawing order, one-branch first, and stops at such a subtree
    (its inside is never shared), so a path jumps at most once.
    """
    counts = [Counter(level) for level in ids]
    found: Counter[int] = Counter()

    def on_leaf(_lo: int, _depth: int, _cursor: None) -> None:
        """Constant spans are never shared, so there is nothing to count."""

    def on_branch(
        lo: int,
        hi: int,
        depth: int,
        _cursor: None,
        descend: Callable[[int, int, int, None], None],
    ) -> None:
        sid = _shareable(ids, counts, depth, lo, hi)
        if sid is None:
            half = (hi - lo) // 2
            descend(lo + half, hi, depth + 1, None)
            descend(lo, lo + half, depth + 1, None)
        else:
            found[sid] += 1

    _folded_walk(len(ids[-1]), constant, on_leaf, on_branch, None)
    return found


_Cursor = tuple[int, bool]


class _Role(Enum):
    """How the stacked layout draws one branch's subtree."""

    PLAIN = "plain"
    JUMP = "jump"  # an earlier copy of a shared subtree: a rail to the last
    BODY = "body"  # the last copy, drawn once and entered from the east


class _Stacked:
    """Painter state for the stacked layout; ``cursor`` is ``(row, locked)``."""

    def __init__(self, truth_table: str, *, share: bool) -> None:
        self.truth_table, self.costs, self.tail = _plan(truth_table)
        # Columns 0..n-1 are the corridors, one per depth; the tree itself
        # sits on ``spine``, far enough east that the answer's ``(( ))``
        # clears them.
        self.spine = len(self.costs) + 2
        self.bus = self.spine + 3
        self.cells: dict[tuple[int, int], str] = {}
        self.constant = constant_span_test(self.truth_table)
        self.taps: list[int] = []
        self.share = share
        self.ids = subtree_ids(self.truth_table)
        self.counts = [Counter(level) for level in self.ids] if share else []
        self.copies = _occurrences(self.ids, self.constant) if share else Counter[int]()
        self.seen: Counter[int] = Counter()
        self.entries: dict[int, int] = {}
        # (row, first column east, id) of each copy drawn as a jump.
        self.jumps: list[tuple[int, int, int]] = []

    def reads(self, y: int, count: int) -> int:
        """Draw ``count`` ``/ /`` nodes down the spine; return the row after."""
        for _ in range(count):
            _paint(self.cells, self.spine - 1, y, "/ /")
            self.cells[(self.spine, y + 1)] = "│"
            y += 2
        return y

    def paint_leaf(self, lo: int, depth: int, cursor: _Cursor) -> _Cursor:
        """Draw the leaf for ``truth_table[lo]``, entered at ``(spine, y)``.

        A folded leaf's owed reads stack above it.  Returns the row below
        the leaf and the unchanged lock flag.
        """
        cells, spine = self.cells, self.spine
        y, locked = cursor
        y = self.reads(y, sum(self.costs[depth:]) + self.tail)
        _paint(cells, spine - 1, y, _set(self.truth_table[lo]))
        cells[(spine, y + 1)] = "│"
        _paint(cells, spine, y + 2, "└──")
        self.taps.append(y + 2)
        return y + 3, locked

    def classify(
        self, lo: int, hi: int, depth: int, *, locked: bool
    ) -> tuple[int | None, _Role]:
        """Return the span's repeating subtree id (or ``None``) and its role.

        A candidate that never repeats in a drawn copy is ``PLAIN`` but its id
        is still returned: the descent below it stays locked.
        """
        if not self.share or locked:
            return None, _Role.PLAIN
        sid = _shareable(self.ids, self.counts, depth, lo, hi)
        if sid is None or self.copies[sid] < 2:
            return sid, _Role.PLAIN
        self.seen[sid] += 1
        last = self.seen[sid] == self.copies[sid]
        return sid, _Role.BODY if last else _Role.JUMP

    def paint_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        cursor: _Cursor,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
    ) -> _Cursor:
        """Draw the subtree for ``truth_table[lo:hi]``; return the row after."""
        y, locked = cursor
        y = self.reads(y, self.costs[depth])
        _paint(self.cells, self.spine - 1, y, "< >")
        half = (hi - lo) // 2
        below = self._one_branch(lo + half, hi, depth, y, descend, locked=locked)
        return self._zero_branch(lo, lo + half, depth, y, below, descend, locked=locked)

    def _enter_from_east(self, y: int, corner: str) -> None:
        """Paint the detour west from ``spine + 2`` onto the spine at row ``y``."""
        self.cells[(self.spine + 2, y)] = corner
        self.cells[(self.spine + 1, y)] = "─"
        self.cells[(self.spine, y)] = "┌"

    def _one_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        y: int,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
        *,
        locked: bool,
    ) -> int:
        """Draw b=1: east out of the switch, down, back west onto the spine.

        Returns the row below it, where the zero-branch's rail ends.
        """
        cells, spine = self.cells, self.spine
        cells[(spine + 2, y)] = "┐"
        one, how = self.classify(lo, hi, depth + 1, locked=locked)
        if how is _Role.JUMP:
            assert one is not None
            cells[(spine + 2, y + 1)] = "└"
            self.jumps.append((y + 1, spine + 3, one))
            return y + 2
        self._enter_from_east(y + 1, "┴" if how is _Role.BODY else "┘")
        if one is not None and how is _Role.BODY:
            self.entries[one] = y + 1
        below, _ = descend(lo, hi, depth + 1, (y + 2, locked or one is not None))
        return below

    def _zero_branch(
        self,
        lo: int,
        hi: int,
        depth: int,
        y: int,
        below: int,
        descend: Callable[[int, int, int, _Cursor], _Cursor],
        *,
        locked: bool,
    ) -> _Cursor:
        """Draw b=0: west to this depth's own column, down past the one-branch.

        Then east again onto the spine.
        """
        cells, spine = self.cells, self.spine
        for x in range(depth + 1, spine - 1):
            cells[(x, y)] = "─"
        cells[(depth, y)] = "┌"
        for row in range(y + 1, below):
            cells[(depth, row)] = "│"
        cells[(depth, below)] = "└"
        zero, how = self.classify(lo, hi, depth + 1, locked=locked)
        if how is _Role.JUMP:
            assert zero is not None
            for x in range(depth + 1, spine + 2):
                cells[(x, below)] = "─"
            self.jumps.append((below, spine + 2, zero))
            return below + 1, locked
        for x in range(depth + 1, spine + 2 if how is _Role.BODY else spine):
            cells[(x, below)] = "─"
        if how is _Role.PLAIN:
            cells[(spine, below)] = "┐"
            return descend(lo, hi, depth + 1, (below + 1, locked or zero is not None))
        # A repeated zero-branch is entered from the east like a one-branch.
        cells[(spine + 2, below)] = "┐"
        self._enter_from_east(below + 1, "┴")
        assert zero is not None
        self.entries[zero] = below + 1
        return descend(lo, hi, depth + 1, (below + 2, True))

    def close(self) -> None:
        """Paint the answer, then the bus joining every leaf tap to it."""
        cells, spine, bus, taps = self.cells, self.spine, self.bus, self.taps
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
        _join_jumps(cells, self.jumps, self.entries, spine)


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
    painter = _Stacked(truth_table, share=share)
    _folded_walk(
        len(painter.truth_table),
        painter.constant,
        painter.paint_leaf,
        painter.paint_branch,
        (2, False),
    )
    painter.close()
    return painter.cells


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
        else:
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
    Constants read a straight skip chain and print once.
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
    if fits and len(shared) < len(stacked) and grid_area(shared) < grid_area(stacked):
        return shared
    return stacked


def _flowchart_deque(truth_table: str) -> str:
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
    if not essential_inputs(truth_table, n):
        # Read only the value bit of the final byte; earlier bytes are skipped.
        nodes = ["( )", *["/ /"] * (8 * (n - 1) + 1), _set(truth_table[0]), *_ANSWER]
        return "─".join(reversed(nodes))
    truth_table, skips, tail = _plan(truth_table)
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

    m = len(skips)
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
    owed = ("/ /",) * tail
    upper = "─".join(reversed((*owed, "/{ }\\", *_ANSWER)))
    _paint(cells, switch - len(upper), spine - 1, upper + "─")
    for text in (*owed, "\\{ }/", *_ANSWER):
        end = west(text)
    del cells[(end - 1, spine)]

    left = min(x for x, _ in cells)
    return _flowchart_render({(x - left, row): c for (x, row), c in cells.items()})


def _banded_candidates(table: str) -> list[str]:
    """Return the banded drawing when ``m`` read levels leave room to split.

    Split ``(m - 3) // 2`` levels off the top, folded over 3 columns: the
    best split of random n=7..12 tables (area per row 1.6k-3.2k at n=7..12,
    against the flat tree's 4.6k at n=8 and 77k at n=12).
    """
    split = (len(_plan(table)[1]) - 3) // 2
    return [_banded(table, split, 3)] if split > 0 else []


def _balance(table: str, default: str) -> str:
    """Return the squarest of the default, banded and trees snaked over columns.

    Candidates are the flat tree folded over 1, 3 or 5 columns per chain
    (``_snake``) and up to 6 for the answer.  Only nine of the 18 pairs ever
    won on 68 random tables n=1..7; dropping the other nine lengthens one
    tiled n=7 table by 11 characters (0.04%).  Folding trades height for
    width, so it fades from n=6, where the leaf row (~4.6 columns a leaf) is
    already the wider side: mean side 272 vs 274 at n=6, 558 vs 559 at n=7.
    From 5 read levels the banded drawing joins them (``_banded``): the flat
    tree's leaf row alone is ~4.6 columns a leaf, so its side grew with T and
    its area as T^2.  The deque (2 rows), the stacked fallback and the
    constant-input deque never beat the flat tree: 0 wins of ~1.5k tables at
    n=1..12 (exhaustive to n=3).
    """
    return min(
        default,
        *_banded_candidates(table),
        *(
            _flowchart_render(_flowchart_cells(table, fold, cols))
            for fold, cols in (
                (1, 2),
                (1, 4),
                (1, 6),
                (3, 2),
                (3, 3),
                (3, 4),
                (3, 6),
                (5, 4),
                (5, 6),
            )
        ),
        key=balance_score,
    )


LANGUAGE = Language(
    "Flowchart",
    "flowchart",
    category="grid_based",
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
    proof_workspace=(workspace, True, (3, 4, 5)),
    grid=True,
)
