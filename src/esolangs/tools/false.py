"""FALSE boolean program builder: a decision tree of nested lambdas.

A node reads with ``^``, keeps the bit with ``1&``, and runs the matching
half as a ``[...]?`` lambda; a leaf prints its bit with ``.`` after reading
the inputs below it with ``^%``, which a caller's next program would
otherwise be handed.  A node over two constant halves is its own literal.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table, constant_span_test

#: ``'0`` and ``'1`` differ in their low bit, so ``1&`` is the bit and ``?``
#: takes any nonzero flag; ``$`` leaves a copy under it for the ``0`` test.
_TEST_ONE = "^1&$["
#: ``0=`` consumes that copy here, so a node is stack-neutral.
_TEST_ZERO = "]?0=["
_CLOSE = "]?"
_SKIP = "^%"
#: The printed bit of a node whose halves are the constants ``0`` and ``1``,
#: and of one whose halves are ``1`` and ``0``: ``'0=`` is ``-1`` on a zero.
_SAME = "^1&"
_FLIPPED = "^'0=_"


def false(truth_table: str) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)
    constant = constant_span_test(truth_table)
    pieces: list[str] = []
    # A tuple is a span still to write; a string is text already placed.
    work: list[str | tuple[int, int, int]] = [(0, 0, len(truth_table))]
    while work:
        item = work.pop()
        if isinstance(item, str):
            pieces.append(item)
            continue
        level, lo, hi = item
        if level == n or constant(lo, hi):
            pieces.append(_SKIP * (n - level) + truth_table[lo] + ".")
            continue
        mid = (lo + hi) // 2
        if constant(lo, mid) and constant(mid, hi):
            read = _SAME if truth_table[mid] == "1" else _FLIPPED
            pieces.append(read + _SKIP * (n - level - 1) + ".")
            continue
        pieces.append(_TEST_ONE)
        # Pushed back to front, so the one half is written first.
        work += [_CLOSE, (level + 1, lo, mid), _TEST_ZERO, (level + 1, mid, hi)]
    return "".join(pieces)
