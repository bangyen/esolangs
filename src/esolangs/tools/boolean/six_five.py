"""Boolean-function generator for 6:5.

:func:`six_five` routes a decision tree that folds its constant subtrees.

There used to be a second construction, ``six_five_arithmetic``, which
packed the inputs and the table into single cells and decoded the entry
with ``f(x) = (T >> x) & 1``.  It existed because the unfolded tree spent
one of 6-5's 35 branch labels per internal node and so capped at n == 5.
Once the tree folded, the cap became a property of the *table* rather than
of ``n``, and the arithmetic path was left unreachable: it needs ``T`` (or
its complement) small enough to build, which confines the ones to low
indices, which leaves the rest of the table constant -- exactly the shape
that folds well inside the label budget.  No table was found that overflows
the budget and still builds arithmetically, so the construction and its
assembler were retired.
"""

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
)
from esolangs.tools.transpilers import _six_five_label

__all__ = ["six_five"]


def _six_five_markers(table: str) -> int:
    """How many branch labels the folded decision tree spends on ``table``.

    One per internal node the fold leaves standing.  This counts exactly
    what :func:`six_five`'s ``build`` allocates rather than re-deriving it:
    the tree splits most-significant-first over a contiguous row range, so
    a node's two children are always the two halves of its table slice, and
    a slice whose characters agree is the constant subtree that folds to a
    leaf and takes no label.
    """
    if len(set(table)) == 1:
        return 0
    half = len(table) // 2
    return 1 + _six_five_markers(table[:half]) + _six_five_markers(table[half:])


def six_five(truth_table: str) -> str:
    """Build a 6-5 program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Each input is read with ``B`` and normalized to 8/9 (subtracting 40 with
    eight ``2``s).  ``78`` branches: the ``7`` compares the cell to 8, so a
    zero bit skips the following ``8n`` jump and falls into the left subtree,
    while a one bit takes the jump to the n-th ``4`` marker holding the right
    subtree.  A leaf adds ``48 + value - base`` (8 for a left path, 9 for a
    right path) with a run of sixes plus ``62`` pairs (each ``6`` then ``2``
    nets ``+6 - 5 = +1``), prints with ``A``, and halts with ``0``.

    A subtree whose rows all hold the same value folds to a single leaf
    rather than the branches that would all reach it -- a constant table is
    17 characters against 226 at n == 3, and 19 against 946 at n == 5.  The
    fold still spends the reads it skipped, so a caller feeding several
    programs from one input stream stays in sync.  Those reads are why a
    folded leaf cannot use the 8/9 base: ``B`` overwrites the cell, so after
    the skipped reads it holds the last input character (48 or 49, differing
    per input) and no fixed run of cell ops maps both to one value.  The
    leaf steps to cell 1 instead -- untouched, since every tree path works in
    cell 0 and every leaf halts -- and builds the digit from zero there.

    The branch labels are the digits 0..9 then A..Z (values 1..35, consumed
    as ``8n`` operands), one per internal node the fold leaves standing.
    An unfolded tree would therefore cap at n == 5 (31 internal nodes), but
    since folding is what spends the labels, the choice is made by counting
    them (:func:`_six_five_markers`) rather than by ``n``: any table whose
    folded tree fits in 35 labels uses the tree, at any ``n``.  This is what
    renders tables the old ``n <= 5`` gate could not -- AND-6 needs 6 labels
    but was refused outright.

    A table that stays wide under folding has no representation here and
    raises :class:`ValueError`: a scattered n == 6 table needs 63 labels
    against a budget of 35.  Every table is renderable through n == 5 (the
    worst case, an alternating table, folds nothing and spends 31), so the
    refusals begin at n == 6.
    """
    n = _validate_truth_table(truth_table)
    labels = _six_five_markers(truth_table)
    if labels > 35:
        raise ValueError(
            "the 6-5 decision tree has 35 branch labels, but this table needs "
            f"{labels} after folding its constant subtrees (n == {n})"
        )
    marker = 0

    def build(rows: list[int], bit: int, base: int) -> str:
        nonlocal marker
        if len(rows) == 1:
            delta = _ASCII_ZERO + int(truth_table[rows[0]]) - base
            q, r = divmod(delta, 6)
            return "6" * q + "62" * r + "A0"
        values = {truth_table[r] for r in rows}
        if len(values) == 1:
            # A constant subtree emits its value directly instead of the
            # branches that would all reach it.  The skipped reads still
            # happen (a caller feeding several programs from one stream
            # would otherwise desync), but their ``B``s leave the cell
            # holding the last input character -- 48 or 49, which differs
            # per input -- and every cell op adds an unconditional
            # constant, so no fixed suffix could bring both to one value.
            # The leaf therefore steps to cell 1, which no tree path ever
            # writes, and builds the digit from zero.
            reads = "B" * (n - bit + 1)
            value = _ASCII_ZERO + int(values.pop())
            return reads + "13" + _six_five_const(value) + "A0"
        g0 = [r for r in rows if ((r >> (n - bit)) & 1) == 0]
        g1 = [r for r in rows if ((r >> (n - bit)) & 1) == 1]
        sub0 = build(g0, bit + 1, 8)
        label = marker + 1
        marker += 1
        sub1 = build(g1, bit + 1, 9)
        return "B" + "2" * 8 + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1

    return build(list(range(2**n)), 1, 0)


def _six_five_const(value: int) -> str:
    """Instructions adding ``value`` to the current cell.

    The ``+5/+6/-5/-6`` cell ops add at most 6 per instruction, so the
    shortest run is mostly ``6`` (one per unit) with a small tail: the old
    ``62`` pair encoding cost ``2 * value`` characters, this is ~``value / 6``.
    """
    q, r = divmod(value, 6)
    if r == 5:
        return "6" * q + "5"  # one +5 beats five +1 pairs
    return "6" * q + "62" * r
