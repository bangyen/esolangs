"""Boolean-function generator for COD (parameterized convention).

The harness fills the template's input runs, one program per combination;
the generator routes a fork/cascade decision tree.  COD does have an
input command (``...`` touching a top or bottom edge), but a reading
generator would have to route every input horizontally: this interpreter
treats each of the three dot cells as its own read.
"""

from itertools import zip_longest

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["cod"]


def _cod_reachable(n: int, k: int) -> tuple[set[int], set[int], set[int]]:
    """Combo-index contributions reachable after fork ``k`` (0 if ``k == 0``).

    ``(flat, plus_one, plus_weight)``: before fork ``k``, after its "continue"
    branch (``+1``, bookkeeping :func:`_cod_fork_box` consumes), and after
    "peel off" (``+ 2**(n-k)``).  Recursive in ``k``.
    """
    if not k:
        return {0}, {0}, {0}

    prev = _cod_reachable(n, k - 1)
    flat = prev[0] | prev[2]
    return (
        flat,
        {v + 1 for v in flat},
        {v + 2 ** (n - k) for v in flat},
    )


def _cod_gauntlet(vals: set[int]) -> str:
    """Build a gauntlet of ``(``/``<`` steps that survives only ``vals``.

    Each gap between sorted ``vals`` is a run of ``(`` then a ``<`` gate; a
    trailing ``)`` run restores the survivor to the maximum.
    """
    arr = [0, *sorted(vals)]
    res = ""
    for k in range(len(arr) - 1):
        diff = arr[k + 1] - arr[k]
        res += "(" * diff + "<"
    res += ")" * max(arr)
    return res


def _cod_fork_box(n: int, k: int) -> str:
    """Build a private, self-contained 5-row box that forks on bit ``k - 1``.

    A ``+`` fork: one branch continues through a net-zero gauntlet, the other
    peels off to a side row netting the bit's weight ``2**(n - k)``, both
    rejoining at a second ``+``.  Every box owns its cells, so boxes compose
    by concatenation (:func:`_cod_combine`) and no cod re-enters another
    box's cells from an unexpected direction (what blocked general ``n``; see
    :func:`cod`).  The leading ``?`` is the entry cell, replaced on joining.
    """
    vals = _cod_reachable(n, k)
    forward_gate = _cod_gauntlet(vals[1])
    side_gate = _cod_gauntlet(vals[0])
    forward_shaft = _cod_gauntlet(vals[2])[::-1]
    side_shaft = side_gate[::-1]
    weight_minus_one = ")" * (2 ** (n - k) - 1)

    forward_row = f"+ {forward_gate} {forward_shaft} +"
    side_row = f" {side_gate} {weight_minus_one} {side_shaft}"
    width = max(len(forward_row), len(side_row))
    forward_row = forward_row.rjust(width)
    side_row = side_row.rjust(width)

    # The two forks (entry and exit) sit on the forward row; the middle
    # wall row is open at those same columns, offset by one to account for
    # the west wall column the forward row itself does not have (it has
    # the entry marker there instead).
    fork_cols = [i + 1 for i, ch in enumerate(forward_row) if ch == "+"]
    middle_row = "".join(" " if c in fork_cols else "~" for c in range(width + 2))

    return "\n".join(
        [
            "~" * (width + 2),
            "?" + forward_row + " ",
            middle_row,
            "~" + side_row + "~",
            "~" * (width + 2),
        ],
    )


def _cod_leaf(n: int, k: int, bit: str) -> str:
    """Build the tail of leaf row ``k``: a gauntlet to 0, the answer, ``---``."""
    diff: int = 2**n - k - 1
    output = ")" if bit == "1" else " "
    return "(<" * diff + ")" * diff + f" {output} ---"


def _cod_cascade_row(n: int) -> str:
    """Build the cascade row's chain of ``+<(`` blocks, one per non-final leaf."""
    total: int = 2**n - 1
    return "  " + "+<(" * total


def _cod_tree(n: int, table: str) -> str:
    """Build the ``2**n`` leaf rows, each peeling off one combo's answer."""

    def row(k: int) -> str:
        output = _cod_leaf(n, k, table[k])
        prefix = "~~ " * (k + 1)
        return prefix + output + "\n" + prefix + "~" * len(output)

    total: int = 2**n - 1
    length = 3 * total + 10
    return (
        "~" * length
        + "\n"
        + "\n".join(row(k) for k in range(total))
        + "\n"
        + _cod_cascade_row(n)
        + " "
        + _cod_leaf(n, total, table[total])
        + "\n"
        + "~" * length
    )


def _cod_cascade(n: int, table: str) -> str:
    """Build the leaf cascade (Phase 2): stairstep gates down to each answer.

    With the combo index ``V`` as the cod's value, a chain of ``+<(`` blocks
    (:func:`_cod_cascade_row`) peels off one copy per step, and leaf ``k``'s
    gate chain fires iff ``V == k``.  Column 1 is a shaft feeding the index
    in from the boxes above (:func:`_cod_combine`).
    """
    tree_rows = _cod_tree(n, table).split("\n")

    # West wall: one column on the top and bottom rows, two on each leaf
    # row (the tree steps in a column per row); the first leaf row's new
    # cell is the shaft down from Phase 1, so it is water.
    first, *middle, last = tree_rows
    wrapped_middle = [("  " if i == 0 else "~ ") + row for i, row in enumerate(middle)]
    return "\n".join(["~" + first, *wrapped_middle, "~" + last])


def _cod_combine(blocks: list[str]) -> str:
    """Concatenate grid blocks left to right, padding shorter ones with blanks."""
    block_rows = [block.split("\n") for block in blocks]
    blanks = [" " * len(rows[0]) for rows in block_rows]
    combined_rows = zip_longest(*block_rows, fillvalue=None)
    return "\n".join(
        "".join(
            row if row is not None else blank
            for row, blank in zip(cells, blanks, strict=True)
        )
        for cells in combined_rows
    )


#: Each input's cell at its ``+`` fork: ``)`` increments; ``_`` acts only on
#: a cod moving *up* and is a no-op crossed sideways.  Both one cell,
#: neither blank (water would do, but a blank spells a bit as nothing).
PAIR = ("_", ")")

#: An input's run: one cell, the width of its setter.
_COD_RUN = TEMPLATE_CHAR * len(PAIR[0])


def _cod_cells(block: str) -> list[list[str]]:
    """Split ``block`` into rows of cells: one character each, a run's too."""
    return [list(row) for row in block.split("\n")]


# Five columns for a rotated box plus one for the riser that climbs back.
_COD_STRIDE = 6


def _cod_rotate_cw(block: str) -> list[str]:
    """Stand a block on end: ``new[c][H - 1 - r] = old[r][c]``.

    A fork box is five rows by up to 1200 columns beside a cascade of
    ``2 ** (n + 1) + 1`` rows, leaving 89% of the grid blank at eight
    inputs; rotated, a box is a vertical pipe.  Nothing needs rewriting:
    COD's ``+-)(<_`` are not directional (a cod is steered by walls), and
    only ``---`` prints and ``...`` reads are orientation-bound, which a
    box has neither of (contrast LaserFuck's mirrors).
    """
    rows = block.split("\n")
    height = len(rows)
    width = max(len(row) for row in rows)
    rows = [row.ljust(width) for row in rows]
    return [
        "".join(rows[height - 1 - r][c] for r in range(height)) for c in range(width)
    ]


def _cod_rotated(n: int, truth_table: str) -> str:
    """Build the program with phase 1 as rotated columns rather than one row.

    Each box is a pipe entered at the top of its column 3 and left at the
    bottom; a private corridor (down, east to a riser, north, east) joins
    it to the next.  No cell is re-entered from two directions, and every
    input's run lands on the same row in name order.
    """
    boxes = [_cod_rotate_cw(_cod_fork_box(n, k + 1)) for k in range(n - 1)]
    height = max(len(box) for box in boxes) + 2  # a top and a bottom corridor
    cascade_col = _COD_STRIDE * (n - 1)
    grid = [["~"] * cascade_col for _ in range(height)]

    for k, box in enumerate(boxes):
        base = _COD_STRIDE * k
        entry, riser = base + 3, base + 5
        for r, row in enumerate(box):
            for c, char in enumerate(row):
                grid[r + 1][base + c] = char
        for r in range(len(box) + 1, height - 1):
            grid[r][entry] = " "  # drop the exit column to the bottom corridor
        for c in range(entry, riser + 1):
            grid[height - 1][c] = " "  # bottom corridor, east to the riser
        # The last riser stops at row 1 to enter the cascade heading east;
        # the others carry on to the top corridor row.
        for r in range(0 if k < n - 2 else 1, height - 1):
            grid[r][riser] = " "
        if k < n - 2:
            for c in range(riser, base + _COD_STRIDE + 4):
                grid[0][c] = " "  # top corridor, east to the next entry

    for c in range(4):
        grid[0][c] = " "
    grid[0][0] = ">"

    cascade = _cod_cascade(n, truth_table).split("\n")
    cascade[1] = _COD_RUN + cascade[1][1:]
    # Pad with wall (as the interpreter does) so every ``---`` touches the
    # right edge; a short row's print would silently find nothing, and
    # blank padding would be water the cod escapes into.
    cells = [len(row) for row in cascade]
    cwidth = max(cells)
    cascade = [
        row + "~" * (cwidth - got) for row, got in zip(cascade, cells, strict=True)
    ]

    rows = [
        "".join(grid[r]) + (cascade[r] if r < len(cascade) else "~" * cwidth)
        for r in range(height)
    ]
    program = "\n".join(rows)
    for _ in range(n - 1):
        program = program.replace("?", _COD_RUN, 1)
    return program


def _cod_width(program: str) -> int:
    """Measure the program's widest row.

    A run is one cell, as its setter is, so this is every filled program's width.
    """
    return max(len(row) for row in program.split("\n"))


def _cod_turned(program: str) -> str:
    """Turn the program a quarter turn clockwise, re-attaching its prints.

    The join is wide and short (1218 x 129 at six inputs); turned, the width
    becomes the tallest block, the cascade at ``2 ** (n + 1) + 1``.  Only
    ``---`` is orientation-bound (it prints as a horizontal edge run, and
    turned it would be three ``-`` removals and a silent death), so each
    print gets a corridor: descend, meet a wall, west to a ``---`` at the
    left edge.  Corridors are laid in descending column order so they never
    cross.  A run is one cell like any other.
    """
    rows = _cod_cells(program)
    height = len(rows)
    width = max(len(row) for row in rows)
    grid = [row + [" "] * (width - len(row)) for row in rows]
    # Clockwise, so a cod swimming east ends up swimming south.
    turned = [[grid[height - 1 - j][i] for j in range(height)] for i in range(width)]
    columns = sorted(
        (
            height - 1 - r
            for r, row in enumerate(program.split("\n"))
            if row.rstrip().endswith("---")
        ),
        reverse=True,
    )
    for i in (width - 3, width - 2, width - 1):
        for column in columns:
            turned[i][column] = " "
    for column in columns:
        corridor = ["~"] * height
        corridor[0] = corridor[1] = corridor[2] = "-"
        for cell in range(3, column + 1):
            corridor[cell] = " "
        turned.append(corridor)
    turned.append(["~"] * height)
    return "\n".join("".join(row).rstrip() for row in turned)


def _cod_dead_box(names: list[int]) -> str:
    """Build a sealed block of ignored inputs' setters, which the cod never enters.

    A ``~`` wall on every side; a ``)`` inside increments nothing, so an
    ignored setter is free.  Stacked above or below rather than beside:
    :func:`_cod_combine` pads with spaces, which are open water.
    """
    inner = _COD_RUN * len(names)
    wall = "~" * (len(inner) + 2)
    return "\n".join([wall, "~" + inner + "~", wall])


def cod(truth_table: str, width: int | None = None) -> str:
    """Build a COD template for an ``n``-input Boolean function, any ``n >= 1``.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.
    ``width`` turns the drawing a quarter turn (:func:`_cod_turned`), so the
    width becomes the tallest block, the cascade at ``2 ** (n + 1) + 1``;
    under that the narrowest program is returned (four inputs 220 -> 33, six
    1236 -> 129).  Banding was tried and is strictly worse over all 576
    tables through four inputs (a fork box grows faster than the cascade).

    Two phases of private, self-contained blocks joined by concatenation.
    The ``n <= 3`` design this replaces fused the row and reused gauntlet
    cells for merges via a backwards "sacrificial retrace"; a merge cell
    could then be entered from west, south and east across steps, and the
    wiki's ``+`` rule excludes a different direction per entry, so a clean
    2-way fork becomes a 3-way one and cods accumulate.  ``n == 3`` never
    triggers it; nothing guaranteed ``n >= 4``.  A ``_``-gate tree was
    rejected for needing a seeded-randomness convention.

    Phase 1 assembles ``V = sum(bit_i * 2**(n-1-i))``: bits ``0..n-2`` each
    get a fork box (:func:`_cod_fork_box`); the last is a bare cell.  Phase
    2 (:func:`_cod_cascade`) peels copies down ``2**n - 1`` ``+<(`` blocks
    so leaf ``k`` fires iff ``V == k`` and prints its baked entry (``)`` for
    a one, nothing for a zero).  Exactly one line prints.
    """
    n = _validate_truth_table(truth_table)

    # The cascade is ``2**n - 1`` blocks whatever the table says, so
    # dropping an ignored input halves the program: build the reduced
    # table and park the rest in sealed boxes (:func:`_cod_dead_box`)
    # either side, keeping every run once in name order.
    used = essential_inputs(truth_table, n) or [0]
    # A gapped set (0 and 2, not 1) would break name order, so it is
    # widened to its span (Taglate declines instead).  Widening need not
    # pay -- the cascade grows as ``2**len(used)`` and a dead box saves one
    # cell -- so the reduced build is measured against the full one.
    used = list(range(used[0], used[-1] + 1))
    reduced = None
    if len(used) < n:
        core = cod(read_at(truth_table, used, n))
        ignored = [i for i in range(n) if i not in used]
        before = [i for i in ignored if i < used[0]]
        after = [i for i in ignored if i > used[-1]]
        parts = [_cod_dead_box(before)] if before else []
        parts.append(core)
        if after:
            parts.append(_cod_dead_box(after))
        reduced = "\n".join(parts)

    blocks = ["~~~\n~> \n~~~"]
    for k in range(n - 1):
        blocks.append(_cod_fork_box(n, k + 1).replace("?", _COD_RUN, 1))

    box_rows = _cod_cascade(n, truth_table).split("\n")
    box_rows[1] = _COD_RUN + box_rows[1][1:]
    blocks.append("\n".join(box_rows))

    full = _cod_combine(blocks)
    if width is not None and _cod_width(full) > width:
        # Two shapes to choose between, and the narrowest wins.  Banding
        # trades width for height a block at a time; *turning* trades the
        # whole drawing's width for its height at once, and since the
        # blocks are joined left to right that is the better trade -- the
        # width becomes the tallest block rather than the widest.
        return _cod_turned(full)
    # Three shapes now, and the shortest wins.  The rotated layout
    # (:func:`_cod_rotated`) overtakes the flat one at four inputs and pulls
    # away -- 1.29x there, 3.67x at eight -- but *loses* at three, where the
    # corridors cost more than the blank rows they remove, so this stays a
    # comparison rather than a replacement.
    candidates = [full]
    if reduced is not None:
        candidates.append(reduced)
    if n >= 2:
        candidates.append(_cod_rotated(n, truth_table))
    return min(candidates, key=len)


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"
