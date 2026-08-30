"""Boolean-function generator for 6:5.

:func:`six_five` routes a decision tree that folds its constant subtrees.

There used to be a second construction, ``six_five_arithmetic``, which
packed the inputs and the table into single cells and decoded the entry
with ``f(x) = (T >> x) & 1``.  It existed because the unfolded tree spent
one branch label per internal node against an alphabet believed to stop at
35, and so capped at n == 5.  Once the tree folded, the cap became a
property of the *table* rather than of ``n``, and the arithmetic path was
left unreachable: it needs ``T`` (or its complement) small enough to build,
which confines the ones to low indices, which leaves the rest of the table
constant -- exactly the shape that folds well inside any budget.  The label
ceiling has since been removed outright (see :func:`_label_for`), so the
arithmetic path is redundant twice over and stays retired.
"""

from itertools import permutations

from esolangs.interpreters.tape_based.six_five import num
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _greedy_input_order,
    _validate_truth_table,
    permute_truth_table,
    stored_inputs,
)

__all__ = ["six_five"]


def _label_for(ordinal: int) -> str | None:
    """Return the character 6-5 reads as ``ordinal`` in a ``7n``/``8n`` operand.

    The interpreter decodes an operand with
    :func:`~esolangs.interpreters.tape_based.six_five.num`, which is
    ``int(c)`` for a digit and ``ord(c.upper()) - 55`` otherwise -- so the
    operand alphabet is *not* the 36 characters ``0..9A..Z``.  Any character
    at all is a legal operand (the tokenizer merges whatever follows a
    ``7``/``8`` without inspecting it), and ``chr(ordinal + 55)`` names every
    ordinal whose character is not case-folded onto a smaller one.

    Returns ``None`` for an ordinal no single character can name -- the
    ranges where ``chr(ordinal + 55)`` is lowercase, since ``.upper()``
    aliases those down (``num("a") == 10``, not 42).  Those ordinals are
    *skipped* rather than lost: a bare ``4`` is a no-op the marker scan
    still counts, so padding walks past a dead ordinal at one character
    each.  This is why the generator has no label ceiling.

    The check is a round trip through the interpreter's own decoder rather
    than a hand-kept table of live ranges, so it cannot drift from it.
    """
    if ordinal < 1:
        return None
    if ordinal < 10:
        return str(ordinal)
    char = chr(ordinal + 55)
    # ``\n`` would be eaten by the comment-stripping regex; every other
    # character survives tokenization untouched.
    if char == "\n":
        return None
    try:
        return char if num(char) == ordinal else None
    except (TypeError, ValueError):
        return None


def _next_label(ordinal: int) -> tuple[int, str]:
    """Return the first ordinal at or after ``ordinal`` a character can name.

    Returns that ordinal and its character.  The caller emits one inert
    ``4`` per ordinal skipped, which is what walks the marker scan past the
    dead ones.
    """
    while True:
        char = _label_for(ordinal)
        if char is not None:
            return ordinal, char
        ordinal += 1


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

    **There is no branch-label ceiling.**  A label is an ``8n`` operand
    naming the n-th ``4`` in the program, and the interpreter decodes that
    operand as ``ord(c.upper()) - 55`` for any character at all -- not as a
    lookup in some 36-character alphabet.  ``0..9A..Z`` merely happens to
    name ordinals 1..35; the punctuation immediately after ``Z`` names 36,
    37, 38, and so on without end.  The only gaps are ordinals whose
    character is lowercase, which ``.upper()`` folds down onto a smaller
    value, and those are stepped over by an inert ``4`` apiece -- a bare
    ``4`` is a no-op the marker scan still counts.  :func:`_label_for`
    decides which is which by round-tripping through the interpreter's own
    decoder, so **every table renders at every ``n``**; the label count only
    sets the length.

    **The order search still runs, now purely for size.**  The count
    (:func:`_six_five_markers`) is what the orders are compared on, since a
    tree that folds harder is a shorter program.  Parity is the shape no
    renaming folds -- 63 standing nodes at n == 6 under all 720 orders,
    because any permutation of parity is parity -- so it is the longest
    build rather than a refusal.  An alternating table folds nothing in
    stream order but is only NOT of the last input, so one reorder collapses
    it to a single label.

    **The order search is capped at ``_ORDER_SEARCH_MAX`` inputs**, the same
    bound and the same greedy fallback ``best_input_order`` uses: searching
    AND-8's 40320 orders takes about 17 seconds against milliseconds for the
    greedy pick, and n == 9 would be half an hour.  Above the cap only the
    identity and the greedy order are built, so a wide table stays fast and
    still never grows.
    """
    n = _validate_truth_table(truth_table)
    # The node-read build goes first and ties keep it, so a table no hoist
    # and no reorder improves emits exactly what it emitted before.
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
        greedy = _greedy_input_order(truth_table, n)
        orders = [identity] if greedy == identity else [identity, greedy]
    for perm in orders:
        table = (
            truth_table if perm == identity else permute_truth_table(truth_table, perm)
        )
        candidate = _six_five_hoisted(table, perm)
        if len(candidate) < len(best):
            best = candidate
    return best


def _six_five_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit the read-up-front 6-5 program for one input order.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame and self-consistent; ``perm`` surfaces only where a node
    names the *stream* input it tests.  Every order builds -- there is no
    label ceiling to overflow (see :func:`_label_for`) -- so the orders are
    compared on length alone.

    **Only the inputs the tree branches on get a cell.**  The read contract
    asks that every input be *consumed*, not that every value be *kept*, so
    an input no node tests is read into a shared scratch cell the next such
    read overwrites.  The kept bits then occupy a contiguous block from cell
    0, so the tree navigates a span as wide as the function's real
    dependencies rather than one as wide as ``n``.

    **A stored read is normalized where it lands**, with the same eight
    ``2``s the node-read build spends.  Testing a raw 48/49 cell is not an
    option even with the operand range opened up: 48 and 49 are exactly the
    ordinals ``g`` and ``h`` would name, and those are lowercase, so
    ``.upper()`` aliases them down to 16 and 17 and no character reaches
    them (:func:`_label_for` returns ``None`` for both).  Normalizing at read
    time is therefore still what lets every node emit a plain ``78`` and
    every leaf inherit the 8/9 base arithmetic.

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
        # whose markers all precede it -- and before the right.  When the
        # next ordinal has no character, inert ``4``s pad up to one that
        # does; they sit between ``sub0`` and this node's own ``4``, where
        # they raise only this marker's ordinal and no earlier one, and
        # where no path reaches them (every leaf in ``sub0`` ends ``A0``).
        sub0 = node(level + 1, lo, mid, cell, 8)
        label, char = _next_label(marker + 1)
        pad = "4" * (label - marker - 1)
        marker = label
        sub1 = node(level + 1, mid, hi, cell, 9)
        return nav + "78" + "8" + char + sub0 + pad + "4" + sub1

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

    Every table builds: labels are ``8n`` operands over an unbounded
    character range, padded past the case-aliased gaps with inert ``4``s
    exactly as in :func:`_six_five_hoisted`.
    """
    n = _validate_truth_table(truth_table)
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
        label, char = _next_label(marker + 1)
        pad = "4" * (label - marker - 1)
        marker = label
        sub1 = build(g1, bit + 1, 9)
        return "B" + "2" * 8 + "78" + "8" + char + sub0 + pad + "4" + sub1

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
