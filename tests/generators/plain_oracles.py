"""Retired plain emitters used by size-comparison tests."""

from collections.abc import Callable

from esolangs.generation.helpers import (
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
