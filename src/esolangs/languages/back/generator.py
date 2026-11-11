r"""Back Boolean program generator: a decision tree over a loaded tape.

A load column embeds each input once, with a primer/run pair of fixed height.
The last tested input is held in answer cell ``n``; earlier tested cells feed
``+\>`` branches. Equal halves advance without a test. Pair leaves then
preserve, complement, clear or set the held bit. The halt dumps cell ``n`` as
the answer; earlier cells are input storage or scratch, not a preserved input
copy. Fall-through sharing and the H-tree fold operate on this shorter tree.
Width requests retain the descending layout or one-column full parity reader.

Size:
    O(T) cells; n=8 constant zero: 25 chars; n=8 random 1847: 2,000 chars,
    n=10 random 1847: 12,341 chars.
    Area, rows x longest row: the comb is at most (3n+5)max(6n+1,T/2).
    The fold's limit is 15.625T; derived Rudin-Shapiro witnesses attain the caps.

Decisions:
    Popcount-symmetric tables reverse the comb's input cells: the drawing
    stays fixed and the loader walk shortens ([ablations.symmetric_reverse_loader]).
    A node whose one-subtree equals the zero-subtree of the next node on its
    level draws none: the beam falls down the column onto that node's mirror
    and turns east into the zero side.  Straight-fall area: see
    [ablations.fall_through_sharing]; n <= 5 is unchanged, the load column
    setting the height.  A wrap of the level's last node onto its first
    (from eight rows up) was retired: 0.0% by area and by chars on random
    tables and on parity, majority, and/or and a threshold at n=7..12
    ([ablations.wrap_race]).  The fold replaces the comb only when its area is
    smaller (ties keep the comb): from n=7, on tables whose one-edges share
    little ([ablations.htree_fold]).  It spends characters, up to its area,
    for area.  ``balance=True`` also races the fold against the comb by
    squareness ([ablations.balance_htree]), at comb bases 2..6
    ([ablations.balance_comb_base]).  A bend of the first nonadjacent
    repeat through column 1 was retired: it saved at most 2.7% of characters
    on average at n=7..10 (best single table 14.7%).  A complementing loader
    (rows ``(INPUT, "+")``) under the reversed table was not shipped: nor/or
    area 29-33% off at n=8 only, under 8% at n=10 and 0% at n=9, 11, 12.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.algebraic import parity_bias
from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_rank,
    grid_width,
    input_weights,
    move_text,
    subtree_ids,
)
from esolangs.generation.lookup import symmetric_outputs
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
    layout_tokens,
)
from esolangs.generation.wrap import balance_score

_Node = tuple[int, int]
_Grid = dict[tuple[int, int], TemplateToken]


#: Finisher for a cell primed to 1: ``-`` flips it to 0, ``+`` is inert.
#: Both are one grid cell, so a run is the exact width of its program.
#: Pair leaves act on the input bit already held in the answer cell.
_PAIR_FINISHERS = {"01": "*", "10": "-*", "00": "+-*", "11": "+--*"}
_BACK_INPUT = InputSlot(1)
#: Subtrees this short stay combs; taller ones fold (25-28 cells per leaf).
_FOLD_BASE = 5
#: Comb bases the balance race folds at (inclusive); the default fold uses 5.
_BALANCE_BASES = (2, 6)
_MIRROR: dict[TemplateToken, TemplateToken] = {"/": "\\", "\\": "/"}


def _extent(grid: _Grid) -> tuple[int, int]:
    """Return the rows and columns ``grid`` spans, counted from zero."""
    return (
        max(r for r, _ in grid) + 1,
        max(c for _, c in grid) + 1,
    )


def _render(rows: list[dict[int, TemplateToken]]) -> TemplateLayout:
    """Join sparse rows and record their input cells in reading order."""
    lines: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for cells in rows:
        line = [" "] * (max(cells, default=-1) + 1)
        slots = []
        for column, cell in cells.items():
            if isinstance(cell, InputSlot):
                slots.append(column)
                line[column] = TEMPLATE_CHAR
            else:
                line[column] = cell
        spans.extend((offset + column, offset + column + 1) for column in sorted(slots))
        lines.append("".join(line))
        offset += len(line) + 1
    return TemplateLayout("\n".join(lines), tuple(spans))


def _place_load(grid: _Grid, units: list[TemplateToken], height: int) -> None:
    """Put the origin ``/`` and the load column, bottom up, into ``grid``."""
    # The load runs down column 0 and the tree starts at column 1, so no row
    # carries the load's width as indent.  The beam starts heading right; the
    # ``/`` sends it up and off the top edge onto the bottom row, it runs the
    # load upward back to the origin, and the ``/`` turns it right into the
    # tree.  The drawing is reflected for output, so the tree grows left and
    # its triangular padding lands at line ends where it is stripped.
    grid[(0, 0)] = "/"
    for k, unit in enumerate(units):
        grid[(height - 1 - k, 0)] = unit


def _reflect_back(grid: _Grid, height: int, width: int) -> TemplateLayout:
    r"""Reflect a Back template and route the fixed eastward start into it.

    ``grid`` maps ``(row, column)`` to a character; ``width`` is the widest
    row.  An input's run is one grid cell like every other character, so
    reflection reverses cells.  Only the beam mirrors swap; ``<`` and ``>``
    move the tape head and keep their meanings.  Rendered from the sparse
    cells, each row only as long as its last one, so the cost is the
    output's size rather than the full height-by-width bounding box.
    """
    rows: list[dict[int, TemplateToken]] = [{} for _ in range(height)]
    for (row, column), cell in grid.items():
        rows[row][width - column] = _MIRROR.get(cell, cell)

    # East, south, wrap west, north, west into the reflected root.  The two
    # extra columns touch only rows 0-1; tree padding is trailing and rstrips.
    rows[0][0] = rows[0][width + 1] = "\\"
    rows[1][0] = "/"
    rows[1][width + 1] = "\\"
    return _render(rows)


def _descending_back(grid: _Grid, units: list[TemplateToken]) -> TemplateLayout:
    """Reflect the tree below a downward loader, without outer entry columns."""
    top = len(units) + 1
    last = max(column for _, column in grid)
    rows: dict[int, dict[int, TemplateToken]] = {0: {last: "\\"}}
    for row, unit in enumerate(units, 1):
        rows[row] = {last: unit}
    rows[top] = {last: "/"}
    for (row, column), char in grid.items():
        rows.setdefault(top + row, {})[last - column] = _MIRROR.get(char, char)
    return _render([rows.get(y, {}) for y in range(max(rows) + 1)])


def _back_parity(truth_table: str, n: int) -> TemplateLayout | None:
    """Return a one-column parity accumulator, or None for another function."""
    bias = parity_bias(truth_table)
    if bias is None:
        return None
    # The primer flips the accumulator. Zero flips it back; one keeps it,
    # and its possible skip consumes only the blank spacer, not the next bit.
    rows: list[TemplateToken] = ["\\", *(">" * n), *(["-"] if bias else [])]
    for _ in range(n):
        rows.extend(("-", _BACK_INPUT, " "))
    return layout_tokens([*rows, "*"], 1)


def _back_htree(
    table: str, weights: Sequence[int], base: int = _FOLD_BASE
) -> TemplateLayout:
    r"""Fold the decision tree into an H-tree of combs, under a row of load.

    A subtree of at most ``base`` levels is the plain comb (``+\>``
    chains, one row per one-edge).  A taller node is ``+ / >`` on row ``m`` of
    its rectangle, entered heading east: the zero side skips the mirror, runs
    on and turns south into the zero-child below; a one turns north, runs a
    wire along row 0 and drops into the one-child above.  Both children are
    entered heading south (a transposed frame), so orientation alternates per
    level and a rectangle is ``3 + max(H0, H1)`` wide and ``W0 + W1 + 2``
    tall: area O(T).  The load runs along row 0 and turns south into the
    transposed root.  Every wire crosses only blank cells, so the beam
    executes nothing off its path.
    """
    levels = len(table).bit_length() - 2
    n = len(weights)
    essential = [i for i, weight in enumerate(weights) if weight]
    cells = [levels] * n
    for level, i in enumerate(essential):
        cells[i] = n if level == levels else level
    units = _back_load(list(range(n)), cells, weights, levels, n)
    ids = subtree_ids(table)

    def leaf(level: int, lo: int) -> bool:
        return level == levels or ids[level][lo >> (levels - level + 1)] < 2

    # (width, height, entry row) of a subtree drawn heading east from its
    # west edge; a comb block enters at its top-left.
    dims: dict[_Node, tuple[int, int, int]] = {}

    def measure(level: int, lo: int) -> tuple[int, int, int]:
        if leaf(level, lo):
            box = (n - level + len(_PAIR_FINISHERS[table[lo : lo + 2]]), 1, 0)
        else:
            half = 1 << (levels - level)
            block = lo // (2 * half)
            if ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]:
                w, h, entry = measure(level + 1, lo)
                box = (1 + w, h, entry)
                dims[level, lo] = box
                return box
            w0, h0, _ = measure(level + 1, lo)
            w1, h1, _ = measure(level + 1, lo + half)
            if levels - level <= base:
                box = (3 + max(w0, w1), h0 + h1, 0)
            else:
                box = (3 + max(h0, h1), w0 + w1 + 2, w1 + 1)
        dims[level, lo] = box
        return box

    width, _, entry = measure(0, 0)
    out: _Grid = {}

    def emit(level: int, lo: int, row0: int, col0: int, *, swap: bool) -> None:
        """Draw a subtree whose frame maps (r, c) to the grid, transposed or not."""

        def put(r: int, c: int, char: str) -> None:
            out[row0 + (c if swap else r), col0 + (r if swap else c)] = char

        def sub(child: int, r: int, c: int, *, turn: bool) -> None:
            """Draw a child with its corner at (r, c), turned to enter south."""
            at = (row0 + c, col0 + r) if swap else (row0 + r, col0 + c)
            emit(level + 1, child, *at, swap=swap != turn)

        if leaf(level, lo):
            code = ">" * (n - level) + _PAIR_FINISHERS[table[lo : lo + 2]]
            for k, char in enumerate(code):
                put(0, k, char)
            return
        half = 1 << (levels - level)
        block = lo // (2 * half)
        if ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]:
            put(dims[level + 1, lo][2], 0, ">")
            sub(lo, 0, 1, turn=False)
            return
        _, _, m = dims[level, lo]
        _, h0, m0 = dims[level + 1, lo]
        _, _, m1 = dims[level + 1, lo + half]
        if levels - level <= base:
            # Comb: the zero side runs on, the one side starts h0 rows down.
            for c, char in enumerate("+\\>"):
                put(0, c, char)
            put(h0, 1, "\\")
            put(h0, 2, ">")
            sub(lo, 0, 3, turn=False)
            sub(lo + half, h0, 3, turn=False)
            return
        for c, char in enumerate("+/>"):
            put(m, c, char)
        put(m, 3 + m0, "\\")
        put(m - 1, 1, ">")
        put(0, 1, "/")
        put(0, 3 + m1, "\\")
        sub(lo, m + 1, 3, turn=True)
        sub(lo + half, 1, 3, turn=True)

    # Root transposed: its entry cell is (0, entry) heading south.  Row 0
    # carries the load, then a mirror above the entry turns the beam down.
    left = max(0, len(units) - entry)
    emit(0, 0, 1, left, swap=True)
    out.update({(0, k): unit for k, unit in enumerate(units)})
    out[0, left + entry] = "\\"
    rows: list[dict[int, TemplateToken]] = [{} for _ in range(1 + width)]
    for (r, c), char in out.items():
        rows[r][c] = char
    return _render(rows)


def back(truth_table: str, width: int | None = None) -> str:
    """Build a Back template; ``truth_table`` has length ``2**n``, MSB first."""
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    if len(table) == 1:
        # [ablations.constant_table_audit_20261101]: each run clears cell 0.
        units = [*(_BACK_INPUT, "-") * n, *(">" * n)]
        units += (["-"] if table == "1" else []) + ["*"]
        flat = layout_fragments(units)
        if width is None or width >= len(flat.source):
            return flat
        return layout_tokens(["\\", *units], 1)
    levels = len(table).bit_length() - 1
    order = tuple(range(levels))
    if width is None and symmetric_outputs(table, levels) is not None:
        # Popcount functions are invariant under reversal. The same comb then
        # needs a shorter loader walk ([ablations.symmetric_reverse_loader]).
        order = tuple(reversed(order))
    program = _back_ordered(table, order, width, weights)
    if width is None and len(table) > 1 << _FOLD_BASE:
        program = min(
            program,
            _back_htree(table, weights),
            key=lambda layout: grid_rank(layout.source),
        )
    if width is not None and width > 0 and grid_width(program.source) > width:
        parity = _back_parity(truth_table, n)
        if parity is not None:
            return parity
    return program


def _back_pointer_walk(frm: int, to: int) -> list[str]:
    """Move the pointer from cell ``frm`` to cell ``to``, one move per row."""
    return list(move_text(frm, to, ">", "<"))


def _back_load(
    order: list[int],
    cells: list[int],
    weights: Sequence[int],
    levels: int,
    n: int,
) -> list[TemplateToken]:
    """Load the inputs in ``order``, then visit the answer cell and home.

    ``cells[i]`` is the tape cell input ``i`` loads into and ``weights[i]``
    is zero for an ignored input.
    """
    # An ignored input borrows the cell loaded after it, or a spare one.
    borrowed = dict(enumerate(cells))
    spare = levels
    for i in reversed(order):
        if weights[i]:
            spare = cells[i]
        borrowed[i] = spare
    units: list[TemplateToken] = []
    at = 0
    for i in order:
        # Primer '-' then the run, one row each (the beam reads one cell
        # per row).  Bit on the trailing row so every load row executes;
        # the walk goes before the pair, never between, or the height
        # leaks the bit.
        units.extend(_back_pointer_walk(at, borrowed[i]))
        units.extend(("-", _BACK_INPUT) if weights[i] else (_BACK_INPUT, "-"))
        at = borrowed[i]
    units.extend(_back_pointer_walk(at, n))
    units.extend("<" * n)
    return units


@dataclass
class _BackContext:
    """One build's tested levels (one less than the table), plan and draw state.

    A single context is threaded through both phases instead of passing the
    table, its geometry, and the plan from helper to helper: ``plan`` fills
    ``shared``, then ``draw`` fills ``grid``/``where`` reading that plan.
    """

    truth_table: str
    levels: int
    n: int
    vertical: bool = False
    shared: set[_Node] = field(default_factory=set)
    ids: Sequence[Sequence[int]] = field(default_factory=list)
    grid: _Grid = field(default_factory=dict)
    where: dict[_Node, tuple[int, int]] = field(default_factory=dict)
    next_row: int = 1

    def leaf(self, level: int, value: str, row: int, col: int) -> None:
        """Emit a leaf finisher at ``(row, col)``."""
        # Walk to the held input; the pair finisher computes its unary function.
        code = ">" * (self.n - level) + _PAIR_FINISHERS[value]
        if self.vertical:
            # Reserved DFS rows turn leaf finishers down without widening the tree.
            self.grid[(row, col)] = "\\"
            for k, ch in enumerate(code, 1):
                self.grid[(row + k, col)] = ch
            self.next_row = max(self.next_row, row + len(code) + 1)
        else:
            for k, ch in enumerate(code):
                self.grid[(row, col + k)] = ch

    def emit(self, level: int, lo: int, hi: int, row: int, col: int) -> None:
        """Emit rows ``[lo, hi)``; pass wires retain the fall columns' alignment."""
        if level == self.levels or self.ids[level][lo // (hi - lo)] < 2:
            self.leaf(level, self.truth_table[lo : lo + 2], row, col)
            return
        mid = lo + (hi - lo) // 2
        block = lo // (hi - lo)
        # Canonical equal halves do not test or draw a one-edge.
        if self.ids[level + 1][2 * block] == self.ids[level + 1][2 * block + 1]:
            self.grid[row, col] = ">"
            self.emit(level + 1, lo, mid, row, col + 3)
            return
        self.grid[(row, col)] = "+"
        self.grid[(row, col + 1)] = "\\"
        self.grid[(row, col + 2)] = ">"
        self.where[level, block] = (row, col + 1)
        self.emit(level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight
        if (level, block) in self.shared:
            return
        nrow = self.next_row
        self.next_row += 1
        self.grid[(nrow, col + 1)] = "\\"
        self.grid[(nrow, col + 2)] = ">"
        self.emit(level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child

    def draw(self) -> tuple[_Grid, dict[_Node, tuple[int, int]]]:
        """Draw the tree; return its cells and each node's cell by (level, block).

        A node in ``shared`` draws no one-subtree: its mirror drops the beam
        down the column to the next mirror below, the zero-side entry of the
        next node on that level.
        """
        self.grid, self.where, self.next_row = {}, {}, 1
        # Tree root at column 1, the beam arriving rightward.
        self.emit(0, 0, len(self.truth_table), 0, 1)
        return self.grid, self.where

    def level_events(
        self, events: list[int | None], level: int, block: int, k: int
    ) -> None:
        """Append what column ``3k + 2`` meets, in text order, to ``events``.

        A level-``k`` node is its block number; ``None`` is a horizontal leaf
        shallower than ``k`` whose finisher runs through the column (it ends
        at column ``2 * level + n + len(finisher)``).  One-subtrees of ``shared``
        nodes are cut, and nothing deeper than ``k`` reaches the column.
        Rows are numbered in this order, so a beam falling down the column
        meets the events in it.
        """
        size = 2 ** (self.levels + 1 - level)
        low = block * size
        if level == self.levels or self.ids[level][block] < 2:
            if not self.vertical and (
                2 * level
                + self.n
                + len(_PAIR_FINISHERS[self.truth_table[low : low + 2]])
                >= 3 * k + 2
            ):
                events.append(None)
            return
        if self.ids[level + 1][2 * block] == self.ids[level + 1][2 * block + 1]:
            if level < k:
                self.level_events(events, level + 1, 2 * block, k)
            return
        if level == k:
            events.append(block)
            return
        self.level_events(events, level + 1, 2 * block, k)
        if (level, block) not in self.shared:
            self.level_events(events, level + 1, 2 * block + 1, k)

    def plan(self) -> set[_Node]:
        """Pick the nodes whose one-edge can fall onto an equal zero-side subtree.

        Level by level: a node qualifies when the next node on its level (in
        text order) has an equal zero subtree and its beam, falling down
        column ``3k + 2``, meets that node's mirror before anything else.
        That is decided from the walk's order alone (``level_events``), not
        by drawing.
        """
        for k in range(self.levels):
            events: list[int | None] = []
            self.level_events(events, 0, 0, k)
            order = [event for event in events if event is not None]
            follower = dict(pairwise(order))
            landing = dict(pairwise(events))
            self.shared.update(
                (k, a)
                for a, b in follower.items()
                if self.ids[k + 1][2 * a + 1] == self.ids[k + 1][2 * b]
                and landing[a] == b
            )
        return self.shared


def _back_ordered(
    truth_table: str,
    perm: tuple[int, ...],
    width: int | None = None,
    weights: Sequence[int] | None = None,
) -> TemplateLayout:
    r"""Build one Back template, loading its inputs in ``perm`` order.

    ``truth_table`` is already permuted, so row indices are in the permuted
    frame; ``perm`` only picks the cell each input loads into.

    A node tests the current cell, *then* advances, so level ``k`` tests cell
    ``k`` and input ``perm[k]`` must load there, except the held final bit.
    Getting it wrong computes a different function.

    The load runs the inputs in name order (run k *is* input k) and walks the
    pointer to cell ``perm.index(i)`` (the inverse), or cell ``n`` for the
    final selector; reading ``perm`` forward computes a different function.
    Filling in cell order would reorder the slots. With all inputs essential
    and identity order, the reflected loader walks ``4n`` moves (``2n`` for one
    input); reversal shortens it to ``2n``. All walks precede their input pair.
    A ``-``/run pair is never split, so both bits still cost two rows.

    ``weights`` names the stream inputs, zero for an ignored one: the table
    indexes the rest, and the answer cell stays at the stream's input count.
    An ignored input's run lands on the empty cell the next load fills and
    a ``-`` follows it: a zero's ``-`` sets the cell and the ``-`` clears it,
    a one's ``+`` meets the empty cell and skips the ``-``. Two fixed rows,
    with the borrowed cell empty again.
    """
    levels = _validate_truth_table(truth_table)
    if weights is None:
        weights = [1] * levels
    n = len(weights)

    # Invert the input order; the final selector is held in the answer cell.
    essential = [i for i, weight in enumerate(weights) if weight]
    cells = [levels] * n
    for level, i in enumerate(perm):
        # [ablations.answer_cell_preload_20261102]: the final bit is a leaf input.
        cells[essential[i]] = n if level == levels - 1 else level

    ids = subtree_ids(truth_table)

    def build(*, vertical: bool) -> _Grid:
        """Plan then draw one layout, both phases sharing one context."""
        context = _BackContext(
            truth_table=truth_table,
            levels=levels - 1,
            n=n,
            vertical=vertical,
            ids=ids,
        )
        context.plan()
        return context.draw()[0]

    grid = build(vertical=False)
    if width is not None and width > 0 and max(c for _, c in grid) + 3 > width:
        down = _back_load(list(range(n)), cells, weights, levels - 1, n)
        # The vertical layout was strictly narrower than the horizontal one on
        # all 6,892 width builds (tables n<=8, widths 1-1000); only it is built.
        return _descending_back(build(vertical=True), down)

    # Reverse name order: the load is drawn bottom-up in column 0, so this
    # emits input 0 first.
    units = _back_load(list(range(n - 1, -1, -1)), cells, weights, levels - 1, n)
    # Height is max(tree rows, load units + 1).  Past n=3 load rows share with
    # tree rows; safe only because a run is one character for either bit.
    rows, tree_width = _extent(grid)
    height = max(rows, 1 + len(units))
    # One '/' at the origin does both turns: right -> up off the top edge onto
    # the bottom row (toroidal wrap), up the load, then up -> right into the
    # tree at column 1.
    _place_load(grid, units, height)
    # No input row can instantiate to whitespace.
    return _reflect_back(grid, height, tree_width)


def _balance(table: str, default: TemplateLayout) -> TemplateLayout:
    """Compare the default, one column and the folded tree at each comb base.

    The comb wins area at n=8 (140 x 29) but the tree is squarer (63 x 80).
    A base moves the fold's shape by a factor of two per level of parity, so
    the even arities reach 2:1 only at another base (n=8: 46 x 102 at base 6).
    """
    candidates = [default, _layout(table, 1)]
    weights, reduced = input_weights(table, _validate_truth_table(table))
    candidates.extend(
        _back_htree(reduced, weights, base)
        for base in range(_BALANCE_BASES[0], _BALANCE_BASES[1] + 1)
        if len(reduced) > 1 << base
    )
    return min(candidates, key=lambda layout: balance_score(layout.source))


def back_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def back_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Balance the native layouts while preserving their slot positions."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    return _balance(request.table, request.source)
