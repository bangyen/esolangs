"""Shared helpers for the boolean-function program generators.

The generators in this package build programs that read ``n`` boolean
inputs and print the result of a truth table; the helpers here are the
common input handling they all repeat.

A truth table's length determines its input count: a valid table has
``2**n`` entries, so ``n`` is recovered from the table alone and the
generators take no ``n`` parameter.
"""

from collections.abc import Callable
from itertools import permutations

# ``ord("0")``.  Input digits arrive as 48/49 from a byte-oriented read, and a
# result prints as ``_ASCII_ZERO + bit``, so this offset appears in every
# generator that reads or writes a digit.  Named because a bare ``48`` in a run
# of ``+`` or ``-`` reads as a magic number.
_ASCII_ZERO = 48
_ASCII_ONE = _ASCII_ZERO + 1  # ``ord("1")``, the digit the other branch prints

# Largest input count :func:`best_input_order` searches exhaustively.  The
# search builds ``n!`` programs of ``O(2**n)`` characters each, so the work
# is the product of two factorial-ish terms: 6 inputs is 720 builds of a
# 64-row table (milliseconds), 7 is 5040, and Dimensional's 12-input table
# would be 479 million.  Above this the order is picked greedily instead.
_ORDER_SEARCH_MAX = 6


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A valid table has ``2**n`` binary entries, so ``n`` is recovered from
    the length (a power of two).
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


def _complement(truth_table: str) -> str:
    """Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str) -> tuple[str, bool]:
    """Return the table (or its complement) and whether it was flipped.

    A sum-of-minterms program costs one term per row it selects, so a table
    with more ones than zeros is cheaper evaluated complemented and
    inverted: every term saved is paid for once, by whatever the language
    spells ``1 - x`` as.

    Every generator in that family uses this, and each reads the *returned*
    table -- selecting its ``1`` rows, which are the original's ``0`` rows
    when it flipped.  What differs is only how the flag is spent, and it is
    often free: Collatz Multiverse's OR already ends on the complement it
    would have added, and Point Break's loop guard is ``1 - f`` for reasons
    of its own, so both simply drop a step instead of gaining one.

    **A constant table may need excluding, and that is the caller's.**  An
    all-ones table complements to no minterms at all, which is the shape an
    all-*zeros* table has -- fine where the sum feeds an inversion that
    turns 0 back into 1, and wrong where the empty case is special-cased
    into a different construction, as Circuit Diagram's single self-fed
    gate is.
    """
    if truth_table.count("1") > len(truth_table) // 2:
        return _complement(truth_table), True
    return truth_table, False


def minterm_literals(row: int, n: int) -> list[tuple[int, bool]]:
    """Return the literals whose product is 1 exactly on ``row``.

    One ``(input, negated)`` pair per input, in input order: ``negated`` is
    True where ``row`` has that input clear, so the minterm wants ``1 - b``
    rather than ``b``.  The table is indexed most significant first, which
    is what makes input ``i`` bit ``n - 1 - i`` of the row index.

    Every sum-of-minterms generator needs exactly this, and each used to
    spell it out: ``(k >> (n - 1 - i)) & 1``, once per generator, with the
    MSB-first convention re-derived each time.  What they do *with* a
    literal is genuinely per-language -- qoibl names a variable, rotfuck
    picks a guard cell, Circuit Diagram indexes a bus pair -- so this
    returns the selection as data and leaves the emitting alone.

    Only the *literals* are shared.  Which rows to enumerate is the
    caller's: :func:`grapheme` evaluates whichever of the one-rows and
    zero-rows is the shorter list, so this takes one row at a time rather
    than walking the table itself.
    """
    return [(i, not (row >> (n - 1 - i)) & 1) for i in range(n)]


SetBit = Callable[[int, int], str]


def instantiate(template: str, bits: list[int], set_bit: SetBit) -> str:
    """Substitute each ``{Xi}`` placeholder.

    ``{Xi}`` becomes ``set_bit(i, bit)``, the language's code for setting
    input ``i`` to the bit.

    **A ``set_bit`` must return the same width for a 0 and a 1.**  This is the
    one place the generators deliberately give up shortness.  Spelling a zero
    as nothing at all (or as a shorter run than a one) is always tempting and
    always wrong: it makes the emitted program's *length* a function of its
    inputs, so the program leaks the very bits it is supposed to be evaluating.
    At ``n == 2`` an earlier Bio embedding ran to 236, 240, 244, and 248
    characters for the four instantiations -- the input recoverable from
    ``len(program)`` without reading a line of it.

    So pad the shorter side to equal width, and prefer padding with characters
    the language *executes* to a no-op over characters it merely ignores: the
    ignored kind is what a later cleanup pass strips, reintroducing the leak.
    :func:`~esolangs.tools.boolean.examples.bio` (``0oz;``) and
    ``bfstack`` (a four-character run proved minimal by exhaustive search over
    ``<>@[]``) are the worked examples.

    There used to be a ``{Ci}`` companion, filled by a ``set_comp`` argument,
    for a generator that wanted the complement embedded beside the bit.  No
    generator does: ``bfpda``'s node marker is a constant that never depends
    on the bit, and ``nocomment`` computes each complement at runtime from
    ``{Xi}`` with its ``s``-as-NOT-gate, so the placeholder never appeared in
    a template and every caller passed a ``set_comp`` nothing consumed.
    """
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
    return template


def permute_truth_table(truth_table: str, perm: tuple[int, ...]) -> str:
    """Rewrite ``truth_table`` so level ``k`` splits on original input ``perm[k]``.

    A decision tree splits on its inputs in a fixed order, but *which* order
    is free: the function is the same however its arguments are named.  This
    returns the table of the same function with the inputs renamed, so a
    walker that always splits most-significant-first ends up testing
    ``perm[0]`` at the root, ``perm[1]`` below it, and so on.

    The point is :func:`decision_tree_tokens`'s ``collapse`` (and the
    equivalent fold in the private recursions): a subtree folds to a leaf
    only when the rows it covers agree, and which rows a subtree covers is
    exactly what the split order decides.  ``11110000`` folds after one
    split; the same function written as ``10101010`` folds only at the
    bottom.  Reordering lets the second be emitted as the first.
    """
    _validate_truth_table(truth_table)
    return read_at(truth_table, perm, len(perm))


def read_at(truth_table: str, inputs: tuple[int, ...] | list[int], n: int) -> str:
    """Return the ``len(inputs)``-input table read at the given input positions.

    Slot ``k`` of the result varies with original input ``inputs[k]``, and
    every original input not named is held at 0.  Both callers want that one
    scatter of a small row index into a wide one, and they differ only in
    whether the naming is a permutation:

    * :func:`permute_truth_table` passes all ``n`` inputs in some order, so
      nothing is held and the result is the same function with its arguments
      renamed.
    * :func:`~esolangs.tools.boolean.minifuck._project` passes the
      *essential* inputs of a table that ignores the rest.  Holding an
      ignored input at 0 is exactly right there, since by construction it
      cannot change the answer -- which is what makes an ``n``-input table
      that ignores some inputs a smaller table wearing extra ones.

    ``n`` is passed rather than derived because the projecting caller's
    result is narrower than its input: ``len(inputs)`` is the *output* width
    and ``n`` the table's own, and the two coincide only for a permutation.
    Validation stays with the callers for the same reason -- minifuck
    projects tables it has already validated, and revalidating a narrowed
    table here would check the wrong width.
    """
    k = len(inputs)
    rows = []
    for row in range(2**k):
        original = 0
        for slot, i in enumerate(inputs):
            if (row >> (k - 1 - slot)) & 1:
                original |= 1 << (n - 1 - i)
        rows.append(truth_table[original])
    return "".join(rows)


def stored_inputs(truth_table: str, perm: tuple[int, ...]) -> set[int]:
    """Return the *stream* inputs a decision tree over ``perm`` has to keep.

    A level whose two halves agree everywhere cannot change the answer, so
    the tree never tests it and the read that fetched it can be discarded.
    What survives is everything else.

    The subtlety is the two frames.  ``truth_table`` is already permuted, so
    the fold is computed in *level* space -- level ``k`` splits on bit
    ``n - 1 - k`` of the permuted table -- while the reads run in *stream*
    order, over the inputs as the program consumes them.  Level ``k`` reads
    input ``perm[k]``, so the answer is translated back through ``perm``
    before it is returned; mixing the frames stores the wrong bits.
    """
    n = _validate_truth_table(truth_table)
    branching = {
        k
        for k in range(n)
        if any(
            truth_table[r] != truth_table[r | (1 << (n - 1 - k))]
            for r in range(2**n)
            if not r & (1 << (n - 1 - k))
        )
    }
    return {perm[k] for k in branching}


def best_input_order(
    truth_table: str,
    build: Callable[[str, tuple[int, ...]], str],
) -> str:
    """Return the shortest program over every input order.

    ``build(permuted_table, perm)`` emits the program that splits on
    ``perm[k]`` at level ``k``, reading the *permuted* table -- so every row
    index inside the build is in the permuted frame and self-consistent, and
    ``perm`` surfaces only where a node names the input it tests.

    **The winner is measured, not modelled.**  What a reorder saves is the
    subtrees it folds, but what it costs is per-language: RAM0 spells an
    input as a run of ``A`` as long as its address, so a cheap order there
    also wants low addresses deep, while Brainfuck pays the same for every
    input and cares only about the fold.  Building all ``n!`` candidates and
    taking the shortest gets both right, and any future language's cost
    shape for free.

    **The exhaustive search is capped at ``_ORDER_SEARCH_MAX`` inputs**,
    because ``n!`` builds of an ``O(2**n)`` program is the kind of cost that
    does not announce itself: Dimensional renders a 4096-row table, and
    ``12!`` is 479 million candidates, so an uncapped search turns a
    millisecond call into one that never returns.  Above the cap the order
    is chosen greedily instead -- level by level, each remaining input
    scored by how many of the subtrees it would create come out constant,
    which is the fold the search is hunting for -- at ``O(n**2)`` builds of
    nothing.  Both paths keep the guarantee below.

    The identity order is tried first and ties keep it, so a table no
    reorder improves emits exactly what it emitted before -- reordering can
    only shrink a program, never grow or churn one.  The greedy path takes
    the identity too whenever its own pick does not measure shorter.

    **The read order does not move.**  Only the order the tree *tests* the
    inputs in changes; the reads (or the load block, or the ``{Xi}``
    placeholders) stay in input order, so the program consumes its input
    stream exactly as it did.  That is what rules out Polynomial, whose node
    reads its own bit and which has *no addressable storage* -- one register,
    no tape and no variables -- so a bit can only be branched on before the
    next read overwrites it, and the test order is forced to be the stream
    order.

    6-5 and Jaune were once excluded here for the same phrase, wrongly: both
    have a tape and a pointer (``B``/``v`` read into the *current* cell,
    ``1``/``3`` and ``>``/``<`` move it), so their reads *could* be hoisted
    and their nodes could test any cell.  Only their old generators read at
    the node.  Both now hoist and reorder, which is what the phrase never
    ruled out -- what it rules out is a language with nowhere to put a bit,
    and 6-5's case is the one where hoisting also has a *price*: it spends a
    pointer move per node and a normalization per stored input, so
    :func:`~esolangs.tools.boolean.six_five.six_five` keeps its node-read
    build as one more candidate rather than replacing it, and measures.

    **Whether a generator can be reordered is a property of the language,
    not of what its generator happens to emit.**  Bitdeque looked excluded
    for pushing and popping in order, and is not: ``INJECT``/``EJECT`` work
    the head where ``PUSH``/``POP`` work the tail, so it is a deque and any
    bit can be rotated to an end.  Read the interpreter's op set before
    concluding a tree is stuck with its load order.

    **Modulous is the case where that check comes back negative, and the
    reason is worth keeping.**  Its stack reaches only the top two cells
    (``SWP`` swaps them; there is no rotate), so the obvious escape is to
    park the bits in its ``VAR1``-``VAR4`` variables and read them back in
    any order.  There is no reading them back: ``[PSH VAR1]`` *stores* the
    stack top into a variable, and the only op that reads one is
    ``[PRT VAR1 INT]``, which prints it.  Every conditional (``JMP ... IF``)
    inspects the stack top alone, so a bit in a variable can never be
    branched on -- the round trip has no return leg.

    Arithmetic does not open one either.  ``[VAR1+k]`` works, but ``k`` is a
    literal parsed at execution time, and ``ADD``/``SUB`` and ``JMP ... IF``
    all reject a variable operand: a variable can be *computed on* and never
    read back.  Verified against both this repo's interpreter and the wiki,
    which calls the variables settable and printable with no load.
    """
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    if n <= _ORDER_SEARCH_MAX:
        orders = [p for p in permutations(range(n)) if p != identity]
    else:
        greedy = _greedy_input_order(truth_table, n)
        orders = [] if greedy == identity else [greedy]

    # An empty candidate means "this order could not be built" -- Forth's
    # stack reader reaches only some arrangements of the bits, so an order
    # it cannot stack comes back empty -- and it is skipped rather than
    # winning on length 0.  A build that always succeeds never returns one,
    # and gets the plain behaviour.  (ZTOALC L was the original reason for
    # this: it searched for a collision-free line placement and some orders
    # had none.  It now constructs a branch-free lookup instead and does not
    # reorder at all, so it is no longer an example.)
    best = build(truth_table, identity)
    for perm in orders:
        candidate = build(permute_truth_table(truth_table, perm), perm)
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    return best


def _greedy_input_order(truth_table: str, n: int) -> tuple[int, ...]:
    """Pick an input order one level at a time, for tables too wide to search.

    At each level every input still unchosen is scored by the number of
    constant subtrees splitting on it would produce among the blocks still
    live, and the best-scoring one is taken.  That is a direct proxy for
    what the exhaustive search finds by measuring -- a constant subtree is
    the leaf a fold emits -- without the language's own per-input cost,
    which is why it is the fallback rather than the rule.

    Ties keep the lowest input index, so a table no order helps yields the
    identity and the caller emits exactly what it emitted before.
    """
    order: list[int] = []
    remaining = list(range(n))
    # Blocks of rows still to be separated: each is a list of row indices
    # that agree on every input chosen so far.
    blocks = [list(range(2**n))]
    while remaining:
        best_input = remaining[0]
        best_score = -1
        for i in remaining:
            bit = 1 << (n - 1 - i)
            score = 0
            for block in blocks:
                for half in (
                    [r for r in block if not r & bit],
                    [r for r in block if r & bit],
                ):
                    if half and len({truth_table[r] for r in half}) == 1:
                        score += 1
            if score > best_score:
                best_input, best_score = i, score
        order.append(best_input)
        remaining.remove(best_input)
        bit = 1 << (n - 1 - best_input)
        split = []
        for block in blocks:
            for half in (
                [r for r in block if not r & bit],
                [r for r in block if r & bit],
            ):
                # A block that is already constant needs no further splitting.
                if half and len({truth_table[r] for r in half}) > 1:
                    split.append(half)
        blocks = split
        if not blocks:
            # Everything below folds; the rest of the order cannot matter, so
            # keep it ascending to stay closest to the identity.
            order.extend(remaining)
            break
    return tuple(order)


Leaf = Callable[[int, int], list[str]]
Node = Callable[[int, list[str], list[str], int], list[str]]


def decision_tree_tokens(
    truth_table: str,
    leaf: Leaf,
    node: Node,
    *,
    parent_width: int | Callable[[int], int] = 0,
    start: int = 0,
    collapse: bool = False,
) -> list[str]:
    """Walk a truth table's decision tree, combining caller-emitted parts.

    ``leaf(level, row)`` returns the tokens for a leaf reached at ``level``
    standing for table entry ``row``; ``node(level, zero, one, at)``
    combines two finished subtrees, given the level it sits at and the index
    it begins at.  The walk is *post-order*: both children are complete
    before their parent runs.

    That is the whole contract, and it is what makes the shared skeleton
    worth having -- the recursion, the row split, and the running index are
    the same in every generator, while what a node and a leaf *say* is not.

    ``collapse`` returns a leaf as soon as a subtree's rows agree, so a
    constant slice emits no branching.

    **The index.**  A language with jumps needs to know where a subtree
    *lands*, not just what it says.  ``start`` is the index the whole tree
    begins at and ``parent_width`` how many tokens a node spends before its
    children -- a constant, or a function of the level when a node's own
    width grows with depth, as RAM0's address run does.  So ``at`` is the
    absolute index of the subtree ``node`` is building, which is what lets
    Bitdeque and RAM0 name the index their one-subtree starts at.  Both used
    to reserve a slot, recurse, and backpatch it; the index arrives up front
    instead.

    **What this deliberately cannot do**, with the generator each rules out:

    * A node acts only *after* both children, never between them.  6-5
      allocates its branch label between the two recursive calls and
      Polynomial appends to a shared buffer while threading the running cell
      value, so both need a hook this does not offer; giving them one turns
      the walker back into the recursion with more moving parts.
    * The zero subtree is laid down first.  Between emits its *one* subtree
      first, so the indices threaded here would reach its children swapped
      and every branch line would name the wrong target -- on any table
      whose two subtrees differ in size.  Which side goes first is a
      language's own business, so Between keeps its own arithmetic.
    * Rows split most-significant-first, keeping each subtree contiguous.
      Modulous walks its bits the other way, so its halves are not runs.
    * Lamfunc returns one plain string with no index to thread, so it would
      spend a one-element list at every use to gain four lines.
    * The grid generators' tree is a placement on a plane, not a token
      sequence, and none of this applies to them.

    Contrast :func:`decision_tree_program`, which shares an entire finished
    construction between two dialects of one language family; this shares
    only the skeleton and takes the emitting as callbacks.
    """
    n = _validate_truth_table(truth_table)
    width = parent_width if callable(parent_width) else lambda _level: parent_width

    def walk(level: int, lo: int, hi: int, at: int) -> list[str]:
        values = {truth_table[r] for r in range(lo, hi)}
        if level == n or (collapse and len(values) == 1):
            return leaf(level, lo)
        half = (hi - lo) // 2
        below = at + width(level)
        zero = walk(level + 1, lo, lo + half, below)
        one = walk(level + 1, lo + half, hi, below + len(zero))
        return node(level, zero, one, at)

    return walk(0, 0, len(truth_table), start)


def decision_tree_program(truth_table: str, right: str, left: str) -> str:
    """Build a brainfuck-family decision-tree program for ``truth_table``.

    Shared by the Brainfuck and Dimensional tree generators, which differ
    only in how a move is spelled: ``right``/``left`` are the tokens that
    step the pointer one cell up/down (``>``/``<`` for Brainfuck, ``>0``/
    ``<0`` for Dimensional, whose bare moves would read the cell value as
    the dimension).  Everything else -- the cell layout, the complement
    construction, and the tree itself -- is identical.

    Each input is read and normalized to 0/1 into cell ``2i``, its
    complement ``1 - b`` into cell ``2i + 1`` (via two temp cells at ``2n``
    and ``2n + 1``), and a node tests ``[b]`` for the one-side and
    ``[1 - b]`` for the zero-side: the complement guards naturally exclude
    the sibling, so only the matching leaf fires.  Each branch clears its
    guard cell before its ``]``, so the loop exits after one pass, and a
    fired leaf clears the result cell, so every ``]`` on the way out sees
    zero.  The tree is O(2**n) characters, sharing the bit tests.

    A subtree whose rows all agree collapses to a leaf rather than branching
    on bits that cannot change the answer: the side jumps straight to the
    result cell and prints.  This is what the deepest level always did --
    a one-row span is trivially constant -- lifted to any level, so a table
    like ``11110000`` spends one leaf per half instead of a full tree.  The
    inputs are still all read (the reads are unconditional, above the tree),
    so a folded program consumes its input the same way an unfolded one
    does.  Factor is the generator that most wants this: it encodes this
    program as an integer and refuses tables whose encoding exceeds
    Python's digit limit, so folding turns some previously unrenderable
    tables into runnable ones.
    """
    return best_input_order(
        truth_table,
        lambda table, perm: _decision_tree_program(table, right, left, perm),
    )


def _decision_tree_program(
    truth_table: str,
    right: str,
    left: str,
    perm: tuple[int, ...],
) -> str:
    """Emit one input order's program; see :func:`decision_tree_program`.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame.  ``perm`` is spent in exactly one place -- the cell a
    node tests, ``2 * perm[i]`` with its complement at ``2 * perm[i] + 1``.
    The reads and the complement construction above the tree run over the
    inputs in their own order and are untouched by it.
    """
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(right * delta if delta >= 0 else left * -delta)
        pos = target

    # read bits b_i at cell 2i, leaving the complements (cells 1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        cells.extend("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # complements nb_i = 1 - b_i at cell 2i+1 (t1, t2 at 2n, 2n+1)
    for i in range(n):
        move(2 * n)
        cells.append("[-]")
        move(2 * n + 1)
        cells.append("[-]")
        move(2 * i)
        cells.append("[")
        move(2 * n)
        cells.append("+")
        move(2 * n + 1)
        cells.append("+")
        move(2 * i)
        cells.append("-")
        cells.append("]")  # b -> t1, t2
        move(2 * i + 1)
        cells.append("+")  # nb = 1
        move(2 * n + 1)
        cells.append("[")
        move(2 * i + 1)
        cells.append("-")
        move(2 * n + 1)
        cells.append("-")
        cells.append("]")  # nb -= t2
        move(2 * n)
        cells.append("[")
        move(2 * i)
        cells.append("+")
        move(2 * n)
        cells.append("-")
        cells.append("]")  # restore b from t1

    # decision tree: node i entered at cell 2i, exits at cell 2i+1
    result = 2 * n + 2

    def leaf(value: str) -> None:
        cells.extend("+" * (_ASCII_ZERO + int(value)))
        cells.append(".")
        cells.append("[-]")  # clear the result so every ] on the way out sees zero

    def constant(i: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(i, combo)``, else None.

        ``combo`` has the bits above level ``i`` set, so the subtree covers
        the ``2**(n - i)`` rows that agree with it there -- a contiguous run,
        since rows split most-significant-first.
        """
        span = 2 ** (n - i)
        rows = truth_table[combo : combo + span]
        return rows[0] if len(set(rows)) == 1 else None

    def branch(i: int, combo: int) -> None:
        """Emit one side of node ``i``: a leaf when constant, else a subtree.

        A folded leaf prints from the result cell just as a full-depth one
        does, so the guard-cell dance around it is unchanged; only the depth
        it is reached at differs.
        """
        value = constant(i + 1, combo)
        # A subtree is entered at the cell holding *its* input, which is
        # ``2 * perm[i + 1]`` -- adjacent only when the order is the
        # identity, so the target is computed rather than stepped over.
        move(result if value is not None else 2 * perm[i + 1])
        if value is not None:
            leaf(value)
        else:
            node(i + 1, combo)

    def node(i: int, combo: int) -> None:
        bit = 2 * perm[i]
        one = combo | (1 << (n - 1 - i))
        move(bit)
        cells.append("[")  # one-side: if b_i
        branch(i, one)
        move(bit)
        cells.append("[-]")  # clear b_i so this ] exits
        cells.append("]")
        move(bit + 1)
        cells.append("[")  # zero-side: if 1 - b_i
        branch(i, combo)
        move(bit + 1)
        cells.append("[-]")  # clear the complement so this ] exits
        cells.append("]")

    move(2 * perm[0])
    node(0, 0)
    return "".join(cells)
