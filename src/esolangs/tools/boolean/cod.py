r"""Boolean-function generator for COD (parameterized convention)."""

import re
from itertools import zip_longest

from esolangs.tools.boolean.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["cod"]


def _cod_reachable(n: int, k: int) -> tuple[set[int], set[int], set[int]]:
    r"""Combo-index contributions reachable after fork ``k`` (0 if ``k ==."""
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
    r"""Build a gauntlet of ``(``/``<`` steps that survives only ``vals``."""
    arr = [0, *sorted(vals)]
    res = ""
    for k in range(len(arr) - 1):
        diff = arr[k + 1] - arr[k]
        res += "(" * diff + "<"
    res += ")" * max(arr)
    return res


def _cod_fork_box(n: int, k: int) -> str:
    r"""Build a private, self-contained 5-row box that forks on bit ``k -."""
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

    # The two forks (entry and.
    # wall row is open at those.
    # the west wall column the.
    # the entry marker there.
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
    r"""Build the tail of leaf row ``k``: a gauntlet to 0, the answer,."""
    diff: int = 2**n - k - 1
    output = ")" if bit == "1" else " "
    return "(<" * diff + ")" * diff + f" {output} ---"


def _cod_cascade_row(n: int) -> str:
    r"""Build the cascade row's chain of ``+<(`` blocks, one per non-final."""
    total: int = 2**n - 1
    return "  " + "+<(" * total


def _cod_tree(n: int, table: str) -> str:
    r"""Build the ``2**n`` leaf rows, each peeling off one combo's answer."""

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
    r"""Build the leaf cascade (Phase 2): stairstep gates down to each."""
    tree_rows = _cod_tree(n, table).split("\n")

    # Wrap the tree in a west wall.
    # need only the one column;.
    # since the tree's own left.
    # row (each leaf sits one.
    # leaf row's own new left cell.
    # the shaft down from Phase 1's.
    # rather than "~ ".
    first, *middle, last = tree_rows
    wrapped_middle = [("  " if i == 0 else "~ ") + row for i, row in enumerate(middle)]
    return "\n".join(["~" + first, *wrapped_middle, "~" + last])


def _cod_combine(blocks: list[str]) -> str:
    r"""Concatenate grid blocks left to right, padding shorter ones with."""
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


# A ``{Xi}`` placeholder is.
# the fill replaces it with.
# cells, so a template row is.
_COD_CELL = re.compile(r"\{X\d+\}|.")


def _cod_cells(block: str) -> list[list[str]]:
    r"""Split ``block`` into rows of cells, a ``{Xi}`` counting as one."""
    return [_COD_CELL.findall(row) for row in block.split("\n")]


# Five columns for a rotated.
_COD_STRIDE = 6


def _cod_rotate_cw(block: str) -> list[str]:
    r"""Stand a block on end: ``new[c][H - 1 - r] = old[r][c]``."""
    rows = block.split("\n")
    height = len(rows)
    width = max(len(row) for row in rows)
    rows = [row.ljust(width) for row in rows]
    return [
        "".join(rows[height - 1 - r][c] for r in range(height)) for c in range(width)
    ]


def _cod_rotated(n: int, truth_table: str) -> str:
    r"""Build the program with phase 1 as rotated columns rather than one."""
    boxes = [_cod_rotate_cw(_cod_fork_box(n, k + 1)) for k in range(n - 1)]
    height = max(len(box) for box in boxes) + 2  # a top and a bottom corridor.
    cascade_col = _COD_STRIDE * (n - 1)
    grid = [["~"] * cascade_col for _ in range(height)]

    for k, box in enumerate(boxes):
        base = _COD_STRIDE * k
        entry, riser = base + 3, base + 5
        for r, row in enumerate(box):
            for c, char in enumerate(row):
                grid[r + 1][base + c] = char
        for r in range(len(box) + 1, height - 1):
            grid[r][entry] = " "  # drop the exit column to the.
        for c in range(entry, riser + 1):
            grid[height - 1][c] = " "  # bottom corridor, east to the.
        # The last riser stops at row 1.
        # the others carry on to the.
        for r in range(0 if k < n - 2 else 1, height - 1):
            grid[r][riser] = " "
        if k < n - 2:
            for c in range(riser, base + _COD_STRIDE + 4):
                grid[0][c] = " "  # top corridor, east to the.

    for c in range(4):
        grid[0][c] = " "
    grid[0][0] = ">"

    cascade = _cod_cascade(n, truth_table).split("\n")
    cascade[1] = "{X" + str(n - 1) + "}" + cascade[1][1:]
    # Pad in *cells* and with wall.
    # shrinks by three when the.
    # stops touching the right edge.
    # since ``_edge_dash_cells``.
    # wall would open water the.
    # cod escapes its shaft; the.
    cells = [len(_COD_CELL.findall(row)) for row in cascade]
    cwidth = max(cells)
    cascade = [
        row + "~" * (cwidth - got) for row, got in zip(cascade, cells, strict=True)
    ]

    rows = [
        "".join(grid[r]) + (cascade[r] if r < len(cascade) else "~" * cwidth)
        for r in range(height)
    ]
    program = "\n".join(rows)
    for k in range(n - 1):
        program = program.replace("?", "{X" + str(k) + "}", 1)
    return program


def _cod_width(program: str) -> int:
    r"""Measure the program as *text*, which is what a caller is handed."""
    return max(len(row) for row in program.split("\n"))


def _cod_turned(program: str) -> str:
    r"""Turn the program a quarter turn clockwise, re-attaching its prints."""
    rows = _cod_cells(program)
    height = len(rows)
    width = max(len(row) for row in rows)
    grid = [row + [" "] * (width - len(row)) for row in rows]
    # Clockwise, so a cod swimming.
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
    r"""Build a sealed block of ignored inputs' setters, which the cod."""
    inner = "".join("{X" + str(i) + "}" for i in names)
    wall = "~" * (len(names) + 2)
    return "\n".join([wall, "~" + inner + "~", wall])


def cod(truth_table: str, width: int | None = None) -> str:
    r"""Build a COD template for an ``n``-input Boolean function, any ``n."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of.
    # cost is the leaf cascade --.
    # -- so dropping an input.
    # table's program, rename its.
    # the rest in sealed boxes.
    # it so every ``{Xi}`` still.
    used = essential_inputs(truth_table, n) or [0]
    # A *gapped* dependency set.
    # core's slots around the.
    # and breaking name order, so.
    # declines a gapped set.
    # table would ghost-pad itself.
    # .
    # Widening is not guaranteed to.
    # ``2**len(used)`` while the.
    # per ignored input, so a span.
    # No table measured here comes.
    # construction forbids it, and.
    # reduced build is measured.
    # the ``shortest``-of-N.
    # box cost more per input is.
    used = list(range(used[0], used[-1] + 1))
    reduced = None
    if len(used) < n:
        core = cod(read_at(truth_table, used, n))
        # Rename through a private.
        # place could collide with a.
        for slot in reversed(range(len(used))):
            core = core.replace("{X" + str(slot) + "}", f"\x01{used[slot]}\x02")
        core = re.sub(r"\x01(\d+)\x02", lambda m: "{X" + m.group(1) + "}", core)
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
        blocks.append(_cod_fork_box(n, k + 1).replace("?", "{X" + str(k) + "}", 1))

    box_rows = _cod_cascade(n, truth_table).split("\n")
    box_rows[1] = "{X" + str(n - 1) + "}" + box_rows[1][1:]
    blocks.append("\n".join(box_rows))

    full = _cod_combine(blocks)
    if width is not None and _cod_width(full) > width:
        # Two shapes to choose between,.
        # trades width for height a.
        # whole drawing's width for its.
        # blocks are joined left to.
        # width becomes the tallest.
        return _cod_turned(full)
    # Three shapes now, and the.
    # (:func:`_cod_rotated`).
    # away -- 1.29x there, 3.67x at.
    # corridors cost more than the.
    # comparison rather than a.
    candidates = [full]
    if reduced is not None:
        candidates.append(reduced)
    if n >= 2:
        candidates.append(_cod_rotated(n, truth_table))
    return min(candidates, key=len)


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"
