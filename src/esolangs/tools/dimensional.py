"""Boolean-function generator for Dimensional.

``d`` reads a line as a number and ``=30`` sets a byte from a literal, so the
``48 * (n + 1)`` characters of ASCII offset -- 70% of the brainfuck program at
``n == 2`` -- are never spent.  One dimension per input was reverted: a move
spells its dimension in decimal, so past ``n == 10`` each costs three
characters instead of two, x2.33 a doubling against the contract's x2.15.
"""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    decision_tree_body,
    move_text,
)

__all__ = ["dimensional", "dimensional_tree"]

#: A bare ``>`` would take its dimension from the cell's value.
_RIGHT, _LEFT = ">0", "<0"


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    Dimensional has no halt command, so this is :func:`dimensional_tree`.
    """
    return dimensional_tree(truth_table)


def dimensional_tree(truth_table: str) -> str:
    """Build a decision-tree Dimensional program for ``truth_table``.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Input
    ``k`` is a number in cell ``2k``, its flag at ``2k + 1``; the answer cell
    at ``2n`` starts at ``'0'``, so a ``'1'`` leaf's ``+`` finishes it.
    """
    return best_input_order(truth_table, _dimensional_ordered)


def _dimensional_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's program; ``perm`` is only the cell a node tests."""
    n = _validate_truth_table(truth_table)
    result = 2 * n
    reads = "".join("d" + (_RIGHT * 2 if k < n - 1 else "") for k in range(n))
    init = move_text(2 * (n - 1), result, _RIGHT, _LEFT) + f"={_ASCII_ZERO:02x}"
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, result)
    return reads + init + body + move_text(pos, result, _RIGHT, _LEFT) + "."
