"""Boolean-function generators for Circlefuck and its byte dialect."""

from collections.abc import Sequence

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def circlefuck(truth_table: str) -> str:
    """Build a Circlefuck program computing the given truth table.

    ``,`` reads each input, 48 ``-``s normalize, and a decision tree branches
    from the last input down; each leaf sets a cleared cell with ``+``s,
    prints, and halts with ``@``.  The byte-valued generator with
    ``48 + bit`` outputs (:func:`circlefuck_byte`).
    """
    # Validated here rather than left to ``circlefuck_byte``: that one takes
    # a *byte* table, where a single entry is a legal constant, so it cannot
    # carry the boolean generators' "at least one input" rule.
    _validate_truth_table(truth_table)
    return circlefuck_byte([_ASCII_ZERO + int(bit) for bit in truth_table])


def circlefuck_byte(truth_table: Sequence[int]) -> str:
    """Build a Circlefuck program computing a byte-valued function.

    ``truth_table`` is ``2**n`` byte values, MSB first; each leaf prints
    ``chr(value)``.  A constant subtree folds; the reads are unconditional
    above the tree.  Identity and greedy orders compete: a node tests the
    cell under the pointer, so an order is a walk with a real cost
    (:func:`_circlefuck_ordered`).
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

    The byte-valued twin of :func:`~esolangs.tools.helpers.best_input_order`;
    identity first, ties keep it.
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

    One C-level slice compare per pair of sibling blocks, ``2**n`` steps in
    all; the bytes compared are ``n * 2**n / 2``, intrinsic to the check.
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

    Essential inputs first, each level taking the one creating the most
    constant subtrees (:func:`_constant_subtree_scores`); after
    :data:`_CIRCLEFUCK_PASSES` the rest follow the last scores.  Full greedy
    was ``Theta(T log T)``; eight passes change four of a 231-table corpus
    by under half a percent.
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

    One pass: a row's index is its bit vector, so each subtree keeps per
    table value the OR of the index and its complement, and a half is
    constant where exactly one value's mask reaches it -- every candidate in
    one word.
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

    The table is in stream order, so each node carries its table index
    (``2**(n-1-perm[k])``) beside its row index.  Folding is settled
    bottom-up, one visit per node.  A level costs
    ``|previous cell - perm[k]|`` moves; the identity's walk is the single
    ``<`` the unordered build emitted.
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
