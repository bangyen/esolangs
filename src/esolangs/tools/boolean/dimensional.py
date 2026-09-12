"""Boolean-function generator for Dimensional.

:func:`dimensional` is the decision tree (:func:`dimensional_tree`), which
folds constant subtrees.  It used to choose between that and a survivor
walk; see :func:`dimensional` for why the survivor went away.
"""

from esolangs.tools.boolean.helpers import decision_tree_program

__all__ = ["dimensional", "dimensional_tree"]


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Dimensional is brainfuck on a multidimensional tape and has no halt
    command, so a decision tree cannot rely on halting at the leaf.  This
    is :func:`dimensional_tree`, a decision tree sharing the bit tests.

    There used to be a second construction here -- a survivor evaluator
    that tested each one-row with its own cell -- and ``dimensional``
    returned whichever came out shorter, since the full tree paid for every
    input where the survivor paid only per one-row.  Once the tree started
    folding constant subtrees it won on *every* table at n <= 4, the
    constant ones included, so the survivor was unreachable and went away.
    """
    return dimensional_tree(truth_table)


def dimensional_tree(truth_table: str) -> str:
    """Build a decision-tree Dimensional program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is :func:`decision_tree_program`, shared with
    :func:`bf_tree`; every move is pinned ``>0``/``<0`` because a bare move
    would take the cell value as the dimension.  The tree is O(2**n)
    characters, less whatever its constant subtrees fold away.
    """
    return decision_tree_program(truth_table, ">0", "<0")
