"""Boolean-function generator for COD (parameterized convention).

COD has no input command, so this follows the parameterized convention
described in :mod:`esolangs.tools.boolean.parameterized`: the template's
``{Xi}`` placeholders are filled by the harness, one program per input
combination.  The generator routes a fork/cascade decision tree whose
leaves print the truth-table entry.
"""

from itertools import zip_longest

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["cod"]


def _cod_reachable(n: int, k: int) -> tuple[set[int], set[int], set[int]]:
    """Combo-index contributions reachable after fork ``k`` (0 if ``k == 0``).

    Returns ``(flat, plus_one, plus_weight)``: the values reachable *before*
    fork ``k`` (``flat``), after taking its "continue" branch (``+1``, an
    artifact of the gauntlet's own bookkeeping consumed by :func:`_cod_fork_box`
    ), and after taking its "peel off" branch (``+ 2**(n-k)``, the bit's
    weight).  Recursive in ``k``: fork ``k``'s reachable set is fork
    ``k - 1``'s two branch sets combined.
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

    ``vals`` sorted with a leading 0 gives consecutive gaps; each gap becomes
    a run of ``(`` (decrement) of that length followed by a ``<`` gate, so
    only a cod whose value already matches one of ``vals`` survives to the
    next gate.  A trailing run of ``)`` (up to the maximum value) restores
    the surviving cod to that value for whatever comes next.
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

    Bit ``k`` (1-indexed, weight ``2**(n - k)``) gets its own ``+`` fork:
    one branch continues forward (a net-zero gauntlet -- the value entering
    and leaving is unchanged), the other peels off to a private side row
    (a gauntlet that nets the branch's full weight), and both rejoin at a
    second ``+`` on the main row.  Unlike nesting fork-and-gauntlet routing
    directly (the ``n <= 3`` construction this replaces), every box below
    uses *its own* private cells for both branches -- no box's gauntlet
    cells are reused by another box's routing -- so boxes compose by plain
    horizontal concatenation (see :func:`_cod_combine`) with no risk of one
    box's cod re-entering another box's cells from an unexpected direction
    (the failure mode that blocked a general-``n`` construction before;
    see ``docs/cod_boolean_generator.md``, "Why the earlier n <= 3 merge
    design didn't generalize").
    The leading ``?`` marks the box's own entry cell, replaced by the
    previous box's exit (or ``>`` for the first box) when boxes are joined.
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

    Reached with the combo index ``V = sum(bit_i * 2**(n-1-i))`` as the
    cod's value, the cascade's chain of ``+<(`` blocks (:func:`_cod_cascade_row`)
    peels off one copy per step, decrementing the rest; each leaf's own
    gate chain only lets the copy carrying exactly the right number of
    decrements through, so leaf ``k`` fires iff ``V == k``.  Column 1 is a
    pre-built vertical shaft from the entry row straight down to the
    cascade row, used to feed in the combo index from :func:`_cod_fork_box`
    boxes stacked above (see :func:`_cod_combine`).
    """
    tree_rows = _cod_tree(n, table).split("\n")

    # Wrap the tree in a west wall column.  The top and bottom wall rows
    # need only the one column; every leaf-tree row in between needs two,
    # since the tree's own left edge already steps in by one column per
    # row (each leaf sits one column deeper than the last).  The first
    # leaf row's own new left cell is open water instead of wall -- it is
    # the shaft down from Phase 1's last exit -- so it alone gets "  "
    # rather than "~ ".
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


def cod(truth_table: str) -> str:
    """Build a COD template for an ``n``-input Boolean function, any ``n >= 1``.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    template's ``{X0}``..``{X(n-1)}`` placeholders become the input bits
    (``)`` for a one bit, a space for a zero); the harness's
    :func:`instantiate` fills them, matching every other no-input
    generator's convention.

    The construction has two phases, each built from private, self-
    contained grid blocks joined by plain horizontal concatenation
    (:func:`_cod_combine`) -- no block's cells are reused by another
    block's routing, which is what makes this generalize past the
    hand-built ``n <= 3`` construction it replaces (see
    ``docs/cod_boolean_generator.md``, "Why the earlier n <= 3 merge design
    didn't generalize", for the re-entry failure mode that blocked a
    general-``n`` version before):

    Phase 1 assembles the input combo's numeric index ``V = sum(bit_i *
    2**(n-1-i))``: bits ``0..n-2`` each get their own fork-and-gauntlet box
    (:func:`_cod_fork_box`) that adds the bit's weight to the running value,
    and the last bit (weight ``2**0 == 1``) is a bare placeholder cell
    needing no fork of its own.

    Phase 2 (:func:`_cod_cascade`) is a leaf cascade: reached with the cod's
    value equal to ``V``, a chain of ``2**n - 1`` ``+<(`` blocks peels off
    one copy per step, and each leaf's own gate chain only lets through the
    copy carrying exactly the right number of decrements -- so leaf ``k``
    fires iff ``V == k``, prints the table's answer for that leaf (baked in
    directly, ``)`` for a one entry, nothing for a zero), and halts.  Every
    entry is therefore a compile-time constant and the program always
    prints exactly one line.
    """
    n = _validate_truth_table(truth_table)
    if n < 1:
        raise ValueError(f"cod requires n >= 1, got n == {n}")

    blocks = ["~~~\n~> \n~~~"]
    for k in range(n - 1):
        blocks.append(_cod_fork_box(n, k + 1).replace("?", "{X" + str(k) + "}", 1))

    box_rows = _cod_cascade(n, truth_table).split("\n")
    box_rows[1] = "{X" + str(n - 1) + "}" + box_rows[1][1:]
    blocks.append("\n".join(box_rows))

    return _cod_combine(blocks)


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"
