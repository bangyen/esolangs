"""Flowchart Boolean program generator: a deque lookup, or a decision tree.

I/O is byte-oriented, low bit first.  Each input is a ``'0'``/``'1'``
byte whose low bit is the value, so input ``k`` is read by eight ``/ /``
nodes -- the previous byte's seven high bits, then this byte's value bit,
which the switch tests.  The first input has no previous byte and the last
byte's high bits are never read: the interpreter has already consumed the
whole byte.  The answer is printed as R and then the seven high bits of
ASCII ``'0'`` (:data:`_ANSWER`), so the output byte is ``'0'`` or ``'1'``.

The default is a deque lookup, one pushed entry a row (a run of equal entries
sets the register once), so it has no subtrees to share.  A deque holds
``2 ** ceil(m / 2)`` entries for m essential inputs; low inputs pop pairs
off both ends to
reach theirs, so the cursor rails shrink to ``sqrt(T)``.  With ``width`` it
draws a decision tree, stacked if narrower; the stacked one draws a repeated
subtree once when ``width`` leaves room for its rail columns and characters
and rectangle both shrink.

Size:
    Default: O(T) characters; n=10 random 1847: 9,754 chars, n=12 random 1847:
    35,074 chars.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import chain

from esolangs.generation.grid import grid_area, grid_width, narrowest_grid
from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.projection import essential_inputs
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import balance_score
from esolangs.languages.flowchart._layout import (
    _ANSWER,
    _answer_column,
    _folded_walk,
    _InputPlan,
    _paint,
    _plan,
    _set,
)
from esolangs.languages.flowchart._stacked import _flowchart_stacked
from esolangs.runtime._program import Program

# Leaf column pitch: 5-cell ``(( ))`` plus 1 gutter.
_FLOWCHART_PITCH = 6


@dataclass(frozen=True)
class _SnakeRun:
    """The shape of one snaking path: where it starts and how it folds.

    The path enters column 0 at ``(x, y)`` heading down and reads the
    columns in turn, ``step`` apart (negative runs west).  A column has
    ``slots`` node rows two apart. Unused read slots are rails. Answer
    strips fill every slot; the caller removes their trailing rail.
    """

    x: int
    y: int
    cols: int
    step: int
    slots: int


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
            row = y + 2 * (slot if down else slots - 1 - slot)
            node = nodes[index] if index < count else None
            if node is None:
                cells[(cx, row)] = "│"
            else:
                _paint(cells, cx - len(node) // 2, row, node)
            cells[(cx, row + 1)] = cells[(cx, row - 1)] = "│"
    for col in range(run.cols - 1):
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
        plan: _InputPlan | None = None,
        *,
        constant: Callable[[int, int], bool] | None = None,
    ) -> None:
        self.fold = fold
        self.answer_cols = answer_cols
        self.cells: dict[tuple[int, int], str] = {}
        self.truth_table, self.costs, self.tail = plan or _plan(truth_table)
        self.constant = (
            constant_span_test(self.truth_table) if constant is None else constant
        )
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
                _SnakeRun(entry, self.top[depth], self.fold, step, slots=slots),
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
                _SnakeRun(base, bus + 2, self.answer_cols, 6, slots=slots),
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
        super().__init__(
            "0" * size,
            1,
            1,
            ("0" * size, costs, 0),
            constant=lambda lo, hi: hi - lo == 1,
        )

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


def _banded(
    table: str, split: int, fold: int, *, plan: _InputPlan | None = None
) -> str:
    """Stack the ``2**split`` subtrees of ``table`` and join their buses.

    A top tree over the first ``split`` inputs sits at the upper east and
    drops one channel per subtree; channel ``b`` turns west into band ``b``,
    and the channels leave in band order so no rail crosses another.  Each
    band's bus runs west to a staircase column, turns down and joins the next
    band's bus, so one answer column serves all.
    """
    reduced, costs, tail = _plan(table) if plan is None else plan
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
    truth_table: str,
    fold: int = 1,
    answer_cols: int = 1,
    *,
    plan: _InputPlan | None = None,
    constant: Callable[[int, int], bool] | None = None,
) -> dict[tuple[int, int], str]:
    """Paint the decision tree onto a sparse ``(x, y) -> character`` grid.

    Leaves first on a fixed pitch, switches collapsed upwards and centred
    between their entry columns with rails to both.  Rows: ``( )``, rail,
    then per level its reads and switch, each followed by a rail; each leaf
    sets the register and drops onto a westward bus to the shared answer.
    ``fold`` (odd) snakes every read chain over that many columns, and
    ``answer_cols`` the answer column; ``1, 1`` is the plain tall drawing.
    """
    return _TreePainter(truth_table, fold, answer_cols, plan, constant=constant).paint()


def _flowchart_render(cells: dict[tuple[int, int], str]) -> str:
    """Flatten a painted cell map into the finished program text."""
    rows: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)
    for point in cells:
        rows[point[1]].append(point)
    output = []
    for y in range(max(rows) + 1):
        points = rows.get(y)
        if not points:
            output.append("")
            continue
        row = [" "] * (max(x for x, _ in points) + 1)
        for point in points:
            row[point[0]] = cells[point]
        output.append("".join(row).rstrip())
    return "\n".join(output)


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


def _deque_depth(levels: int) -> int:
    """Return ``k``: the deque holds ``2 ** k`` entries, ``levels`` read levels.

    Rails and ``[ >`` cost 12 cells a deque, the pops 24 a pair: minimised
    at ``k = (levels + 1) // 2``.
    """
    return max(1, (levels + 1) // 2)


def _flowchart_deque(truth_table: str, *, plan: _InputPlan | None = None) -> str:
    r"""Address one preloaded answer by walking the deque cursor to it.

    A deque holds ``2 ** k`` entries, ``k = ceil(m / 2)`` for ``m`` essential
    inputs (:func:`_deque_depth`): the even ones are pushed to the bottom, the
    odd to the top, so pair ``p`` sits ``p`` from both ends. On zero, the
    first ``m-k`` switches skip ``2 ** (m-k-1-level)`` deques; the next
    ``k-1`` pop ``2 ** (m-2-level)`` pairs from both ends. The final pick
    takes the end.

    Input ``p``'s value bit is stream bit ``8p``, so an ignored input costs
    only the eight ``/ /`` that skip it, and the deque holds the table over
    the essential inputs alone.  Trailing ignored inputs are read in each
    answer arm, ahead of its pop.
    """
    n = len(truth_table).bit_length() - 1
    if plan is None:
        used = essential_inputs(truth_table, n)
        plan = _plan(truth_table, used=used) if used else None
    elif constant_output(truth_table) is not None:
        plan = None
    if plan is None:
        # Read only the value bit of the final byte; earlier bytes are skipped.
        nodes = ["( )", *["/ /"] * (8 * (n - 1) + 1), _set(truth_table[0]), *_ANSWER]
        return "─".join(reversed(nodes))
    truth_table, skips, tail = plan
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

    m = len(skips)
    # A deque holds ``2 ** k`` entries, the even ones pushed to the bottom and
    # the odd to the top, so the pairs nest from the ends inward.
    deep = _deque_depth(m)
    west("( )")
    # ``\[ ]/`` and ``[ >`` both leave the register alone, so a run of equal
    # entries is set once and pushed however many times it is long.
    register: str | None = None
    for index, bit in enumerate(truth_table):
        if register != bit:
            west(_set(bit))
            register = bit
        west("/[ ]\\" if deep > 1 and index % 2 == 0 else "\\[ ]/")
        if (index + 1) % (1 << deep) == 0 and index + 1 < len(truth_table):
            west("[ >")

    for level in range(m - 1):
        for _ in range(skips[level]):
            west("/ /")
        switch = west("< >")
        # Travelling west a switch sends 1 straight on and 0 up, and the
        # rail west of the switch is the one-branch's bypass.  The top
        # levels step the cursor over deques; the next ``deep - 1`` pop
        # ``2 ** (m - 2 - level)`` pairs off both ends, so the last switch
        # still finds its pair at the ends.
        if level < m - deep:
            count, unit = 1 << (m - deep - 1 - level), "< ]─"
        else:
            count, unit = 1 << (m - 2 - level), "/{ }\\─\\{ }/─"
        junction = col - len(unit) * count + 1
        _paint(cells, switch, spine - 1, "─┐")
        _paint(cells, junction + 1, spine - 1, unit * count)
        _paint(cells, junction + 1, spine, "─" * (len(unit) * count))
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


def _banded_candidates(table: str, *, plan: _InputPlan | None = None) -> list[str]:
    """Return the banded drawing when ``m`` read levels leave room to split.

    Split ``(m - 3) // 2`` levels off the top, folded over 3 columns: the
    best split of random n=7..12 tables (area per row 1.6k-3.2k at n=7..12,
    against the flat tree's 4.6k at n=8 and 77k at n=12). That record's
    corpus is unspecified; [ablations.banded_balance] records the separate
    seed-4242 fleet and its 1.3k-1.7k range.
    """
    if plan is None:
        plan = _plan(table)
    split = (len(plan[1]) - 3) // 2
    return [_banded(table, split, 3, plan=plan)] if split > 0 else []


def _balance(table: str) -> str:
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
    plan = _plan(table)
    default = _flowchart_deque(table, plan=plan)
    constant = constant_span_test(plan[0])
    folded = (
        _flowchart_render(
            _flowchart_cells(table, fold, cols, plan=plan, constant=constant)
        )
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
    )
    return min(
        chain((default,), _banded_candidates(table, plan=plan), folded),
        key=balance_score,
    )


def flowchart_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.balance:
        return _balance(request.table)
    return flowchart(request.table, request.width)
