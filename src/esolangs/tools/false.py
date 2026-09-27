"""FALSE boolean program builder: a decision tree of nested lambdas.

A node reads with ``^``, tests the character against ``1`` then ``0``, and
runs the matching half as a ``[...]?`` lambda; a leaf prints its bit with
``.`` after reading the inputs below it with ``^%``, which a caller's next
program would otherwise be handed.  Both halves are spelled: ``17T - 15``.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table, separated_tree_text

#: ``$`` leaves a copy of the bit under the flag, for the ``0`` test to read
#: after the true branch has rebalanced the stack.
_TEST_ONE = "^'0-$1=["
#: ``0=`` consumes that copy here, so a node is stack-neutral.
_TEST_ZERO = "]?0=["
_CLOSE = "]?"
_SKIP = "^%"


def false(truth_table: str) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)

    def leaf(level: int, row: int) -> str:
        return _SKIP * (n - level) + truth_table[row] + "."

    return separated_tree_text(
        truth_table,
        leaf,
        head=_TEST_ONE,
        between=_TEST_ZERO,
        close=_CLOSE,
        one_first=True,
    )
