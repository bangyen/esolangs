"""Retired plain emitters used by size-comparison tests."""

from collections.abc import Callable

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
)


def false_plain(truth_table: str, n: int) -> str:
    """Return the tree with every half written out where it is used."""
    from esolangs.tools.false import (
        _FLIPPED,
        _SAME,
        _SKIP,
        _TEST_ONE,
    )

    def pair(level: int, mid: int) -> str:
        read = _SAME if truth_table[mid] == "1" else _FLIPPED
        return read + _SKIP * (n - level - 1) + "."

    return separated_tree_text(
        truth_table,
        lambda level, row: _SKIP * (n - level) + truth_table[row] + ".",
        head=_TEST_ONE,
        between="]?0=[",
        close="]?",
        one_first=True,
        pair=pair,
    )


def underload_plain(truth_table: str, *, short: bool = False) -> str:
    """Return the unshared promise tree, each leaf printing its own bit."""
    from esolangs.tools.underload import _SHORT_PAIR, PAIR, TEMPLATE_CHAR, _reflected

    n = _validate_truth_table(truth_table)
    reflected = _reflected(truth_table, n)
    constant = constant_span_test(reflected)

    def tree(level: int, lo: int, hi: int) -> str:
        if constant(lo, hi):
            return "!" * (n - level) + f"({reflected[lo]})S"
        mid = (lo + hi) // 2
        return f"({tree(level + 1, lo, mid)})~({tree(level + 1, mid, hi)})~^" + (
            "^" if short else ""
        )

    slots = TEMPLATE_CHAR * (len((_SHORT_PAIR if short else PAIR)[0]) * n)
    return slots + f"({tree(0, 0, len(reflected))})^"


def unlambda_plain(truth_table: str) -> str:
    """Return the unshared tree of forced promises, ``29T - 25`` at most."""
    from esolangs.tools.unlambda import _READ, _leaf

    n = _validate_truth_table(truth_table)
    return separated_tree_text(
        truth_table,
        lambda level, row: _leaf(n, level, truth_table[row]),
        head=_READ + "````k`?1i```?0i`d",
        between="v`d",
        close="v",
    )


def intercal_plain(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's template; level ``k`` selects input ``perm[k]``.

    ``truth_table`` is already permuted.  The assignments stay in name
    order, input ``i`` in ``.{n - i}``.
    """
    from esolangs.tools.intercal import _Expr, _mux, _program

    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)

    def tree(level: int, lo: int, hi: int) -> _Expr:
        if constant(lo, hi):
            return _Expr("constant", int(truth_table[lo]))
        mid = (lo + hi) // 2
        # In name order large variable numbers occur near the root, where
        # their decimal spelling is repeated least; this keeps source size
        # linear in T.  A reorder moves them only through the greedy cap
        # (n = 10), where no name is longer than two digits.
        zero, one = tree(level + 1, lo, mid), tree(level + 1, mid, hi)
        return _mux(_Expr("input", n - 1 - perm[level]), zero, one)

    return _program(n, [], tree(0, 0, len(truth_table)))


def separated_tree_text(
    truth_table: str,
    leaf: Callable[[int, int], str],
    *,
    head: str,
    between: str,
    close: str,
    one_first: bool = False,
    pair: Callable[[int, int], str] | None = None,
) -> str:
    """Return a folded decision tree as text, with a separator between halves.

    ``head`` opens a node and its first half, ``between`` closes that half
    and opens the other, and ``close`` ends the node; ``leaf(level, row)``
    writes a leaf, which a collapsed subtable reaches early.  ``one_first``
    lays the one-half before the zero-half, and ``pair(level, mid)`` writes
    a node whose halves are two different constants, split at row ``mid``.

    :func:`decision_tree_tokens` deliberately cannot act *between* the
    children, and a language whose branch is a delimited body -- FALSE's
    ``[...]?`` lambda, Unlambda's ``d`` promise -- needs exactly that: one
    delimiter per half, in the text, between the two.  One pre-order pass
    with an explicit stack, so a node's text is appended once rather than
    copied into its parent's: O(len(result)).
    """
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    pieces: list[str] = []
    # A tuple is a subtable still to write; a string is text already placed.
    work: list[str | tuple[int, int, int]] = [(0, 0, len(truth_table))]
    while work:
        item = work.pop()
        if isinstance(item, str):
            pieces.append(item)
            continue
        level, lo, hi = item
        if level == n or constant(lo, hi):
            pieces.append(leaf(level, lo))
            continue
        mid = (lo + hi) // 2
        if pair is not None and constant(lo, mid) and constant(mid, hi):
            pieces.append(pair(level, mid))
            continue
        halves = ((mid, hi), (lo, mid)) if one_first else ((lo, mid), (mid, hi))
        pieces.append(head)
        # Pushed back to front: the stack is popped, so this is source order.
        work += [close, (level + 1, *halves[1]), between, (level + 1, *halves[0])]
    return "".join(pieces)


def _ram0_linear(truth_table: str) -> str:
    """Emit a linear straight-line RAM initializer and indexed lookup."""
    from esolangs.tools.ram0 import _RAM0_INPUT

    n = _validate_truth_table(truth_table)
    tokens: list[str] = []
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(*commands: str) -> None:
        tokens.extend(commands)

    def mark(name: str) -> None:
        labels[name] = len(tokens)

    def jump(target: str) -> None:
        jumps.append((len(tokens), target))
        tokens.append("@")

    def unary(value: int) -> None:
        emit("Z", *("A" for _ in range(value)))

    def store_constant(address: int, value: int) -> None:
        unary(address)
        emit("N")
        unary(value)
        emit("S")

    # Cells 0/1 hold the initializer's address counter and the selected table
    # pointer; cells 2..n+1 hold the parameterized inputs.
    for i in range(n):
        unary(i + 2)
        emit("N", "Z", _RAM0_INPUT, "S")

    table_base = n + 2
    store_constant(0, table_base - 1)
    store_constant(1, table_base)

    # Advance cell 0, using the new address as a temporary copy of itself,
    # then store one table bit there.  This is constant work per row.
    for bit in truth_table:
        emit("Z", "L", "A", "N", "S")
        emit("Z", "N", "Z", "L", "A", "L", "S")
        emit("Z", "L", "N", "Z")
        if bit == "1":
            emit("A")
        emit("S")

    # Add each set bit's weight to the selected table pointer.  Across all
    # inputs the unary runs contain 2T-2 commands.
    for i in range(n):
        unary(i + 2)
        emit("L", "C")
        one = f"input_{i}_one"
        after = f"input_{i}_after"
        jump(one)
        jump(after)
        mark(one)
        unary(1)
        emit("N", "Z", "A", "L")
        emit(*("A" for _ in range(1 << (n - 1 - i))))
        emit("S")
        mark(after)

    emit("Z", "A", "L", "L")
    for at, target in jumps:
        target_at = labels[target]
        tokens[at] = str(target_at + 1)
    return " ".join(tokens)


def _jaune_linear(truth_table: str) -> str:
    """Emit a linear spatial table and travelling counter for Jaune."""
    n = _validate_truth_table(truth_table)
    out = ["v>" * n]

    # Cell n is counter 0; each row then owns one output cell and the next
    # counter cell.  Only one increment is needed for a true row.
    for bit in truth_table:
        out.append(">")
        if bit == "1":
            out.append("+")
        out.append(">")
    out.append("<" * (n + 2 * len(truth_table)))

    # Revisit each input, carry it in the hold cell, and add its unary weight
    # to counter 0.  The weights sum to T-1.
    for i in range(n):
        out.append("#")
        out.append(">" * (n - i))
        out.append("&" * (1 << (n - 1 - i)))
        if i + 1 < n:
            out.append("<" * (n - i - 1))

    # Move a decremented copy of the counter two cells at a time.  When it
    # reaches zero, the adjacent cell is the selected output.
    # A signed literal now includes ``-1?``; keep the decrement separate
    # from the label jump with an ignored character.
    out.append("1:2!#>>%&-x1?1!2:>^.")
    return "".join(out)
