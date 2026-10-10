"""Retired plain emitters used by size-comparison tests."""

from collections.abc import Callable

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
)


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
    """Return a folded decision tree as text, with a separator between halves."""
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
