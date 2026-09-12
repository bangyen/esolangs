r"""Boolean-function generator for Dimensional."""

from esolangs.tools.boolean.helpers import decision_tree_program

__all__ = ["dimensional", "dimensional_tree"]


def dimensional(truth_table: str) -> str:
    r"""Build a Dimensional program computing the given truth table."""
    return dimensional_tree(truth_table)


def dimensional_tree(truth_table: str) -> str:
    r"""Build a decision-tree Dimensional program for the given truth table."""
    return decision_tree_program(truth_table, ">0", "<0")
