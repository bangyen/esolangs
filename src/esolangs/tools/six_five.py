"""Boolean-function generator for 6:5.

:func:`six_five` routes a decision tree that folds constant subtrees,
shares duplicates past the label budget, falls back to a positional walk
(:func:`_six_five_walk`) when the distinct subtrees overflow, and past 35
inputs loops (:func:`_six_five_looped`), so it is total.  A
``six_five_arithmetic`` construction (``(T >> x) & 1`` over packed cells)
was retired: once the tree folded, any table small enough to pack was
one that folds inside the budget.
"""

import string

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _GREEDY_ORDER_MAX_ARITY,
    _greedy_input_order,
    _validate_truth_table,
    constant_span_test,
    permute_truth_table,
    stored_inputs,
)

__all__ = ["six_five"]

# ``0..9A..Z`` names 0..35 per the spec; the interpreter's fallthrough
# past ``Z`` is undefined behaviour (``docs/limitations.md``), not a feature.
_SIX_FIVE_MAX_LABEL = 10 + len(string.ascii_uppercase) - 1


def _six_five_label(value: int) -> str:
    """Return the single character 6-5 reads as ``value`` for a 7n/8n operand."""
    if not 0 <= value <= _SIX_FIVE_MAX_LABEL:
        raise ValueError(f"6-5 has no operand character for {value}")
    return str(value) if value < 10 else chr(value + 55)


def _six_five_markers(table: str) -> int:
    """How many branch labels the folded decision tree spends on ``table``.

    One per internal node the fold leaves; a slice whose characters agree
    folds to a leaf.  Pass a permuted table for that order's count -- the
    35-label budget is a per-order gate.  Spans, not slices: O(2**n).
    """
    constant = constant_span_test(table)

    def count(lo: int, hi: int) -> int:
        if constant(lo, hi):
            return 0
        mid = (lo + hi) // 2
        return 1 + count(lo, mid) + count(mid, hi)

    return count(0, len(table))


def six_five(truth_table: str) -> str:
    """Build a 6-5 program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  A
    node is ``78``: ``7`` compares the cell to 8, a zero bit skips the
    ``8n`` jump into the left subtree, a one bit jumps to the n-th ``4``.  A
    leaf adds ``48 + value - base`` (8 left, 9 right) with sixes and ``62``
    pairs, prints with ``A``, halts with ``0``.  Constant subtrees fold.

    Labels are 0..9 then A..Z (35), one per surviving internal node, so the
    choice is by count (:func:`_six_five_markers`), not ``n``, and per input
    order: an alternating table folds nothing in stream order but is NOT of
    the last input under a reorder.  Past the budget the tree is shared
    (:func:`_six_five_shared`): parity, once the cap's witness, is now the
    cheapest wide table (two distinct subtrees per level, 20 markers at
    n == 10 vs 1023), and dense n == 7 needs 47.  Past that the table goes
    on the tape (:func:`_six_five_walk`, one label per input) and past 35
    inputs :func:`_six_five_looped` (sixteen at any width).  Trees stay
    preferred while one fits.  Four orders compete: identity, fold-greedy,
    reverse, first-then-reversed (the last two find cheap pointer walks on
    symmetric tables; AND-8's 40320 orders took 17s vs milliseconds).  The
    greedy order is scored through :data:`_GREEDY_ORDER_MAX_ARITY`, as in
    :func:`best_input_order`; wider tables drop it.
    """
    n = _validate_truth_table(truth_table)
    best = ""
    identity = tuple(range(n))
    orders = dict.fromkeys(
        (
            identity,
            _greedy_input_order(truth_table, n)
            if n <= _GREEDY_ORDER_MAX_ARITY
            else identity,
            tuple(reversed(identity)),
            (0, *reversed(range(1, n))),
        )
    )
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

    Spends exactly ``n`` labels: the branching moves the pointer, not the
    cursor.  Row ``j`` is preloaded at stride ``n + j`` (cell ``2 * (n + j)``;
    ``1`` moves two cells), ones as ``62``.  Each bit is read where the
    pointer stands: bit 1 skips the ``8n`` into ``2**(n-1-i)`` strides, bit 0
    jumps past them; both share one more stride, so after ``n`` bits the
    pointer is at the indexed row and the leaf adds 48 and prints.  The
    shared stride keeps every ``B`` behind the final cell.  Dense n == 10:
    10 labels, 5319 chars, 1024 rows in 12s.
    """
    n = _validate_truth_table(truth_table)
    if n > _SIX_FIVE_MAX_LABEL:
        # A table of 2**36 entries in practice, but the walk's arithmetic
        # genuinely depends on the bound, so the wider table goes to the
        # walk that loops instead of spending a label per input.
        return _six_five_looped(truth_table)
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


#: The looped walk's markers in program order.  ``8n`` names the n-th ``4``
#: of the whole program, so a label is a position, and the list is the
#: allocation: sixteen for any table.
_SIX_FIVE_LOOP_MARKERS = (
    "back",
    "passes",
    "go",
    "dec",
    "left",
    "exit",
    "bit",
    "go2",
    "here",
    "advance",
    "zero",
    "join",
    "inc",
    "left2",
    "done",
    "here2",
)


def _six_five_looped(truth_table: str) -> str:
    """Emit the positional walk that spends sixteen labels at any width.

    One bit loop, with a bit's advance (``2**(n-1-i)`` rows on a 1) read off
    the tape.  Rows sit four cells apart from cell 4: value, *mark*, *flag*,
    scratch; cells 0..2 hold the bits- and passes-remaining counters (in
    sixes) and the start sentinel (5); an end sentinel (6) sits one row past
    the table, and the current row's flag is 1.  Row ``q``'s mark is its
    2-adic valuation ``v(q)``: after ``i`` bits the pointer is at a multiple
    of ``S = 2**(n-1-i)`` with ``q / S`` even, so ``q + S`` is the first row
    past ``q`` with valuation exactly ``n-1-i``; the advance loop walks marks
    until one reads zero, and the marks are kept at ``6 * (v(q) - (n-1-i))``
    by ``n-1`` decrement passes then one increment pass per bit.  Every loop
    tests with ``7n`` and jumps back with the same label.  Size is linear;
    execution ``O(n * 2**n)``.  Every row at n <= 7 executed; reached only past 35.
    """
    n = _validate_truth_table(truth_table)
    label = {
        name: _six_five_label(index)
        for index, name in enumerate(_SIX_FIVE_LOOP_MARKERS, start=1)
    }

    def jump(name: str) -> str:
        return "8" + label[name]

    out = [
        # Cells 0..3: both counters pre-decrement before they test, so each
        # holds one more than the loops it allows; the start sentinel is 5.
        "6" * (n + 1),
        "13" + "6" * n,
        "13" + "5",
        "13" + "13",
    ]
    for row in range(1 << n):
        valuation = (row & -row).bit_length() - 1 if row else 0
        out.append("62" if truth_table[row] == "1" else "")
        out.append("13" + "6" * valuation)
        out.append("13" + ("62" if row == 0 else ""))
        out.append("1")
    out.append("13" + "13" + "6")  # the end sentinel
    # Back to the start sentinel.
    out.append("4" + "3333" + "75" + jump("back"))
    # n-1 decrement passes: count down, sweep right subtracting six from
    # each mark, sweep left.
    out.append("4" + "3" + "9" + "70" + jump("go") + jump("exit") + "4" + "13")
    out.append("4" + "11" + "3" + "9" + "13" + "76" + jump("dec"))
    out.append("4" + "3333" + "75" + jump("left") + jump("passes"))
    out.append("4" + "13")
    # The bit loop: count down, walk to the pointer's row, read the bit.
    out.append("4" + "33" + "9" + "70" + jump("go2") + jump("done") + "4" + "1")
    out.append("4" + "11" + "71" + jump("here"))
    out.append("13" + "B" + "2" * 8 + "79" + jump("zero"))
    # A 1: clear the flag, walk the marks to the first zero, plant the flag.
    out.append("3" + "59" + "3")
    out.append("4" + "11" + "70" + jump("advance"))
    out.append("13" + "62" + jump("join"))
    out.append("4" + "3")
    out.append("4")
    # The increment pass, then back to the counters.
    out.append("4" + "11" + "3" + "6" + "13" + "76" + jump("inc"))
    out.append("4" + "3333" + "75" + jump("left2") + jump("bit"))
    # Every bit read: walk to the pointer's row and print it.
    out.append("4" + "1")
    out.append("4" + "11" + "71" + jump("here2"))
    out.append("33" + "6" * 8 + "A0")
    return "".join(out)


def _six_five_dag_cost(truth_table: str) -> int:
    """Markers the shared build spends on ``truth_table``.

    One per distinct internal node less the root, plus one per distinct
    *right* leaf (:func:`_six_five_shared`).  Two windows are equal exactly
    when their children are, so each span is named by its children's names
    (a constant span by its length and value) and the names are interned:
    O(1) a node, O(2**n) in all, against hashing every slice.
    """
    constant = constant_span_test(truth_table)
    names: dict[tuple[object, object], int] = {}
    internal: set[int] = set()
    right_leaves: set[str] = set()

    def walk(lo: int, hi: int, *, right: bool) -> tuple[object, object]:
        if constant(lo, hi):
            if right:
                right_leaves.add(truth_table[lo])
            return (hi - lo, truth_table[lo])
        mid = (lo + hi) // 2
        name = (walk(lo, mid, right=False), walk(mid, hi, right=True))
        internal.add(names.setdefault(name, len(names)))
        return name

    walk(0, len(truth_table), right=False)
    return max(len(internal) - 1, 0) + len(right_leaves)


def _six_five_shared(
    truth_table: str,
    perm: tuple[int, ...],
    cell_of: dict[int, int],
    entry: int,
    n: int,
) -> str:
    """Emit the tree as a DAG, each distinct subtree laid down once.

    Parity at n == 6 has 63 internal nodes, 11 distinct.  ``8n`` names the
    n-th ``4`` in the program, not a scope, so branches may share a target.
    Two equal slices are always the same node: a slice's length fixes its
    level and :func:`_six_five_hoisted` makes the pointer's entry position a
    function of level alone.  Left leaves stay inline (the fall-through
    costs no marker); right leaves count from 9 and there are only two
    distinct ones, emitted once at the end.
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

        A clobbered input has no cell; descend the zero half, as the tree does.
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

        Always a jump: ``7`` skips exactly one token.
        """
        if len(set(window)) == 1:
            return "8" + _six_five_label(leaf_label[window[0]])
        return "8" + _six_five_label(label_of[window])

    def block(window: str, arrive: int) -> str:
        """One node's code: test, jump right, then fall into the left arm.

        ``arrive`` is the pointer's cell on entry, the same whichever parent jumped.
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

    ``truth_table`` is already permuted; ``perm`` names the stream input a
    node tests.  Returns ``""`` when this order overflows the 35 labels.
    Only inputs the tree branches on get a cell (others read into a shared
    scratch), so the kept bits are a contiguous block from cell 0.  A stored
    read is normalized where it lands with eight ``2``s (``7n``'s operand is
    capped at 35, so 48/49 cannot be tested).  A leaf prints from the cell
    it stands on (9 on the jump, 8 on the fall-through); the pointer's entry
    position is a function of level alone.
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

    constant = constant_span_test(truth_table)

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        nonlocal marker
        if level == n or constant(lo, hi):
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

    ``1`` steps two right, ``3`` one left (a no-op at cell 0), so rightward
    by ``d`` is ``ceil(d / 2)`` ones plus a ``3`` when ``d`` is odd.
    """
    if to > frm:
        distance = to - frm
        return "1" * ((distance + 1) // 2) + ("3" if distance % 2 else "")
    return "3" * (frm - to)


def _six_five_stream_ordered(truth_table: str) -> str:
    """Emit the read-at-the-node 6-5 program; see :func:`six_five`.

    Reads with ``B`` at the node and normalizes in place, so no pointer moves
    (competitive on shallow tables).  Splits in stream order: one candidate.
    A constant subtree folds (17 chars vs 226 at n == 3, 19 vs 946 at n == 5)
    but still spends its reads, so a folded leaf cannot use the 8/9 base and
    builds its digit from cell 1 instead.  Raises :class:`ValueError` past 35 labels.
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
            # Folded leaf: the skipped reads still run (stream sync) and
            # leave 48 or 49 in the cell, so build the digit from cell 1.
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

    Mostly ``6`` (~``value / 6`` chars; the ``62`` pairs cost ``2 * value``).
    """
    q, r = divmod(value, 6)
    if r == 5:
        return "6" * q + "5"  # one +5 beats five +1 pairs
    return "6" * q + "62" * r
