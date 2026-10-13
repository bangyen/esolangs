"""Boolean-function generator for Back."""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    grid_width,
    input_weights,
    layout_width,
    move_text,
    same_up_to_wrapping,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

_Node = tuple[int, int]
_Grid = dict[tuple[int, int], str]


def _back_walk(grid: _Grid, height: int, width: int) -> int | None:
    """Bound both outcomes of every skip; reject a reachable beam cycle."""
    start = (0, 1, 0, 1)
    costs: dict[tuple[int, int, int, int], int] = {}
    active: set[tuple[int, int, int, int]] = set()
    stack = [(start, False)]

    def successors(state: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
        row, col, dy, dx = state
        char = grid.get((row, col), " ")
        if char == "*":
            return []
        if char == "\\":
            dy, dx = dx, dy
        elif char == "/":
            dy, dx = -dx, -dy
        steps = (1, 2) if char == "+" else (1,)
        return [
            ((row + step * dy) % height, (col + step * dx) % width, dy, dx)
            for step in steps
        ]

    while stack:
        state, returning = stack.pop()
        if state in costs:
            continue
        children = successors(state)
        if returning:
            costs[state] = 1 + max((costs[child] for child in children), default=0)
            active.remove(state)
        else:
            if state in active:
                return None
            active.add(state)
            stack.append((state, True))
            stack.extend((child, False) for child in children if child not in costs)
    return costs[start]


def _back_bend(
    grid: _Grid,
    positions: dict[_Node, tuple[int, int]],
    shared: set[_Node],
    ids: list[list[int]],
    draw: Callable[[set[_Node]], tuple[_Grid, dict[_Node, tuple[int, int]]]],
) -> _Grid | None:
    """Route the first nonadjacent repeat through column one, if unobstructed."""
    route = None
    for level in range(len(ids) - 1):
        order = [node for node in positions if node[0] == level]
        owners: dict[int, list[_Node]] = {}
        for index in range(len(order) - 1, -1, -1):
            node = order[index]
            if node not in shared:
                matching = owners.get(ids[level + 1][2 * node[1] + 1], [])
                if matching and matching[-1] != order[index + 1]:
                    route = node, matching[-1]
            owners.setdefault(ids[level + 1][2 * node[1]], []).append(node)
        if route is not None:
            break
    if route is None:
        return None
    node, owner = route
    candidate, where = draw(shared | {node})
    if node not in where or owner not in where:
        return None
    sy, col = where[node]
    ty, _ = where[owner]
    sy += 1
    ty -= 1
    if sy >= ty:
        return None
    path = [(sy, c) for c in range(1, col + 1)]
    path += [(r, 1) for r in range(sy + 1, ty + 1)]
    path += [(ty, c) for c in range(2, col + 1)]
    if any(cell in candidate for cell in path):
        return None
    turns = {(sy, col): "/", (sy, 1): "/", (ty, 1): "\\", (ty, col): "\\"}

    def falls(
        cells: _Grid, nodes: dict[_Node, tuple[int, int]]
    ) -> dict[_Node, _Node | None]:
        height = max(r for r, _ in cells) + 1
        by_cell = {cell: key for key, cell in nodes.items()}
        targets = {}
        for key in shared:
            if key not in nodes:
                continue
            row, column = nodes[key]
            row = (row + 1) % height
            while (row, column) not in cells:
                row = (row + 1) % height
            targets[key] = by_cell.get((row, column))
        return targets

    candidate.update(turns)
    before = falls(grid, positions)
    if any(target is None for target in before.values()):
        return None
    after = falls(candidate, where)
    if any(after.get(key) != target for key, target in before.items() if key in where):
        return None
    return candidate


#: Finisher for a cell primed to 1: ``-`` flips it to 0, ``+`` is inert.
#: Both are one grid cell, so a run is the exact width of its program.
PAIR = ("-", "+")
_BACK_INPUT = TEMPLATE_CHAR
_WRAP_ROWS = 8
_MIRROR = {"/": "\\", "\\": "/"}


def _render(rows: list[dict[int, str]]) -> str:
    """Join sparse rows, gaps blank, each row only as long as its last cell."""
    return "\n".join(
        "".join(cells.get(x, " ") for x in range(max(cells, default=-1) + 1))
        for cells in rows
    )


def _place_load(
    grid: dict[tuple[int, int], str], units: list[str], height: int
) -> None:
    """Put the origin ``/`` and the load column, bottom up, into ``grid``."""
    grid[(0, 0)] = "/"
    for k, unit in enumerate(units):
        grid[(height - 1 - k, 0)] = unit


def _reflect_back(grid: dict[tuple[int, int], str], height: int, width: int) -> str:
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


def _descending_back(grid: dict[tuple[int, int], str], units: list[str]) -> str:
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
    r"""Build a Back template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    Width puts the loader above the tree, removing two entry columns.
    Unfitting parity tables use a one-column accumulator in answer cell n;
    earlier cells remain scratch rather than carrying the inputs.

    Back is a no-input grid language: a beam travels the grid and ``-`` flips
    the current tape bit, ``+`` steps the beam forward when the current bit
    is 0, ``<``/``>`` move the tape pointer, ``\`` reflects the beam down,
    and ``*`` halts printing the tape.  Each input is embedded once by
    filling its tape cell over two load rows: a constant ``-`` primes the
    cell to 1 for either bit, then the input's run finishes it -- ``+`` (inert on
    a set cell) for a one, ``-`` (flipping it back) for a zero.  So cells
    ``0..n-1`` hold the inputs and cell ``n`` is the answer cell.  Both
    bits cost the same two rows, so the height cannot leak an input.

    A decision node is ``+\>``: ``+`` tests the current tape bit (advancing
    the beam straight past the ``\`` when it is 0) and ``\`` reflects the
    beam down when it is 1, while ``>`` advances the tape pointer to the next
    input.  Both branches advance the pointer once, so a leaf at depth ``d``
    has the pointer at cell ``d``.  A leaf walks to cell ``n``, flips it with
    ``-`` when its value is 1, and halts.

    The load runs *down column 0* and the tree starts at column 1, so no row
    carries the load's width as indent.  A ``/`` at the origin does both
    turns: the beam starts heading right, the ``/`` sends it up and off the
    top edge onto the bottom row, it runs the load upward back to the origin,
    and the ``/`` -- now taking a beam heading up -- turns it right into the
    tree.  The load is written bottom-to-top, and the drawing is reflected
    for output, so the tree grows left and its triangular padding lands at
    line ends where it is stripped.  A two-row outer route converts Back's
    fixed eastward start into the westward entry the reflected root needs.

    The answer is the *value* of cell ``n``, which the halt dump prints;
    the head's position is not printed.

    A node whose one-subtree equals the zero-subtree of the next node on its
    level draws none: the beam falls down the column onto that node's mirror,
    the first cell below, and turns east into the zero side.  The column
    wraps, so the level's last node reaches its first the same way, from eight
    rows up.  At 6..12 essential inputs, the first nonadjacent repeat may
    bend through column 1. Admission preserves existing falls, reduces text
    and rectangular area, and bounds both outcomes of each skip. A seeded
    n=7 three-block control shrinks 1,267 to 1,156 characters and 1,560 to
    1,274 cells, executing all 128 inputs within 179 commands (bound 221).
    Unrestricted bends previously raised n=6/7 worst commands from 122/221
    to 154/306, past that bound.  Straight-fall area (rows x longest row), n=6/7:
    random -21.9% / -23.6%, tiled from two random blocks -17.5% / -35.8%,
    constant half 0% / -13.1%; n <= 5 is unchanged, the load column setting
    the height.  The wrap, over the next-node fall alone, n=8/9: tiled -9.7% /
    -6.6% of characters (-16.5% / -9.7% of area), random and constant half 0%.
    """
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
    # Bound the admission analysis; larger trees retain their existing scaling.
    if wrap and width is None and 6 <= levels <= 12:
        candidate = _back_ordered(
            table, tuple(range(levels)), weights=weights, wrap=True, bend=True
        )
        if len(candidate) < len(program) and len(candidate.splitlines()) * grid_width(
            candidate
        ) < len(program.splitlines()) * grid_width(program):
            program = candidate
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
class _BackDrawState:
    """Mutable state threaded through the tree emitter."""

    grid: _Grid
    where: dict[_Node, tuple[int, int]]
    next_row: int
    vertical: bool
    reserved: _Node | None
    shared: set[_Node]
    levels: int
    n: int
    truth_table: str
    constant: Callable[[int, int], bool]


def _back_leaf(
    state: _BackDrawState, level: int, value: str, row: int, col: int
) -> None:
    """Emit a leaf finisher at ``(row, col)``."""
    # Walk to cell n, flip it (starts 0) for a 1-leaf, halt.
    code = ">" * (state.n - level) + ("-" if value == "1" else "") + "*"
    if state.vertical:
        # Reserved DFS rows turn leaf finishers down without widening the tree.
        state.grid[(row, col)] = "\\"
        for k, ch in enumerate(code, 1):
            state.grid[(row + k, col)] = ch
        state.next_row = max(state.next_row, row + len(code) + 1)
    else:
        for k, ch in enumerate(code):
            state.grid[(row, col + k)] = ch


def _back_emit(
    state: _BackDrawState, level: int, lo: int, hi: int, row: int, col: int
) -> None:
    """Emit the subtree over rows ``[lo, hi)``, node mirror at ``(row, col)``."""
    if level == state.levels or state.constant(lo, hi):
        _back_leaf(state, level, state.truth_table[lo], row, col)
        return
    mid = lo + (hi - lo) // 2
    state.grid[(row, col)] = "+"
    state.grid[(row, col + 1)] = "\\"
    state.grid[(row, col + 2)] = ">"
    block = lo >> (state.levels - level)
    state.where[level, block] = (row, col + 1)
    _back_emit(state, level + 1, lo, mid, row, col + 3)  # zero (bit=0) straight
    if (level, block) in state.shared:
        # Keep one empty row for the bend before compacting later nodes.
        if (level, block) == state.reserved:
            state.next_row += 1
        return
    nrow = state.next_row
    state.next_row += 1
    state.grid[(nrow, col + 1)] = "\\"
    state.grid[(nrow, col + 2)] = ">"
    _back_emit(state, level + 1, mid, hi, nrow, col + 3)  # one (bit=1) child


def _back_draw(
    truth_table: str,
    levels: int,
    n: int,
    shared: set[_Node],
    constant: Callable[[int, int], bool],
    *,
    vertical: bool,
    reserved: _Node | None = None,
) -> tuple[_Grid, dict[_Node, tuple[int, int]]]:
    """Draw the tree; return its cells and each node's cell by (level, block).

    A node in ``shared`` draws no one-subtree: its mirror drops the beam down
    the column to the next mirror below, the zero-side entry of the next
    node on that level.
    """
    state = _BackDrawState(
        grid={},
        where={},
        next_row=1,
        vertical=vertical,
        reserved=reserved,
        shared=shared,
        levels=levels,
        n=n,
        truth_table=truth_table,
        constant=constant,
    )
    # Tree root at column 1, the beam arriving rightward.
    _back_emit(state, 0, 0, 2**levels, 0, 1)
    return state.grid, state.where


def _level_walk(
    order: list[int],
    level: int,
    block: int,
    levels: int,
    constant: Callable[[int, int], bool],
    k: int,
    shared: set[_Node],
) -> None:
    """Walk the tree in text order, appending level ``k``'s blocks to ``order``.

    One-subtrees of ``shared`` nodes are cut: their beam falls onto the next
    node's mirror instead of drawing a child.
    """
    size = 2 ** (levels - level)
    if level == levels or constant(block * size, (block + 1) * size):
        return
    if level == k:
        order.append(block)
    _level_walk(order, level + 1, 2 * block, levels, constant, k, shared)
    if (level, block) not in shared:
        _level_walk(order, level + 1, 2 * block + 1, levels, constant, k, shared)


def _back_level_order(
    k: int, shared: set[_Node], levels: int, constant: Callable[[int, int], bool]
) -> list[int]:
    """Return level ``k``'s nodes in text order, one-subtrees of ``shared`` cut."""
    order: list[int] = []
    _level_walk(order, 0, 0, levels, constant, k, shared)
    return order


def _back_plan(
    *,
    vertical: bool,
    truth_table: str,
    levels: int,
    n: int,
    wrap: bool,
    ids: list[list[int]],
    constant: Callable[[int, int], bool],
) -> set[_Node]:
    """Pick the nodes whose one-edge can fall onto an equal zero-side subtree.

    Level by level: a node qualifies when the next node on its level (in
    text order) has an equal zero subtree and that node's mirror is the
    first cell below it in the column.
    """
    shared: set[_Node] = set()
    for k in range(levels):
        order = _back_level_order(k, shared, levels, constant)
        # The last node's beam falls off the bottom and wraps to the top,
        # where the level's first mirror is the first in the column.  Its
        # walk is about the rows it saves, but only from eight rows up:
        # below that it is a few cells saved for a whole column walked.
        ring = wrap and 2 ** (levels - k - 1) >= _WRAP_ROWS
        follower = dict(pairwise([*order, *order[:1]] if ring else order))
        tried = {
            (k, a)
            for a, b in follower.items()
            if ids[k + 1][2 * a + 1] == ids[k + 1][2 * b]
        }
        if not tried:
            continue
        grid, where = _back_draw(
            truth_table, levels, n, shared | tried, constant, vertical=vertical
        )
        height = max(r for r, _ in grid) + 1
        column = 3 * k + 2
        owner = {cell: node for node, cell in where.items()}
        for _, a in tried:
            row = where[k, a][0] + 1
            while row < height and (row, column) not in grid:
                row += 1
            if ring and row == height:
                # Off the bottom the beam wraps to the top of the column.
                row = 0
                while (row, column) not in grid:
                    row += 1
            if owner.get((row, column)) == (k, follower[a]):
                shared.add((k, a))
    return shared


def _bend_command_limit(n: int) -> int:
    """Admission bound for a bent tree's worst-case command count.

    ``tree_rows`` budgets the rows the beam may walk in the bent tree: three
    quarters of the full ``2**n``-row tree plus the origin row.  The full
    limit is the tree-height bound ``max(tree_rows, 6 * n - 1)`` (the load
    column can set the height) plus the walk bound ``tree_rows`` again, plus
    ``3 * n`` for the entry/load turns and a six-command margin.  A bend is
    admitted only when ``bent_height + 5 + commands`` stays within it.
    """
    tree_rows: int = 3 * 2**n // 4 + 1
    return max(tree_rows, 6 * n - 1) + tree_rows + 3 * n + 6


def _back_ordered(
    truth_table: str,
    perm: tuple[int, ...],
    width: int | None = None,
    weights: list[int] | None = None,
    *,
    wrap: bool = False,
    bend: bool = False,
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

    # Reverse name order: the load is drawn bottom-up in column 0, so this
    # emits input 0 first.
    units = _back_load(list(range(n - 1, -1, -1)), cells, weights, levels, n)

    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)

    shared = _back_plan(
        vertical=False,
        truth_table=truth_table,
        levels=levels,
        n=n,
        wrap=wrap,
        ids=ids,
        constant=constant,
    )
    grid, positions = _back_draw(
        truth_table, levels, n, shared, constant, vertical=False
    )
    bent = None
    if bend and width is None and 6 <= levels <= 12:
        bent = _back_bend(
            grid,
            positions,
            shared,
            ids,
            lambda chosen: _back_draw(
                truth_table,
                levels,
                n,
                chosen,
                constant,
                vertical=False,
                reserved=next(iter(chosen - shared)),
            ),
        )

    if width is not None and width > 0:
        span = max(c for _, c in grid) + 3
        if span > width:
            down = _back_load(list(range(n)), cells, weights, levels, n)
            wide = _descending_back(grid, down)
            grid, _ = _back_draw(
                truth_table,
                levels,
                n,
                _back_plan(
                    vertical=True,
                    truth_table=truth_table,
                    levels=levels,
                    n=n,
                    wrap=wrap,
                    ids=ids,
                    constant=constant,
                ),
                constant,
                vertical=True,
            )
            tall = _descending_back(grid, down)
            return min((wide, tall), key=grid_width)

    # Height is max(tree 2**n, load units + 1).  Past n=3 load rows share with
    # tree rows; safe only because a run is one character for either bit.
    height = max(max(r for r, _ in grid) + 1, 1 + len(units))
    tree_width = max(c for _, c in grid) + 1
    # One '/' at the origin does both turns: right -> up off the top edge onto
    # the bottom row (toroidal wrap), up the load, then up -> right into the
    # tree at column 1.
    _place_load(grid, units, height)
    # No input row can instantiate to whitespace (a zero used to embed as a
    # blank, and the height revealed it).
    program = _reflect_back(grid, height, tree_width)
    if bent is not None:
        bent_height = max(max(r for r, _ in bent) + 1, 1 + len(units))
        bent_width = max(c for _, c in bent) + 1
        commands = _back_walk(bent, bent_height, bent_width + 2)
        limit = _bend_command_limit(n)
        # Five entry turns plus the full load column bound either bit value.
        if commands is not None and bent_height + 5 + commands <= limit:
            _place_load(bent, units, bent_height)
            candidate = _reflect_back(bent, bent_height, bent_width)
            if len(candidate) < len(program) and bent_height * (
                bent_width + 2
            ) < height * (tree_width + 2):
                return candidate
    return program


def _balance(table: str, default: str) -> str:
    """Compare the reflected tree, descending tree and parity column."""
    descending = back(table, max(1, grid_width(default) - 1))
    # The unshared layouts stay: sharing can leave a layout less square.
    plain = back(table, wrap=False)
    narrow = back(table, max(1, grid_width(plain) - 1), wrap=False)
    return min(default, descending, plain, narrow, back(table, 1), key=balance_score)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Rebuild a width-fitted grid at the template's own width."""
    return template == layout(layout_width(template)) or same_up_to_wrapping(
        template, plain
    )


LANGUAGE = Language(
    "Back",
    "back",
    category="tape_based",
    boolean=back,
    same_layout=_same_layout,
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
)
