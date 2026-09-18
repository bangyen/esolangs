"""Boolean-function generator for Dimensional."""

from esolangs.tools.helpers import decision_tree_program

__all__ = ["dimensional", "dimensional_tree"]


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Dimensional has no halt command, so
    this is :func:`dimensional_tree`.  A survivor evaluator used to compete
    here; once the tree folded constant subtrees it won on every table at
    n <= 4, so the survivor went away.
    """
    return dimensional_tree(truth_table)


def dimensional_tree(truth_table: str) -> str:
    """Build a decision-tree Dimensional program for the given truth table.

    :func:`decision_tree_program`, shared with :func:`bf_tree`; every move
    is pinned ``>0``/``<0`` because a bare move takes the cell value as
    the dimension.
    """
    return decision_tree_program(truth_table, ">0", "<0")
