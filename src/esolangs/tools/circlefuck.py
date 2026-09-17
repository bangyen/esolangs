"""Boolean-function generators for Circlefuck and its byte dialect."""

from collections.abc import Sequence

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Circlefuck reads each input with ``,`` and normalizes it to 0/1 with 48
    ``-``s, then a decision tree branches on the cells from the last input
    down. Each leaf starts from a cleared cell, so it sets the result with
    ``+``s, prints it, and halts with ``@`` -- halting at the leaf means the
    tree never needs to skip the sibling branch.  A boolean table is just
    the byte-valued generator with ``48 + bit`` outputs.

    A subtree whose rows all agree folds to a leaf; see
    :func:`circlefuck_byte`, which both share.
    """
    # Validated here rather than left to ``circlefuck_byte``: that one takes
    # a *byte* table, where a single entry is a legal constant, so it cannot
    # carry the boolean generators' "at least one input" rule.
    _validate_truth_table(truth_table)
    return circlefuck_byte([_ASCII_ZERO + int(bit) for bit in truth_table])


def circlefuck_byte(truth_table: Sequence[int]) -> str:
    """Build a Circlefuck program computing a byte-valued function.

    ``truth_table`` is a sequence of ``2**n`` byte values (0-255) indexed by
    the inputs (most significant first); the input count ``n`` is implied
    by the table length.  This is the boolean generator generalized to
    arbitrary byte outputs: each leaf prints ``chr(value)`` instead of
    ``chr(48 + bit)``.

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer.  The reads sit above the tree and
    are unconditional, so a folded program consumes its input exactly as an
    unfolded one does.

    **The tree compares its identity and greedy input orders.**  Unlike
    generators whose nodes
    *name* the input they test, a Circlefuck node tests whatever cell the
    pointer is over, so an order is not a renaming: the tree has to walk
    the pointer to the cell it wants, and the walk is a real cost the fold
    has to beat.  See :func:`_circlefuck_ordered`.
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    return _best_byte_order(truth_table, n)


def _best_byte_order(truth_table: Sequence[int], n: int) -> str:
    """Return the shorter program from the identity and greedy orders.

    The byte-valued twin of
    :func:`~esolangs.tools.helpers.best_input_order`, which takes a
    binary *string*; the search and its guarantees are the same.  The
    identity order goes first and ties keep it, so a table no reorder helps
    emits exactly what it emitted before.

    The identity and greedy orders are both built, so the heuristic cannot
    make the output longer.
    """
    best = _circlefuck_ordered(list(truth_table), tuple(range(n)))
    if n < 2:
        return best
    return min(best, _circlefuck_greedy(truth_table, n), key=len)


# Scoring passes the greedy order spends before it settles the rest by the
# last scores it has.  A pass is one walk over the rows, so this is what
# keeps the order a fixed number of passes rather than one per input; every
# table with this many essential inputs or fewer gets the full greedy.
_CIRCLEFUCK_PASSES = 8


def _essential_byte_inputs(truth_table: Sequence[int], n: int) -> list[int]:
    """Return the inputs the byte table depends on, ascending.

    An input is inessential when flipping it never changes the value: the
    two halves of every subtree that splits on it are the same.  In the
    packed table those halves are adjacent runs, so the test is one
    comparison per pair of sibling blocks -- ``2**n / 2**(b + 1)`` pairs
    for the input at row bit ``b``, a total of ``2**n`` Python steps over
    all inputs.  The bytes compared come to ``n * 2**n / 2``, which at a
    word width of ``w`` is ``n * 2**n / (2 w)`` word operations, and
    ``n <= w`` for any table that fits in memory, so this is O(T).
    """
    packed = bytes(truth_table)
    width = len(packed)
    essential = []
    for i in range(n):
        block = 1 << (n - 1 - i)
        if any(
            packed[lo : lo + block] != packed[lo + block : lo + 2 * block]
            for lo in range(0, width, 2 * block)
        ):
            essential.append(i)
    return essential


def _circlefuck_greedy(truth_table: Sequence[int], n: int) -> str:
    """Pick an order level by level, in a fixed number of passes.

    The inputs the table depends on go first, since splitting on any other
    folds nothing, and among them each level takes the one that creates
    the most constant subtrees (:func:`_constant_subtree_scores`, one pass
    over the rows per level, with the subtree keys carried from the level
    before).  After :data:`_CIRCLEFUCK_PASSES` passes the rest of the
    essential inputs follow the last pass's scores, and the inessential
    ones come last in stream order.

    Scoring every level was one pass per input, ``Theta(T log T)`` by
    construction.  On a 231-table corpus to twelve inputs, stopping at
    eight passes changes four programs by under half a percent and
    shrinks the corpus overall; a table with at most eight essential
    inputs gets exactly the full greedy.
    """
    essential = _essential_byte_inputs(truth_table, n)
    remaining = list(essential)
    order: list[int] = []
    keys = [0] * len(truth_table)
    for _ in range(_CIRCLEFUCK_PASSES):
        if not remaining:
            break
        scores = _constant_subtree_scores(truth_table, n, keys)
        best_input = max(remaining, key=lambda i: scores[i])
        order.append(best_input)
        remaining.remove(best_input)
        shift = n - 1 - best_input
        keys = [(key << 1) | ((row >> shift) & 1) for row, key in enumerate(keys)]
    if remaining:
        scores = _constant_subtree_scores(truth_table, n, keys)
        order.extend(sorted(remaining, key=lambda i: (-scores[i], i)))
    order.extend(i for i in range(n) if i not in essential)
    # ``_circlefuck_ordered`` descends its permuted row bits from least to
    # most significant, so its tuple is the reverse of this root-first score.
    return _circlefuck_ordered(list(truth_table), tuple(reversed(order)))


def _constant_subtree_scores(
    truth_table: Sequence[int], n: int, keys: list[int]
) -> list[int]:
    """Count the constant subtrees splitting each subtree on ``i``, per ``i``.

    ``keys[row]`` names the row's subtree: rows agreeing on every input in
    the prefix chosen so far share a key.  A subtree is constant when the
    table takes one value across all of its rows, which is exactly when the
    build folds it to a leaf.  The tests keep the one-prefix definition
    this is checked against.

    One pass over the rows.  A row's index *is* the vector of its input
    bits, so which half of its subtree the row falls into for every
    candidate at once is the index itself (candidates reading 1) and its
    complement (candidates reading 0).  Each subtree keeps, per table
    value, the OR of those two vectors, and a half is then constant where
    exactly one value's mask reaches it -- for every candidate in one word.
    """
    width = len(truth_table)
    full = (1 << n) - 1
    # Per subtree, per table value: the OR of the row indices carrying it
    # (which candidates' 1-halves it reaches) and of their complements
    # (which 0-halves).  Row indices count input 0 as the most significant
    # bit, so the masks are read back with the same reversal below.
    masks: dict[int, dict[int, list[int]]] = {}
    for row in range(width):
        subtree = masks.get(keys[row])
        if subtree is None:
            subtree = masks[keys[row]] = {}
        entry = subtree.get(truth_table[row])
        if entry is None:
            entry = subtree[truth_table[row]] = [0, 0]
        entry[0] |= row
        entry[1] |= full ^ row
    scores = [0] * n
    for subtree in masks.values():
        for half in (0, 1):
            # A half is constant where exactly one value reaches it.
            once = twice = 0
            for entry in subtree.values():
                twice |= once & entry[half]
                once |= entry[half]
            constant = once & ~twice
            while constant:
                low = constant & -constant
                scores[n - low.bit_length()] += 1
                constant ^= low
    return scores


def _circlefuck_ordered(truth_table: list[int], perm: tuple[int, ...]) -> str:
    """Emit one input order's Circlefuck program; see :func:`circlefuck_byte`.

    ``truth_table`` is in stream order and ``perm[k]`` is the input tested
    at level ``k``, so the tree's row index -- bit ``k`` for level ``k`` --
    is not the table's: every node carries its table index alongside,
    adding ``2**(n-1-perm[k])`` where the row adds ``2**(n-1-k)``.  That is
    what a permuted copy of the table used to spell out, at ``n`` steps
    per row; here it is one addition per node.

    A subtree folds when every row it could reach agrees.  Whether it does
    is settled bottom-up before anything is emitted -- a node is constant
    when both children are and agree -- one visit per node, where testing
    each node's rows as the build reached it read every row once per
    level.

    **The walk is what makes this generator's reorder a real question.**  A
    node here does not name its input, it tests the cell under the pointer,
    so a level costs ``|previous cell - perm[k]|`` move characters on top of
    its branch.  The identity order is the one the walk is free for -- it
    steps left one cell per level, the single ``<`` the unordered build
    emitted -- so any other order has to fold enough to pay for its moves.
    """
    n = len(perm)
    prog: list[str] = []

    def emit(c: str) -> None:
        prog.append(c)

    for _ in range(n):
        emit(",")
        prog.extend("-" * _ASCII_ZERO)
        emit(">")
    prog.pop()  # the trailing ">" would leave the pointer past the last input

    def move(source: int, target: int) -> None:
        """Walk the pointer from cell ``source`` to cell ``target``."""
        step = ">" if target > source else "<"
        prog.extend(step * abs(target - source))

    # ``folded[k][row]`` is the one value the subtree at ``(k, row)`` takes,
    # or ``None`` where its rows disagree; level ``k`` has ``2**(n-1-k)``
    # subtrees, one per setting of the bits below it.
    folded: list[list[int | None]] = [[None] * (1 << (n - 1 - k)) for k in range(n)]

    def settle(k: int, row: int, index: int) -> int | None:
        if k < 0:
            return truth_table[index]
        zero = settle(k - 1, row, index)
        one = settle(k - 1, row + (1 << (n - 1 - k)), index + (1 << (n - 1 - perm[k])))
        value = zero if zero is not None and zero == one else None
        folded[k][row] = value
        return value

    settle(n - 1, 0, 0)

    def leaf(value: int) -> None:
        if value:
            prog.extend("+" * value)
        emit(".")
        emit("@")

    def build(k: int, row: int, index: int, cell: int) -> None:
        """Emit the subtree at level ``k`` with the pointer over ``cell``."""
        if k < 0:
            leaf(truth_table[index])
            return
        value = folded[k][row]
        if value is not None:
            # Every row this subtree could reach agrees, so the bits it
            # would branch on cannot change the answer.  The reads are
            # unconditional, above the tree, so a folded program still
            # consumes its input the same way an unfolded one does.
            #
            # The ``[-]`` is what a full-depth leaf relies on: it is
            # emitted inside each ``[`` on the way down, so a leaf builds
            # its value on a cleared cell.  A folded leaf skips those
            # levels and so must clear the cell itself -- without this the
            # pointer still holds an input bit and every one-valued input
            # prints one too high.
            emit("[-]")
            leaf(value)
            return
        target = perm[k]
        move(cell, target)
        emit("[")
        emit("[-]")
        # Both arms leave the pointer wherever the deeper level put it, but
        # each arm re-aims from ``target`` itself: the ``[-]`` above cleared
        # the tested cell, so the loop runs at most once and the ``]`` is
        # reached with the pointer back under our control only if the arm
        # returns it.  Emitting the walk inside each arm rather than once
        # before the branch is what keeps the two arms independent.
        build(k - 1, row + (1 << (n - 1 - k)), index + (1 << (n - 1 - perm[k])), target)
        emit("]")
        build(k - 1, row, index, target)

    build(n - 1, 0, 0, n - 1)
    return "".join(prog)
