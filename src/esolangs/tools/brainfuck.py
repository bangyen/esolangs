"""Build brainfuck Boolean programs with a folded decision tree."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
    essential_inputs,
    in_input_order,
    move_text,
)

__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return the folded tree for a binary, MSB-first ``2**n`` truth table."""
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return the folded decision tree, consuming every input unconditionally.

    Bits use cells 2i, flags 2i+1; branches clear both, and one final print
    reads the result. Flags cut n=10 sparse from 2,646 to 754 chars;
    folding and shared output cut n=10 XOR from 77,939 to 18,495.  Equal
    sibling halves merge; the code has no call, so other repeats are copied.
    An ignored input before the last kept one is read bare into the next
    kept cell, whose read overwrites it: 1.9% smaller at n=8 with one ignored,
    6.7% with two. A trailing one keeps its subtract; left at 48/49 it breaks
    the Workspace bound, and ``,[-]`` the execution bound (289 > 251 steps).
    """
    return in_input_order(truth_table, _bf_ordered)


def _bf_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero; an
    # ignored input is read into the next kept input's cell, which overwrites it
    kept = essential_inputs(truth_table, n)
    last = kept[-1] if kept else -1
    reads, pending = [], ""
    for i in range(n):
        if i in kept or i > last:
            reads.append(pending + "," + "-" * _ASCII_ZERO)
            pending = ""
        else:
            reads.append("")
            pending += ","
    cells = [(_RIGHT * 2).join(reads)]
    pos = 2 * max(n - 1, 0)

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)
