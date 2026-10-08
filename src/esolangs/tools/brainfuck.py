"""Build brainfuck Boolean programs with a folded decision tree."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
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
    An ignored input is still read with its 48 subtracted: a bare read is
    2.4% smaller at n=8 (7.5% with two ignored) but leaves 48/49 in the cell,
    breaking the Workspace bound (30 > 25 bits at n=3, ``00111100``).
    """
    return in_input_order(truth_table, _bf_ordered)


def _bf_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero
    cells = [(_RIGHT * 2).join(["," + "-" * _ASCII_ZERO] * n)]
    pos = 2 * max(n - 1, 0)

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)
