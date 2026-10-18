r"""Back Boolean program generator: a decision tree over a loaded tape.

A load column embeds each input once into its tape cell (a primer ``-``
plus the input's run, two rows for either bit, so the height cannot leak an
input); cells ``0..n-1`` hold the inputs, cell ``n`` the answer.  Each tree
node ``+\>`` tests the current cell (``+`` skips the ``\`` when it is 0,
``\`` reflects the beam down when it is 1, ``>`` advances); both branches
advance once, so a leaf at depth ``d`` has the pointer at cell ``d``.  It
walks to cell ``n``, flips it with ``-`` for a 1 and halts; the halt dump
prints the cell's value, not the head position.  Fall-through sharing reuses
an equal zero-side subtree, and ``width`` selects a descending layout (loader
above the tree, two entry columns fewer) or, for an unfitting parity table, a
one-column accumulator in cell ``n`` (earlier cells stay scratch).

Size:
    O(T) cells; n=8 random 1847: 2,443 chars, n=10 random 1847: 7,807 chars.

Decisions:
    A node whose one-subtree equals the zero-subtree of the next node on its
    level draws none: the beam falls down the column onto that node's mirror
    and turns east into the zero side.  Straight-fall area (rows x longest
    row), n=6/7: random -21.9% / -23.6%, tiled from two random blocks -17.5% /
    -35.8%, constant half 0% / -13.1%; n <= 5 is unchanged, the load column
    setting the height.  The column wraps, so the level's last node reaches
    its first from eight rows up; over the next-node fall alone, n=9 (200
    tables each): random and constant half 0%, eight blocks drawn from two
    random ones -10.2% of characters (-15.6% of area), from two 32-row blocks
    -2.9%.  A bend of the first nonadjacent repeat through column 1 was
    retired: it saved at most 2.7% of characters on average at n=7..10 (best
    single table 14.7%).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    grid_width,
    input_weights,
    move_text,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.back.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

_Node = tuple[int, int]
_Grid = dict[tuple[int, int], str]


#: Finisher for a cell primed to 1: ``-`` flips it to 0, ``+`` is inert.
#: Both are one grid cell, so a run is the exact width of its program.
PAIR = ("-", "+")
_BACK_INPUT = TEMPLATE_CHAR
_WRAP_ROWS = 8
_MIRROR = {"/": "\\", "\\": "/"}


def _extent(grid: _Grid) -> tuple[int, int]:
    """Return the rows and columns ``grid`` spans, counted from zero."""
    return (
        max(r for r, _ in grid) + 1,
        max(c for _, c in grid) + 1,
    )


def _render(rows: list[dict[int, str]]) -> str:
    """Join sparse rows, gaps blank, each row only as long as its last cell."""
    return "\n".join(
        "".join(cells.get(x, " ") for x in range(max(cells, default=-1) + 1))
        for cells in rows
    )


def _place_load(grid: _Grid, units: list[str], height: int) -> None:
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


def _reflect_back(grid: _Grid, height: int, width: int) -> str:
    r"""Reflect a Back template and route the fixed eastward start into it.

    ``grid`` maps ``(row, column)`` to a character; ``width`` is the widest
    row.  An input's run is one grid cell like every other character, so
    reflection reverses cells.  Only the beam mirrors swap; ``<`` and ``>``
    move the tape head and keep their meanings.  Rendered from the sparse
    cells, each row only as long as its last one, so the cost is the
    output's size rather than the bounding box (``2**n`` rows by ``4n``).
    """
    rows: list[dict[int, str]] = [{} for _ in range(height)]
    for (row, column), cell in grid.items():
        rows[row][width - column] = _MIRROR.get(cell, cell)

    # East, south, wrap west, north, west into the reflected root.  The two
    # extra columns touch only rows 0-1; tree padding is trailing and rstrips.
    rows[0][0] = rows[0][width + 1] = "\\"
    rows[1][0] = "/"
    rows[1][width + 1] = "\\"
    return _render(rows)


def _descending_back(grid: _Grid, units: list[str]) -> str:
    """Reflect the tree below a downward loader, without outer entry columns."""
    top = len(units) + 1
    last = max(column for _, column in grid)
    rows: dict[int, dict[int, str]] = {0: {last: "\\"}}
    for row, unit in enumerate(units, 1):
        rows[row] = {last: unit}
    rows[top] = {last: "/"}
    for (row, column), char in grid.items():
        rows.setdefault(top + row, {})[last - column] = _MIRROR.get(char, char)
    return _render([rows.get(y, {}) for y in range(max(rows) + 1)])


def _back_parity(truth_table: str, n: int) -> str | None:
    """Return a one-column parity accumulator, or None for another function."""
    bias = int(truth_table[0])
    parity = bytearray(len(truth_table))
    for row in range(1, len(truth_table)):
        parity[row] = parity[row >> 1] ^ (row & 1)
        if int(truth_table[row]) != parity[row] ^ bias:
            return None
    # The primer flips the accumulator. Zero flips it back; one keeps it,
    # and its possible skip consumes only the blank spacer, not the next bit.
    rows = ["\\", *(">" * n), *(["-"] if bias else [])]
    for _ in range(n):
        rows.extend(("-", _BACK_INPUT, " "))
    return "\n".join([*rows, "*"])


def back(truth_table: str, width: int | None = None, *, wrap: bool = True) -> str:
    """Build a Back template; ``truth_table`` has length ``2**n``, MSB first."""
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    if len(table) == 1:
        # A constant already folds to one leaf; it keeps every input.
        weights, table = [1] * n, truth_table
    levels = len(table).bit_length() - 1
    # A wrapped fall only removes rows; the shorter build, the plain one on a
    # tie, is the guard that no table grows.
    program = min(
        (
            _back_ordered(table, tuple(range(levels)), width, weights, wrap=w)
            for w in ((False, True) if wrap else (False,))
        ),
        key=len,
    )
    if width is not None and width > 0 and grid_width(program) > width:
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
    weights: list[int],
    levels: int,
    n: int,
) -> list[str]:
    """Load the inputs in ``order``, then open the answer cell and home.

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
    units: list[str] = []
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
    """One build's context: table geometry, its plan, and its draw state.

    A single context is threaded through both phases instead of passing the
    table, its geometry, and the plan from helper to helper: ``plan`` fills
    ``shared``, then ``draw`` fills ``grid``/``where`` reading that plan.
    """

    truth_table: str
    levels: int
    n: int
    constant: Callable[[int, int], bool]
    vertical: bool = False
    shared: set[_Node] = field(default_factory=set)
    wrap: bool = False
    ids: list[list[int]] = field(default_factory=list)
    grid: _Grid = field(default_factory=dict)
    where: dict[_Node, tuple[int, int]] = field(default_factory=dict)
    next_row: int = 1

    def leaf(self, level: int, value: str, row: int, col: int) -> None:
        """Emit a leaf finisher at ``(row, col)``."""
        # Walk to cell n, flip it (starts 0) for a 1-leaf, halt.
        code = ">" * (self.n - level) + ("-" if value == "1" else "") + "*"
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
        """Emit the subtree over rows ``[lo, hi)``, node mirror at ``(row, col)``."""
        if level == self.levels or self.constant(lo, hi):
            self.leaf(level, self.truth_table[lo], row, col)
            return
        mid = lo + (hi - lo) // 2
        self.grid[(row, col)] = "+"
        self.grid[(row, col + 1)] = "\\"
        self.grid[(row, col + 2)] = ">"
        block = lo >> (self.levels - level)
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
        self.emit(0, 0, 2**self.levels, 0, 1)
        return self.grid, self.where

    def level_events(
        self, events: list[int | None], level: int, block: int, k: int
    ) -> None:
        """Append what column ``3k + 2`` meets, in text order, to ``events``.

        A level-``k`` node is its block number; ``None`` is a horizontal leaf
        shallower than ``k`` whose finisher runs through the column (it ends
        at column ``2 * level + n + 1 + bit``).  One-subtrees of ``shared``
        nodes are cut, and nothing deeper than ``k`` reaches the column.
        Rows are numbered in this order, so a beam falling down the column
        meets the events in it.
        """
        size = 2 ** (self.levels - level)
        low = block * size
        if level == self.levels or self.constant(low, low + size):
            if not self.vertical and (
                2 * level + self.n + 1 + int(self.truth_table[low]) >= 3 * k + 2
            ):
                events.append(None)
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
            # The last node's beam falls off the bottom and wraps to the
            # top, where the level's first mirror is the first in the
            # column.  Its walk is about the rows it saves, but only from
            # eight rows up: below that it is a few cells saved for a whole
            # column walked.
            ring = self.wrap and 2 ** (self.levels - k - 1) >= _WRAP_ROWS
            follower = dict(pairwise([*order, *order[:1]] if ring else order))
            landing = dict(pairwise([*events, *events[:1]] if ring else events))
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
    weights: list[int] | None = None,
    *,
    wrap: bool = False,
) -> str:
    r"""Build one Back template, loading its inputs in ``perm`` order.

    ``truth_table`` is already permuted, so row indices are in the permuted
    frame; ``perm`` only picks the cell each input loads into.

    A node tests the current cell, *then* advances, so level ``k`` tests cell
    ``k`` and input ``perm[k]`` must load there -- one cell lower than
    another language's halls and a raster one's ``>#v)``, which test cell ``k + 1``.
    Getting it wrong computes a different function.

    The load runs the inputs in name order (run k *is* input k) and walks the
    pointer to cell ``perm.index(i)``, the inverse permutation; reading
    ``perm`` forward computes a different function.  Filling in cell order
    needs no walk and screens 12.0% against 9.15% here, but breaks name
    order.  The walk is ``4n - 2`` moves, 10 of the 236 characters at n=3.
    A ``-``/run pair is never split, so both bits still cost two rows.

    ``weights`` names the stream inputs, zero for an ignored one: the table
    indexes the rest, and the answer cell stays at the stream's input count.
    An ignored input's run lands on the empty cell the next load fills and
    a ``-`` follows it: a zero's ``-`` sets the cell and the ``-`` clears it,
    a one's ``+`` meets the empty cell and skips the ``-``.  Two rows, no
    walk, and the cell is empty again.
    """
    levels = _validate_truth_table(truth_table)
    if weights is None:
        weights = [1] * levels
    n = len(weights)

    # Level c tests cell c and input perm[c], so input i lives at cell
    # perm.index(i).
    essential = [i for i, weight in enumerate(weights) if weight]
    cells = [levels] * n
    for level, i in enumerate(perm):
        cells[essential[i]] = level

    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)

    def build(*, vertical: bool) -> _Grid:
        """Plan then draw one layout, both phases sharing one context."""
        context = _BackContext(
            truth_table=truth_table,
            levels=levels,
            n=n,
            constant=constant,
            vertical=vertical,
            wrap=wrap,
            ids=ids,
        )
        context.plan()
        return context.draw()[0]

    grid = build(vertical=False)
    if width is not None and width > 0 and max(c for _, c in grid) + 3 > width:
        down = _back_load(list(range(n)), cells, weights, levels, n)
        wide = _descending_back(grid, down)
        tall = _descending_back(build(vertical=True), down)
        return min((wide, tall), key=grid_width)

    # Reverse name order: the load is drawn bottom-up in column 0, so this
    # emits input 0 first.
    units = _back_load(list(range(n - 1, -1, -1)), cells, weights, levels, n)
    # Height is max(tree 2**n, load units + 1).  Past n=3 load rows share with
    # tree rows; safe only because a run is one character for either bit.
    rows, tree_width = _extent(grid)
    height = max(rows, 1 + len(units))
    # One '/' at the origin does both turns: right -> up off the top edge onto
    # the bottom row (toroidal wrap), up the load, then up -> right into the
    # tree at column 1.
    _place_load(grid, units, height)
    # No input row can instantiate to whitespace.
    return _reflect_back(grid, height, tree_width)


def _balance(table: str, default: str) -> str:
    """Compare the default with the parity column; other layouts never won."""
    return min(default, back(table, 1), key=balance_score)


LANGUAGE = Language(
    "Back",
    "back",
    category="tape_based",
    boolean=back,
    split=True,
    contract=BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n, past the n input cells",
    ),
    balance=_balance,
    no_wrap="the beam path and embedded input occupy fixed grid coordinates",
    empty_program="Back program cannot be empty",
    example=Example(pair=PAIR, expected="0 1 0"),
    proof_execution=(execution, True, (3, 5, 6)),
)
