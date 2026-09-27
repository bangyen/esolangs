"""FALSE boolean program builder: a decision tree of nested lambdas.

``false(truth_table)`` emits one node per subtable.  A node reads its input
with ``^``, compares the character to ``1`` and to ``0``, and runs the
matching half as a ``[...]?`` lambda; a leaf prints its bit with ``.``.
Both halves are spelled, so the emission is ``a * T + b`` characters -- 15
per internal node, and two plus two per unread input for a leaf.

A subtable whose rows agree collapses to a leaf, but the leaf still reads
the inputs below it -- ``^%`` apiece -- because the reads are the interface:
a program that answered a constant table without reading would leave the
caller's bits on the stream for whatever runs next.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table, separated_tree_text

#: Read a character, turn it into a bit, and leave a copy of it under the
#: ``1`` test.  ``$`` before ``1=`` is what lets the ``0`` test read the
#: same bit after the true branch has run and rebalanced the stack.
_TEST_ONE = "^'0-$1=["
#: Close the true branch and open the false one: the bit is still under the
#: flag, so ``0=`` consumes it here and the node ends stack-neutral.
_TEST_ZERO = "]?0=["
_CLOSE = "]?"
#: One unread input at a collapsed leaf: read it and drop it.
_SKIP = "^%"


def false(truth_table: str) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)

    def leaf(level: int, row: int) -> str:
        return _SKIP * (n - level) + truth_table[row] + "."

    # The one-half first, because ``1=`` is the test that opens the node.
    return separated_tree_text(
        truth_table,
        leaf,
        head=_TEST_ONE,
        between=_TEST_ZERO,
        close=_CLOSE,
        one_first=True,
    )
