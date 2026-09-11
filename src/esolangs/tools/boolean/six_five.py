"""Boolean-function generator for 6:5.

:func:`six_five` routes a decision tree that folds its constant subtrees,
shares its duplicates past the label budget, and falls back to a positional
walk (:func:`_six_five_walk`) when even the distinct subtrees overflow --
which makes the generator total through n == 35.

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

import string
from itertools import permutations

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _greedy_input_order,
    _validate_truth_table,
    permute_truth_table,
    stored_inputs,
)

__all__ = ["six_five"]

# The 6-5 spec denotes operands "beyond 9 ... using letters (A=10, B=11
# etc.)", so ``0..9A..Z`` names 0..35 and there is no character for 36.
# This interpreter would decode past ``Z`` through an unguarded
# fallthrough, which is undefined behaviour rather than a language feature
# (see the conformance note in ``docs/limitations.md``), so nothing may
# emit into that region.
_SIX_FIVE_MAX_LABEL = 10 + len(string.ascii_uppercase) - 1


def _six_five_label(value: int) -> str:
    """Return the single character 6-5 reads as ``value`` for a 7n/8n operand."""
    if not 0 <= value <= _SIX_FIVE_MAX_LABEL:
        raise ValueError(f"6-5 has no operand character for {value}")
    return str(value) if value < 10 else chr(value + 55)


def _six_five_markers(table: str) -> int:
    """How many branch labels the folded decision tree spends on ``table``.

    One per internal node the fold leaves standing.  This counts exactly
    what either construction allocates rather than re-deriving it: both
    split most-significant-first over a contiguous row range, so a node's
    two children are always the two halves of its table slice, and a slice
    whose characters agree is the constant subtree that folds to a leaf and
    takes no label.

    ``table`` is whatever table the caller is about to build, so passing a
    *permuted* one gives that input order's count.  The counts differ per
    order -- that is what makes the 35-label budget a per-order gate rather
    than a property of the function.
    """
    if len(set(table)) == 1:
        return 0
    half = len(table) // 2
    return 1 + _six_five_markers(table[:half]) + _six_five_markers(table[half:])


def six_five(truth_table: str) -> str:
    """Build a 6-5 program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is a decision tree over ``78``: the ``7`` compares the
    cell to 8, so a zero bit skips the following ``8n`` jump and falls into
    the left subtree, while a one bit takes the jump to the n-th ``4`` marker
    holding the right subtree.  A leaf adds ``48 + value - base`` (8 for a
    left path, 9 for a right path) with a run of sixes plus ``62`` pairs
    (each ``6`` then ``2`` nets ``+6 - 5 = +1``), prints with ``A``, and
    halts with ``0``.  A subtree whose rows all hold the same value folds to
    a single leaf rather than the branches that would all reach it.

    The identity order reads and tests in place. A reordered tree stores its
    inputs first, then tests any cell. 6-5 has a tape and pointer (``B``,
    ``1``/``3``), so one ordered builder covers both cases. Every order is
    measured and the shortest emitted program wins.

    The branch labels are the digits 0..9 then A..Z (values 1..35, consumed
    as ``8n`` operands), one per internal node the fold leaves standing.
    An unfolded tree would therefore cap at n == 5 (31 internal nodes), but
    since folding is what spends the labels, the choice is made by counting
    them (:func:`_six_five_markers`) rather than by ``n``: any table whose
    folded tree fits in 35 labels uses the tree, at any ``n``.

    **The budget is spent per input order**, so a table whose identity tree
    overflows may fold inside it under some other order.  An alternating
    table folds nothing in stream order but is only NOT of the last input,
    so one reorder collapses it to a single label: a table that merely
    looks scattered is not a hard one.

    **Past the budget the tree is shared** (:func:`_six_five_shared`), which
    is what carries this generator past n == 5 and inverts which table is
    hard.  Parity used to be the witness that fixed the cap -- no renaming
    folds any of its 63 nodes at n == 6, since any permutation of parity is
    parity -- and it is now the *cheapest* wide table there is, because
    those nodes are duplicates of one another: two distinct subtrees per
    level, 20 markers at n == 10 against 1023 unshared.  What binds a tree
    is a table with many *different* subtrees, which is the dense one:
    n == 7 dense needs 47.

    **Past even the distinct subtrees the table goes on the tape**
    (:func:`_six_five_walk`), which spends one label per *input* rather
    than per subtree and so is total through n == 35: the reads steer the
    pointer to the row the inputs index instead of steering the cursor.
    The trees stay preferred while one fits -- they are what every
    committed size measurement was taken against, and far shorter when a
    table folds or shares well.

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
    identity = tuple(range(n))
    # The same cap ``best_input_order`` uses, for the same reason: ``n!``
    # builds of an ``O(2**n)`` program does not announce itself.  This
    # generator renders past n == 6 whenever a table folds hard enough, so
    # the cap is reachable here rather than theoretical -- AND-8 measures
    # 17 seconds searching all 40320 orders against milliseconds greedily.
    if n <= _ORDER_SEARCH_MAX:
        orders = list(permutations(range(n)))
    else:
        greedy = _greedy_input_order(truth_table, n)
        orders = [identity] if greedy == identity else [identity, greedy]
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
        # Every order overflowed the budget even shared, so the table has
        # too many distinct subtrees for any tree-shaped emission.  The walk
        # spends labels per *input* rather than per subtree, so it always
        # fits at these widths.
        return _six_five_walk(truth_table)
    return best


def _six_five_walk(truth_table: str) -> str:
    """Emit the positional-walk 6-5 program: the whole table on the tape.

    The tree constructions spend a label per subtree, so a table with more
    than 35 *distinct* subtrees (dense n == 7 has 47) overflows under every
    input order.  This one spends exactly ``n`` labels however scattered
    the table is: the branching moves the *pointer* instead of the cursor.

    Layout: table row ``j`` is preloaded at stride ``n + j`` (``1`` moves
    two cells, so a stride is one ``1`` and row ``j`` sits at cell
    ``2 * (n + j)``), ones as ``62`` pairs and zeros left as the tape's
    own 0.  The pointer returns to cell 0 and each input bit is then read
    where the pointer stands and decoded in place: bit 1 (cell 9 after the
    ``2``s) skips the ``8n`` and falls into a run of ``2**(n-1-i)`` strides,
    bit 0 takes the jump to the ``4`` just past the run.  Both paths then
    share one more stride, so after ``n`` bits the pointer is at stride
    ``n + x`` -- the row the inputs index -- and the leaf adds 48 to the
    0/1 there and prints.  The one ``4`` per bit is the whole label bill.

    The shared stride per bit keeps every read strictly behind the final
    cell (at bit ``i`` the walk still has ``n - i`` strides to go), so the
    ``B``s only ever clobber rows this run has already passed -- harmless,
    since one cell is printed and the program halts.

    Dense n == 10 spends 10 labels and 5319 chars, and all 1024 rows run
    in 12s; size doubles per input, so the label bound ``n <= 35`` is the
    only other gate.
    """
    n = _validate_truth_table(truth_table)
    if n > _SIX_FIVE_MAX_LABEL:
        # Unreachable in practice: it takes a table of 2**36 entries, which
        # is more characters than the machine has memory for.  Kept because
        # the walk's arithmetic genuinely depends on the bound, and
        # converted to the cap class with its siblings so the class is not
        # half-applied.
        raise GeneratorCapError(  # pragma: no cover - needs a 2**36 table
            f"the 6-5 walk spends one branch label per input and there are "
            f"only 35, so n == {n} does not fit"
        )
    ones = [j for j, value in enumerate(truth_table) if value == "1"]
    out = ""
    if ones:
        # Rows past the last 1 stay virgin: the walk's own strides grow the
        # tape, and a virgin cell already holds the 0 those rows need.
        out += "1" * n
        for j in range(ones[-1] + 1):
            if truth_table[j] == "1":
                out += "62"
            if j != ones[-1]:
                out += "1"
        out += "3" * (2 * (n + ones[-1]))
    for i in range(n):
        out += "B" + "2" * 8 + "79" + "8" + _six_five_label(i + 1)
        out += "1" * 2 ** (n - 1 - i) + "4" + "1"
    return out + "6" * 8 + "A0"


def _six_five_dag_cost(truth_table: str) -> int:
    """Markers the shared build spends on ``truth_table``.

    One per distinct internal node, less the root's -- whose block is
    entered by falling into it rather than by a jump -- plus one per
    distinct *right* leaf.  See :func:`_six_five_shared` for why the right
    leaves are shared globally and the left ones are not, and why two equal
    slices are always the same node.
    """
    internal: set[str] = set()
    right_leaves: set[str] = set()

    def walk(window: str, *, right: bool) -> None:
        if len(set(window)) == 1:
            if right:
                right_leaves.add(window[0])
            return
        if window in internal:
            return
        internal.add(window)
        half = len(window) // 2
        walk(window[:half], right=False)
        walk(window[half:], right=True)

    walk(truth_table, right=False)
    return max(len(internal) - 1, 0) + len(right_leaves)


def _six_five_shared(
    truth_table: str,
    perm: tuple[int, ...],
    cell_of: dict[int, int],
    entry: int,
    n: int,
) -> str:
    """Emit the tree as a DAG, each distinct subtree laid down once.

    The tree spends a marker per internal node it leaves standing, and most
    of those nodes are duplicates: parity at n == 6 has 63 of them and only
    11 distinct ones.  ``8n`` names the *n-th* ``4`` in the program rather
    than a scope, so two branches may name the same one -- which makes the
    duplicates shareable and turns the label budget from a bound on the
    tree's size into one on the function's distinct subfunctions.

    **Two equal slices are always the same node.**  A slice's length fixes
    its level, and :func:`_six_five_hoisted` guarantees the pointer's
    position on entry is a function of the level alone, so every parent of
    a merged node enters it identically.  Nothing else in a node's code
    depends on the path: ``held`` reaches only the leaves.

    **Left leaves stay inline; right leaves are shared.**  A leaf's
    arithmetic counts from the value its parent's test left in the cell --
    8 falling through, 9 on the jump -- so leaves do not merge across the
    two.  A left leaf is the fall-through and costs no marker where it
    sits.  A right leaf needs one, but there are only ever two distinct
    ones in a whole program (print 0 from 9, print 1 from 9), so they are
    emitted once at the end and every right branch names one of the two.
    """
    # Distinct blocks, in the order their code is laid down: the root's
    # subtree first, then the rest reachable from it.  A block's label is
    # its index among the ``4`` markers, so the layout fixes the numbering
    # and both are decided here before a character is emitted.
    order: list[str] = []
    seen: set[str] = set()

    def level_of(window: str) -> int:
        return n - (len(window).bit_length() - 1)

    def test_cell(window: str) -> tuple[str, int]:
        """Return the slice this block really tests, and the cell it uses.

        A clobbered input has no cell, so its two halves are the same
        function -- descend the zero half, as the tree build does.  Every
        walk over the DAG has to skip in exactly this way, or the blocks
        that get laid down are not the ones the jumps name.
        """
        level = level_of(window)
        while perm[level] not in cell_of:
            window = window[: len(window) // 2]
            level += 1
        return window, cell_of[perm[level]]

    def children(window: str) -> tuple[str, str]:
        tested, _ = test_cell(window)
        half = len(tested) // 2
        return tested[:half], tested[half:]

    def collect(window: str) -> None:
        if len(set(window)) == 1 or window in seen:
            return
        seen.add(window)
        order.append(window)
        for child in children(window):
            collect(child)

    collect(test_cell(truth_table)[0])
    right_leaf_values = sorted(
        {
            child[0]
            for parent in order
            for child in (children(parent)[1],)
            if len(set(child)) == 1
        }
    )
    # The root falls through rather than being jumped to, so it carries no
    # marker; every other block is preceded by one, and the shared right
    # leaves follow them.
    label_of = {window: i for i, window in enumerate(order[1:], start=1)}
    leaf_label = {value: len(order) + i for i, value in enumerate(right_leaf_values)}

    def leaf_code(value: str, held: int) -> str:
        delta = _ASCII_ZERO + int(value) - held
        q, r = divmod(delta, 6)
        # one +5 beats five "62" pairs, as _six_five_const already does
        tail = "5" if r == 5 else "62" * r
        return "6" * q + tail + "A0"

    def right_branch(window: str) -> str:
        """Return the jump taken when the test succeeds.

        Always a jump, never inline code: the ``7`` skips exactly one
        token, so the taken branch has one token to spend.  That is why a
        right leaf needs a marker where a left one does not.
        """
        if len(set(window)) == 1:
            return "8" + _six_five_label(leaf_label[window[0]])
        return "8" + _six_five_label(label_of[window])

    def block(window: str, arrive: int) -> str:
        """One node's code: test, jump right, then fall into the left arm.

        ``arrive`` is the cell the pointer is on when this block is entered.
        Every parent of a shared block tests the same cell -- they are all
        at its level, since a slice's length fixes that -- so the walk to
        this block's own cell is the same whichever parent jumped.
        """
        _, cell = test_cell(window)
        left, right = children(window)
        code = _six_five_move(arrive, cell) + "78" + right_branch(right)
        if len(set(left)) == 1:
            return code + leaf_code(left[0], 8)
        # The left arm is a node of its own, reached by falling through the
        # test and then jumping -- unconditionally, since ``7`` owns the
        # condition and has already skipped the branch above.
        return code + "8" + _six_five_label(label_of[left])

    # Where the pointer sits on entry: the root is entered from the reads,
    # every other block from its parent's test cell.
    arrive_at = {order[0]: entry}
    for window in order:
        _, cell = test_cell(window)
        for child in children(window):
            if len(set(child)) != 1:
                arrive_at.setdefault(child, cell)
    out = block(order[0], arrive_at[order[0]])
    for window in order[1:]:
        out += "4" + block(window, arrive_at[window])
    for value in right_leaf_values:
        out += "4" + leaf_code(value, 9)
    return out


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
    # The tree is preferred while it fits: it is what every committed size
    # measurement was taken against, and sharing only pays once there are
    # duplicates worth merging.  Past the budget the DAG is tried before
    # the order is given up on.
    shared = _six_five_markers(truth_table) > 35
    if shared and _six_five_dag_cost(truth_table) > 35:
        return ""
    if perm == tuple(range(n)) and not shared:
        return _six_five_stream_ordered(truth_table)
    stored = stored_inputs(truth_table, perm)
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
        # one +5 beats five "62" pairs, as _six_five_const already does
        tail = "5" if r == 5 else "62" * r
        return "6" * q + tail + "A0"

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

    if shared:
        return reads + _six_five_shared(truth_table, perm, cell_of, pos, n)
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


def _six_five_stream_ordered(truth_table: str) -> str:
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
        raise GeneratorCapError(
            "the 6-5 decision tree has 35 branch labels, but this table needs "
            f"{labels} after folding its constant subtrees (n == {n})"
        )
    marker = 0

    def build(rows: list[int], bit: int, base: int) -> str:
        nonlocal marker
        if len(rows) == 1:
            delta = _ASCII_ZERO + int(truth_table[rows[0]]) - base
            q, r = divmod(delta, 6)
            tail = "5" if r == 5 else "62" * r
            return "6" * q + tail + "A0"
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
