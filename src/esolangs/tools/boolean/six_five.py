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

from contextlib import suppress
from itertools import permutations
from math import factorial

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _greedy_input_order,
    _validate_truth_table,
    permute_truth_table,
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

    Both constructions are decision trees over ``78``: the ``7`` compares the
    cell to 8, so a zero bit skips the following ``8n`` jump and falls into
    the left subtree, while a one bit takes the jump to the n-th ``4`` marker
    holding the right subtree.  A leaf adds ``48 + value - base`` (8 for a
    left path, 9 for a right path) with a run of sixes plus ``62`` pairs
    (each ``6`` then ``2`` nets ``+6 - 5 = +1``), prints with ``A``, and
    halts with ``0``.  A subtree whose rows all hold the same value folds to
    a single leaf rather than the branches that would all reach it.

    What differs is where the reads sit.  :func:`_six_five_node_read` reads
    at the node that tests the bit, which forces the tree to test its inputs
    in stream order.  :func:`_six_five_hoisted` reads every input up front
    into a cell of its own, which lets a node test *any* input and so lets
    the tree split in whichever order folds best -- 6-5 has a tape and a
    pointer (``B`` reads the current cell, ``1``/``3`` move it), so the read
    order and the test order are independent.

    **The shortest of both constructions over every input order wins.**  The
    hoist is not free -- it pays a pointer move per node and eight ``2``s per
    stored input where the node-read tree normalizes in place -- so on small
    or shallow tables it loses to the tree it replaces (at n == 3 the
    hoisted identity order is longer than the node-read build on 96 of 256
    tables).  Keeping the node-read build as one more candidate is what makes
    this a pure shrink: measured over all 256 tables at n == 3 the dispatch
    is 18.1% shorter, improving 186 and growing none, and 23.6% shorter over
    a sample at n == 4.

    The branch labels are the digits 0..9 then A..Z (values 1..35, consumed
    as ``8n`` operands), one per internal node the fold leaves standing.
    An unfolded tree would therefore cap at n == 5 (31 internal nodes), but
    since folding is what spends the labels, the choice is made by counting
    them (:func:`_six_five_markers`) rather than by ``n``: any table whose
    folded tree fits in 35 labels uses the tree, at any ``n``.

    **The budget is now per-order**, which widens what renders: a table whose
    identity tree overflows may fold inside the budget under some other
    order, and only a table that overflows under *every* order is refused.
    An alternating n == 6 table used to be the standard refusal -- it folds
    nothing in stream order -- but it is NOT of the last input, so the order
    that tests that input first folds it to a single label and it now
    renders.  What is still refused is a table no renaming can fold:
    **parity** of all six inputs needs 63 labels under all 720 orders, since
    any permutation of parity is parity.  Every table is renderable through
    n == 5 (the worst case spends 31), so the refusals still begin at
    n == 6, and a table refused under every order raises :class:`ValueError`.

    **The order search is capped at ``_ORDER_SEARCH_MAX`` inputs**, the same
    bound and the same greedy fallback ``best_input_order`` uses.  The cap
    matters more here than there, because this generator does render past
    n == 6 when a table folds hard: searching AND-8's 40320 orders takes
    about 17 seconds against milliseconds for the greedy pick, and n == 9
    would be half an hour.  Above the cap only the identity and the greedy
    order are built, so a wide table stays fast and still never grows.
    """
    n = _validate_truth_table(truth_table)
    best = ""
    # The node-read build goes first and ties keep it, so a table no hoist
    # and no reorder improves emits exactly what it emitted before.  It
    # raises on a table whose identity tree overflows the budget, which is
    # not a refusal of the *table* any more -- another order may still fit.
    with suppress(ValueError):
        best = _six_five_node_read(truth_table)
    identity = tuple(range(n))
    # The same cap ``best_input_order`` uses, for the same reason: ``n!``
    # builds of an ``O(2**n)`` program does not announce itself.  This
    # generator renders past n == 6 whenever a table folds hard enough, so
    # the cap is reachable here rather than theoretical -- AND-8 measures
    # 17 seconds searching all 40320 orders against milliseconds greedily.
    if n <= _ORDER_SEARCH_MAX:
        orders = list(permutations(range(n)))
    else:
        orders = [identity, _greedy_input_order(truth_table, n)]
    for perm in orders:
        table = (
            truth_table if perm == identity else permute_truth_table(truth_table, perm)
        )
        candidate = _six_five_hoisted(table, perm)
        # An empty candidate means this order overflowed the label budget,
        # so it is skipped rather than winning on length 0.
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    if not best:
        searched = factorial(n) if n <= _ORDER_SEARCH_MAX else len(orders)
        raise ValueError(
            "the 6-5 decision tree has 35 branch labels, but this table needs "
            f"{_six_five_markers(truth_table)} after folding its constant "
            f"subtrees under every one of the {searched} input orders tried "
            f"(n == {n})"
        )
    return best


def _six_five_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit the read-up-front 6-5 program for one input order.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame and self-consistent; ``perm`` surfaces only where a node
    names the *stream* input it tests.  Returns ``""`` when this order's
    folded tree overflows the 35-label budget, which is a signal to try
    another order rather than a refusal of the table.

    **Only the inputs the tree branches on get a cell.**  The read contract
    asks that every input be *consumed*, not that every value be *kept*, so
    an input no node tests is read into a shared scratch cell the next such
    read overwrites.  The kept bits then occupy a contiguous block from cell
    0, so the tree navigates a span as wide as the function's real
    dependencies rather than one as wide as ``n``.

    **A stored read is normalized where it lands**, with the same eight
    ``2``s the node-read build spends: ``7n`` decodes its operand through a
    single character capped at 35, so a cell still holding 48/49 can never be
    tested directly, and normalizing at read time is what lets every node
    emit a plain ``78`` and every leaf inherit the 8/9 base arithmetic.

    **A leaf prints from the cell it is standing on.**  It was reached by its
    parent's test, so the pointer is on that parent's cell and the value
    there is known -- 9 on the jump branch, 8 on the fall-through -- which
    makes the leaf a run of cell ops with no navigation.  Mutating a bit cell
    is safe because exactly one leaf runs per execution and every leaf halts.
    The pointer's position on entry to a node is a function of its *level*
    alone, never of the path taken: both branches leave the pointer on the
    parent's cell.
    """
    n = _validate_truth_table(truth_table)
    if _six_five_markers(truth_table) > 35:
        return ""
    # Which levels the tree can branch on, computed in *level* space over the
    # permuted table and then translated to the *stream* inputs the read
    # block runs over -- level ``k`` reads input ``perm[k]``, and mixing the
    # two frames stores the wrong bits.
    branching = {
        k
        for k in range(n)
        if any(
            truth_table[r] != truth_table[r | (1 << (n - 1 - k))]
            for r in range(2**n)
            if not r & (1 << (n - 1 - k))
        )
    }
    stored = {perm[k] for k in branching}
    # Reads run in input order; only a stored input claims a cell, so the
    # kept bits occupy a contiguous block from cell 0 and every clobbered
    # read reuses the one cell past it.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    pos = 0
    for i in range(n):
        reads += _six_five_move(pos, slot)
        pos = slot
        reads += "B"
        if i in stored:
            reads += "2" * 8
            cell_of[i] = slot
            slot += 1
    # A clobbered read leaves 48/49 under the pointer, so the cell the reads
    # finish on is blank only when the last read was stored and advanced past
    # it.  A whole-table constant has no parent cell to print from and builds
    # its digit from zero, so it needs a cell no read ever wrote: step one
    # past the shared scratch when the final read clobbered.
    scratch = slot + 1 if n and (n - 1) not in stored else slot
    marker = 0

    def leaf(value: str, entry: int, held: int | None) -> str:
        if held is None:
            # No node tested anything, so no cell holds a known value.
            digit = _ASCII_ZERO + int(value)
            return _six_five_move(entry, scratch) + _six_five_const(digit) + "A0"
        delta = _ASCII_ZERO + int(value) - held
        q, r = divmod(delta, 6)
        return "6" * q + "62" * r + "A0"

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        nonlocal marker
        if level == n or len(set(truth_table[lo:hi])) == 1:
            return leaf(truth_table[lo], entry, held)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either is the same function -- take the zero half,
        # which keeps the row span halving in step with the level.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held)
        cell = cell_of[perm[level]]
        mid = (lo + hi) // 2
        nav = _six_five_move(entry, cell)
        # A label is the index of this node's own ``4`` among every ``4`` in
        # the emitted string, so it is allocated *after* the left subtree --
        # whose markers all precede it -- and before the right.
        sub0 = node(level + 1, lo, mid, cell, 8)
        marker += 1
        label = marker
        sub1 = node(level + 1, mid, hi, cell, 9)
        return nav + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1

    return reads + node(0, 0, 2**n, pos, None)


def _six_five_move(frm: int, to: int) -> str:
    """Pointer ops walking from cell ``frm`` to cell ``to``.

    The moves are asymmetric: ``1`` steps *two* cells right and ``3`` steps
    one left (and is a silent no-op at cell 0, so a leftward walk must be
    known to stay in range).  Rightward by ``d`` is therefore ``ceil(d / 2)``
    ones plus a ``3`` when ``d`` is odd, which is why an odd rightward hop
    costs the same as the even one above it.
    """
    if to > frm:
        distance = to - frm
        return "1" * ((distance + 1) // 2) + ("3" if distance % 2 else "")
    return "3" * (frm - to)


def _six_five_node_read(truth_table: str) -> str:
    """Emit the read-at-the-node 6-5 program; see :func:`six_five`.

    Each input is read with ``B`` at the node that tests it and normalized in
    place to 8/9 (subtracting 40 with eight ``2``s), so this construction
    spends no pointer moves at all -- which is what keeps it competitive with
    the hoisted build on shallow tables, and why :func:`six_five` measures
    both rather than replacing this one.

    Testing at the read forces the tree to split in stream order, so this
    build has no input-order freedom: it is one candidate, not ``n!`` of
    them.

    A constant subtree folds to a single leaf -- 17 characters against 226 at
    n == 3, and 19 against 946 at n == 5.  The fold still spends the reads it
    skipped, so a caller feeding several programs from one input stream stays
    in sync.  Those reads are why a folded leaf cannot use the 8/9 base:
    ``B`` overwrites the cell, so after the skipped reads it holds the last
    input character (48 or 49, differing per input) and no fixed run of cell
    ops maps both to one value.  The leaf steps to cell 1 instead --
    untouched, since every tree path works in cell 0 and every leaf halts --
    and builds the digit from zero there.

    Raises :class:`ValueError` when the folded tree overflows the 35 labels.
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
