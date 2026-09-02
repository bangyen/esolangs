"""Boolean-function generator for COD (parameterized convention).

This follows the parameterized convention described in
:mod:`esolangs.tools.boolean.parameterized`: the template's ``{Xi}``
placeholders are filled by the harness, one program per input combination.
The generator routes a fork/cascade decision tree whose leaves print the
truth-table entry.

COD *does* have an input command, contrary to what this docstring used to
say: ``...`` (three periods, touching the top or bottom edge) sets the cod's
value from stdin, per the wiki spec and
:func:`esolangs.interpreters.grid_based.cod._edge_dot_cells`.  The
parameterized convention is kept here anyway because a reading generator
would have to route every input crossing *horizontally* -- this interpreter
treats each of the three dot cells as its own read, so a cod that turns into
the column reads three times for one command, and one that dead-ends there
re-reads until EOF.  See ``docs/parameterized-input-conversion.md``.
"""

import re
from itertools import zip_longest

from esolangs.tools.boolean.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)

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
    see :func:`cod` for why the shared-cell merge it replaces could not be
    proven safe past ``n == 3``).
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


def _cod_dead_box(names: list[int]) -> str:
    """Build a sealed block of ignored inputs' setters, which the cod never enters.

    Every input keeps its ``{Xi}`` -- the harness has a bit for each one --
    but an input the table ignores must not reach the value the cascade
    reads.  COD is a *grid*, so unlike a one-dimensional tape it has cells
    that are genuinely unreachable: a ``~`` wall on every side is water the
    cod cannot cross, and a ``)`` inside it increments nothing because no
    cod is ever there.  That makes an ignored setter free rather than merely
    cheap -- there is nothing to discard (taglate), erase (minifuck), or
    weigh zero (home_row).

    The box is stacked above or below the reduced program rather than
    concatenated beside it, because :func:`_cod_combine` pads shorter blocks
    with *spaces*, and a space in COD is open water rather than inert filler
    -- padding the reduced program out to a common width lets the cod swim
    out of it, and the program then prints nothing at all.
    """
    inner = "".join("{X" + str(i) + "}" for i in names)
    wall = "~" * (len(names) + 2)
    return "\n".join([wall, "~" + inner + "~", wall])


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
    hand-built ``n <= 3`` construction it replaces:

    The design this supersedes built ``n == 3`` as a single fused row whose
    forks' merge cells reused the *same physical cells* as the forward
    gauntlets, walked backwards (a "sacrificial retrace") to unwind a
    rejoining cod's value to 0.  It could not be proven safe past
    ``n == 3``: a merge cell could be re-entered from more than one
    direction across different steps -- from the west via the forward path,
    from the south via the side path's shaft, and, once a west-bound
    retrace from a *later* merge passed back through an *earlier* merge's
    own cell, from the east too.  The wiki's ``+`` rule excludes a
    different "came from" direction per entry, so a cell acting as a clean
    2-way fork from one entry direction acts as a 3-way fork from another,
    and cods accumulate instead of being consumed -- an exploding
    population rather than a clean halt.  ``n == 3`` never triggers it (its
    one two-stage retrace never passes through another merge cell), but
    nothing guaranteed that for ``n >= 4``.  The private-cell construction
    below sidesteps the problem rather than solving it.

    A ``_``-gate decision tree was also considered and rejected: it needs a
    seeded-randomness convention for ``_``'s junctions, where the
    ``+``-fork-and-gauntlet idiom uses no ``_`` gate and no random
    junctions at all.

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

    # A table that ignores some of its inputs is a smaller table, and COD's
    # cost is the leaf cascade -- ``2**n - 1`` blocks whatever the table says
    # -- so dropping an input roughly halves the program.  Build the reduced
    # table's program, rename its slots to the inputs that survived, and park
    # the rest in sealed boxes (:func:`_cod_dead_box`) placed either side of
    # it so every ``{Xi}`` still appears exactly once, in ascending order.
    used = essential_inputs(truth_table, n) or [0]
    # A *gapped* dependency set (inputs 0 and 2 but not 1) would emit the
    # core's slots around the ignored one, leaving ``{X2}`` before ``{X1}``
    # and breaking name order, so the set is widened to its span.  Taglate
    # declines a gapped set outright instead, because there the widened
    # table would ghost-pad itself.
    #
    # Widening is not guaranteed to pay: the span's cascade grows as
    # ``2**len(used)`` while the dead boxes it buys back save only one cell
    # per ignored input, so a span that is wide but sparse recovers little.
    # No table measured here comes out longer, but nothing in the
    # construction forbids it, and the check is two comparisons -- so the
    # reduced build is measured against the full one and the shorter kept,
    # the ``shortest``-of-N precedent.  A future change that makes the dead
    # box cost more per input is exactly what this guard is for.
    used = list(range(used[0], used[-1] + 1))
    reduced = None
    if len(used) < n:
        core = cod(read_at(truth_table, used, n))
        # Rename through a private marker: rewriting ``{X0}`` to ``{X2}`` in
        # place could collide with a ``{X2}`` this loop has not reached yet.
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
    return reduced if reduced is not None and len(reduced) < len(full) else full


_byte_limit = "this truth table needs a skip beyond the 256-cell byte limit"
