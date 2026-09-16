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


def _permute_byte_table(truth_table: Sequence[int], perm: tuple[int, ...]) -> list[int]:
    """Return ``truth_table`` re-indexed so input ``perm[i]`` sits at position ``i``.

    Row ``r`` of the result holds the value the original table gives when
    input ``perm[i]`` carries bit ``i`` of ``r`` -- the permuted frame
    :func:`~esolangs.tools.helpers.best_input_order` documents, in
    which every row index inside the build is self-consistent.
    """
    n = len(perm)
    out = [0] * len(truth_table)
    for row in range(len(truth_table)):
        source = 0
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            source |= bit << (n - 1 - perm[i])
        out[row] = truth_table[source]
    return out


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


def _circlefuck_greedy(truth_table: Sequence[int], n: int) -> str:
    """Pick an order level by level.

    Each remaining input is scored by how many constant subtrees choosing
    it next would create.  One pass over the rows scores every candidate
    for a level (:func:`_constant_subtree_scores`), so the whole order
    costs ``n`` passes; scoring each candidate with its own pass, keyed
    from scratch, was ``O(n**2)`` passes of ``O(n)`` work per row and made
    this build grow x2.5 per added input.

    The subtree keys are carried from level to level -- the chosen input's
    bit is shifted onto each row's key -- so a level is one pass over the
    rows and not one per input already in the order.
    """
    remaining = list(range(n))
    order: list[int] = []
    keys = [0] * len(truth_table)
    while remaining:
        scores = _constant_subtree_scores(truth_table, n, keys)
        best_input = max(remaining, key=lambda i: scores[i])
        order.append(best_input)
        remaining.remove(best_input)
        shift = n - 1 - best_input
        keys = [(key << 1) | ((row >> shift) & 1) for row, key in enumerate(keys)]
    # ``_circlefuck_ordered`` descends its permuted row bits from least to
    # most significant, so its tuple is the reverse of this root-first score.
    perm = tuple(reversed(order))
    return _circlefuck_ordered(_permute_byte_table(truth_table, perm), perm)


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

    ``truth_table`` is in the permuted frame -- bit ``k`` of a row index is
    the input tested at level ``k`` -- so the fold test below reads rows
    without consulting ``perm``.  ``perm`` surfaces only where the pointer
    has to be *aimed*: the inputs sit in cells ``0..n-1`` in stream order,
    and the cell level ``k`` tests is ``perm[k]``.

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

    def span(k: int, row: int) -> range:
        """Return the table rows the subtree at ``(k, row)`` stands for.

        Bit ``k`` of a row index is the input tested at level ``k``, so a
        subtree entered at level ``k`` has fixed the bits above ``k`` and
        varies the ones below: its rows are the stride the unordered build
        also walked, now in the permuted frame.
        """
        step = 2 ** (n - 1 - k)
        return range(row, len(truth_table), step)

    def build(k: int, row: int, cell: int) -> None:
        """Emit the subtree at level ``k`` with the pointer over ``cell``."""
        if k < 0:
            value = truth_table[row]
            if value:
                prog.extend("+" * value)
            emit(".")
            emit("@")
            return
        if len({truth_table[r] for r in span(k, row)}) == 1:
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
            build(-1, row, cell)
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
        build(k - 1, row + 2 ** (n - 1 - k), target)
        emit("]")
        build(k - 1, row, target)

    build(n - 1, 0, n - 1)
    return "".join(prog)
